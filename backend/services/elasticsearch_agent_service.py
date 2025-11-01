"""
Сервис для работы с ИИ-агентом Elasticsearch
Поддерживает различные модели ИИ: Mistral, Ollama, BERT+spaCy
"""
import spacy
from elasticsearch import Elasticsearch
from datetime import datetime, timedelta
import re
import httpx
from typing import List, Dict, Any, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class ElasticSearchAgentBase:
    """Базовый класс для Elasticsearch агента"""
    
    def __init__(self, es_host: str = "http://localhost:9200", es_port: int = 9200):
        """
        Инициализация базового агента
        
        Args:
            es_host: Хост Elasticsearch
            es_port: Порт Elasticsearch (9200 или 9300)
        """
        # Пробуем разные порты и форматы URL
        es_urls = []
        # Добавляем с http:// префиксом если его нет
        base_host = es_host
        if not base_host.startswith('http://') and not base_host.startswith('https://'):
            base_host = f"http://{base_host}"
        
        es_urls.extend([
            f"{base_host}:{es_port}",
            f"{base_host}:9200",
            "http://elasticsearch:9200",
            "http://elasticsearch:9300"
        ])
        
        # Добавляем localhost только если не в Docker
        import os
        if not os.getenv('ELASTICSEARCH_HOST'):
            es_urls.extend(["http://localhost:9200", "http://localhost:9300"])
        
        self.es = None
        for url in es_urls:
            try:
                # Для Elasticsearch 8.x используем правильные параметры
                self.es = Elasticsearch(
                    [url], 
                    request_timeout=5,
                    http_compress=True,
                    verify_certs=False,
                    headers={"Accept": "application/vnd.elasticsearch+json; compatible-with=8"}
                )
                if self.es.ping(request_timeout=5):
                    logger.info(f"Подключено к Elasticsearch: {url}")
                    break
            except Exception as e:
                logger.warning(f"Не удалось подключиться к {url}: {e}")
                continue
        
        if not self.es or not self.es.ping(request_timeout=5):
            raise Exception("Не удалось подключиться к Elasticsearch. Убедитесь, что Elasticsearch запущен на порту 9200 или 9300")
        
        # Загружаем модели spaCy для русского и английского
        try:
            self.nlp_ru = spacy.load("ru_core_news_sm")
        except OSError:
            logger.warning("Русская модель spaCy не найдена. Запустите: python -m spacy download ru_core_news_sm")
            self.nlp_ru = None
        
        try:
            self.nlp_en = spacy.load("en_core_web_sm")
        except OSError:
            logger.warning("Английская модель spaCy не найдена. Запустите: python -m spacy download en_core_web_sm")
            self.nlp_en = None
    
    def detect_language(self, text: str) -> str:
        """Определяем язык текста"""
        if any(cyr_char in text.lower() for cyr_char in 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя'):
            return "ru"
        return "en"
    
    def extract_entities(self, query: str) -> tuple:
        """Извлекаем сущности из запроса"""
        lang = self.detect_language(query)
        nlp = self.nlp_ru if lang == "ru" else self.nlp_en
        
        if not nlp:
            return {"dates": [], "organizations": [], "persons": [], "locations": [], "products": [], "other": []}, lang
        
        doc = nlp(query)
        entities = {
            'dates': [],
            'organizations': [],
            'persons': [],
            'locations': [],
            'products': [],
            'other': []
        }
        
        for ent in doc.ents:
            if ent.label_ in ['DATE', 'TIME']:
                entities['dates'].append(ent.text)
            elif ent.label_ in ['ORG', 'ORGANIZATION']:
                entities['organizations'].append(ent.text)
            elif ent.label_ in ['PERSON', 'PER']:
                entities['persons'].append(ent.text)
            elif ent.label_ in ['GPE', 'LOC']:
                entities['locations'].append(ent.text)
            elif ent.label_ in ['PRODUCT']:
                entities['products'].append(ent.text)
            else:
                entities['other'].append(ent.text)
        
        return entities, lang
    
    def parse_date_range(self, date_text: str) -> Optional[Dict[str, str]]:
        """Парсим временные диапазоны из текста"""
        now = datetime.now()
        date_text_lower = date_text.lower()
        
        if 'последние' in date_text_lower or 'last' in date_text_lower:
            numbers = re.findall(r'\d+', date_text)
            if numbers:
                days = int(numbers[0])
                return {
                    'gte': (now - timedelta(days=days)).isoformat(),
                    'lte': now.isoformat()
                }
        
        if 'сегодня' in date_text_lower or 'today' in date_text_lower:
            return {
                'gte': now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
                'lte': now.isoformat()
            }
        
        if 'вчера' in date_text_lower or 'yesterday' in date_text_lower:
            yesterday = now - timedelta(days=1)
            return {
                'gte': yesterday.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
                'lte': (yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)).isoformat()
            }
        
        return None
    
    def build_es_query(self, query: str, index: str = "logs") -> Dict[str, Any]:
        """Строим Elasticsearch запрос на основе NLP-анализа"""
        entities, lang = self.extract_entities(query)
        
        es_query = {
            "query": {
                "bool": {
                    "must": [],
                    "filter": []
                }
            }
        }
        
        # Добавляем текстовый поиск
        if query:
            es_query["query"]["bool"]["must"].append({
                "multi_match": {
                    "query": query,
                    "fields": ["message", "content", "title", "text"],
                    "type": "best_fields",
                    "fuzziness": "AUTO"
                }
            })
        
        # Обрабатываем даты
        for date_entity in entities['dates']:
            date_range = self.parse_date_range(date_entity)
            if date_range:
                es_query["query"]["bool"]["filter"].append({
                    "range": {
                        "timestamp": date_range
                    }
                })
        
        # Добавляем фильтры по сущностям
        entity_filters = []
        for org in entities['organizations']:
            entity_filters.append({"term": {"organization": org}})
        for person in entities['persons']:
            entity_filters.append({"term": {"author": person}})
        for location in entities['locations']:
            entity_filters.append({"term": {"location": location}})
        
        if entity_filters:
            es_query["query"]["bool"]["filter"].extend(entity_filters)
        
        return es_query
    
    def search(self, query: str, index: str = "logs", size: int = 10) -> List[Dict[str, Any]]:
        """Выполняем интеллектуальный поиск"""
        es_query = self.build_es_query(query, index)
        
        try:
            # Для ES 8.x используем правильный синтаксис
            response = self.es.search(index=index, body=es_query, size=size)
            return self.format_results(response)
        except Exception as e:
            logger.error(f"Ошибка поиска в Elasticsearch: {e}")
            raise Exception(f"Ошибка поиска: {str(e)}")
    
    def format_results(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Форматируем результаты поиска"""
        results = []
        for hit in response.get('hits', {}).get('hits', []):
            source = hit.get('_source', {})
            results.append({
                'score': hit.get('_score', 0),
                'id': hit.get('_id'),
                'index': hit.get('_index'),
                'data': source
            })
        return results


class MistralElasticSearchAgent(ElasticSearchAgentBase):
    """Elasticsearch агент с использованием Mistral AI"""
    
    def __init__(self, es_host: str = "http://localhost:9200", es_port: int = 9200, 
                 mistral_api_key: Optional[str] = None):
        super().__init__(es_host, es_port)
        self.mistral_api_key = mistral_api_key or getattr(settings, 'mistral_api_key', None)
        self.mistral_base_url = "https://api.mistral.ai"
    
    async def semantic_search(self, query: str, index: str = "documents", top_k: int = 5) -> List[Dict[str, Any]]:
        """Семантический поиск с использованием Mistral эмбеддингов"""
        if not self.mistral_api_key:
            raise Exception("Mistral API ключ не установлен")
        
        # Получаем эмбеддинг запроса через Mistral API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.mistral_base_url}/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self.mistral_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "mistral-embed",
                    "input": query
                },
                timeout=30.0
            )
            
            if response.status_code != 200:
                raise Exception(f"Ошибка Mistral API: {response.status_code} - {response.text}")
            
            data = response.json()
            query_embedding = data['data'][0]['embedding']
        
        # Поиск в Elasticsearch с использованием векторного поиска
        script_query = {
            "script_score": {
                "query": {"match_all": {}},
                "script": {
                    "source": "cosineSimilarity(params.query_vector, 'embedding') + 1.0",
                    "params": {"query_vector": query_embedding}
                }
            }
        }
        
        response = self.es.search(
            index=index,
            body={
                "query": script_query,
                "size": top_k
            }
        )
        
        return self.format_semantic_results(response)
    
    def format_semantic_results(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Форматируем результаты семантического поиска"""
        results = []
        for hit in response.get('hits', {}).get('hits', []):
            score = hit.get('_score', 0)
            results.append({
                'score': score,
                'similarity': (score - 1.0) / 2.0,  # Нормализуем косинусное сходство
                'id': hit.get('_id'),
                'index': hit.get('_index'),
                'data': hit.get('_source', {})
            })
        return results
    
    async def hybrid_search(self, query: str, index: str = "documents") -> Dict[str, Any]:
        """Гибридный поиск: комбинация ключевых слов и семантики"""
        keyword_results = self.search(query, index)
        semantic_results = await self.semantic_search(query, index)
        
        return {
            'keyword_results': keyword_results,
            'semantic_results': semantic_results
        }


class OllamaElasticSearchAgent(ElasticSearchAgentBase):
    """Elasticsearch агент с использованием Ollama"""
    
    def __init__(self, es_host: str = "http://localhost:9200", es_port: int = 9200,
                 ollama_url: Optional[str] = None, model_name: str = "llama3:8b"):
        super().__init__(es_host, es_port)
        ollama_host = getattr(settings, 'ollama_host', 'http://localhost')
        ollama_port = getattr(settings, 'ollama_port', 11434)
        self.ollama_base_url = ollama_url or f"{ollama_host}:{ollama_port}"
        self.model_name = model_name
    
    async def _find_working_ollama_url(self) -> Optional[str]:
        """Находит рабочий URL для Ollama"""
        urls = [
            self.ollama_base_url,
            "http://localhost:11434",
            "http://host.docker.internal:11434"
        ]
        
        for url in urls:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{url}/api/version",
                        timeout=2.0
                    )
                    if response.status_code == 200:
                        return url
            except:
                continue
        return None
    
    async def semantic_search(self, query: str, index: str = "documents", top_k: int = 5) -> List[Dict[str, Any]]:
        """Семантический поиск с использованием Ollama эмбеддингов"""
        working_url = await self._find_working_ollama_url()
        if not working_url:
            raise Exception("Ollama недоступен")
        
        # Получаем эмбеддинг через Ollama
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{working_url}/api/embeddings",
                json={
                    "model": self.model_name,
                    "prompt": query
                },
                timeout=30.0
            )
            
            if response.status_code != 200:
                raise Exception(f"Ошибка Ollama: {response.status_code} - {response.text}")
            
            data = response.json()
            query_embedding = data.get('embedding', [])
        
        # Поиск в Elasticsearch
        script_query = {
            "script_score": {
                "query": {"match_all": {}},
                "script": {
                    "source": "cosineSimilarity(params.query_vector, 'embedding') + 1.0",
                    "params": {"query_vector": query_embedding}
                }
            }
        }
        
        response = self.es.search(
            index=index,
            body={
                "query": script_query,
                "size": top_k
            }
        )
        
        return self.format_semantic_results(response)
    
    def format_semantic_results(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Форматируем результаты семантического поиска"""
        results = []
        for hit in response.get('hits', {}).get('hits', []):
            score = hit.get('_score', 0)
            results.append({
                'score': score,
                'similarity': (score - 1.0) / 2.0,
                'id': hit.get('_id'),
                'index': hit.get('_index'),
                'data': hit.get('_source', {})
            })
        return results
    
    async def hybrid_search(self, query: str, index: str = "documents") -> Dict[str, Any]:
        """Гибридный поиск"""
        keyword_results = self.search(query, index)
        semantic_results = await self.semantic_search(query, index)
        
        return {
            'keyword_results': keyword_results,
            'semantic_results': semantic_results
        }


class BERTElasticSearchAgent(ElasticSearchAgentBase):
    """Elasticsearch агент с использованием BERT и spaCy"""
    
    def __init__(self, es_host: str = "http://localhost:9200", es_port: int = 9200,
                 model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        super().__init__(es_host, es_port)
        self.model_name = model_name
        
        try:
            # Используем sentence-transformers для более удобной работы
            self.model = SentenceTransformer(model_name)
            logger.info(f"Загружена модель: {model_name}")
        except Exception as e:
            logger.error(f"Ошибка загрузки модели: {e}")
            raise Exception(f"Не удалось загрузить модель {model_name}: {str(e)}")
    
    def get_embedding(self, text: str) -> np.ndarray:
        """Получаем эмбеддинг текста с помощью BERT"""
        try:
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding
        except Exception as e:
            logger.error(f"Ошибка получения эмбеддинга: {e}")
            raise Exception(f"Ошибка получения эмбеддинга: {str(e)}")
    
    def semantic_search(self, query: str, index: str = "documents", top_k: int = 5) -> List[Dict[str, Any]]:
        """Семантический поиск с использованием BERT эмбеддингов"""
        # Получаем эмбеддинг запроса
        query_embedding = self.get_embedding(query).tolist()
        
        # Поиск в Elasticsearch с использованием векторного поиска
        script_query = {
            "script_score": {
                "query": {"match_all": {}},
                "script": {
                    "source": "cosineSimilarity(params.query_vector, 'embedding') + 1.0",
                    "params": {"query_vector": query_embedding}
                }
            }
        }
        
        try:
            response = self.es.search(
                index=index,
                body={
                    "query": script_query,
                    "size": top_k
                }
            )
        except Exception as e:
            # Если индекс не поддерживает векторный поиск, делаем обычный поиск
            logger.warning(f"Векторный поиск недоступен, используем обычный поиск: {e}")
            return self.search(query, index, top_k)
        
        return self.format_semantic_results(response)
    
    def format_semantic_results(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Форматируем результаты семантического поиска"""
        results = []
        for hit in response.get('hits', {}).get('hits', []):
            score = hit.get('_score', 0)
            results.append({
                'score': score,
                'similarity': (score - 1.0) / 2.0,
                'id': hit.get('_id'),
                'index': hit.get('_index'),
                'data': hit.get('_source', {})
            })
        return results
    
    def hybrid_search(self, query: str, index: str = "documents") -> Dict[str, Any]:
        """Гибридный поиск: комбинация ключевых слов и семантики"""
        keyword_results = self.search(query, index)
        semantic_results = self.semantic_search(query, index)
        
        return {
            'keyword_results': keyword_results,
            'semantic_results': semantic_results
        }
    
    def index_document_with_embedding(self, index: str, document: Dict[str, Any]) -> Dict[str, Any]:
        """Индексируем документ с автоматическим созданием эмбеддинга"""
        content = document.get('content') or document.get('text') or document.get('message', '')
        
        if content:
            # Создаем эмбеддинг
            embedding = self.get_embedding(content).tolist()
            document['embedding'] = embedding
            
            # Извлекаем сущности для дополнительной индексации
            entities, lang = self.extract_entities(content)
            document['detected_language'] = lang
            document['entities'] = entities
        
        # Индексируем в Elasticsearch
        try:
            response = self.es.index(index=index, body=document)
            return response
        except Exception as e:
            logger.error(f"Ошибка индексации документа: {e}")
            raise Exception(f"Ошибка индексации: {str(e)}")


class ElasticSearchAgentService:
    """Фабрика и менеджер для Elasticsearch агентов"""
    
    _agents: Dict[str, Any] = {}
    _active_agent: Optional[str] = None
    
    @classmethod
    def create_agent(cls, agent_type: str, **kwargs) -> ElasticSearchAgentBase:
        """
        Создает агента указанного типа
        
        Args:
            agent_type: Тип агента (mistral, ollama, bert_spacy)
            **kwargs: Параметры для инициализации агента
        """
        es_host = kwargs.get('es_host', 'http://localhost')
        es_port = kwargs.get('es_port', 9200)
        
        if agent_type == "mistral":
            api_key = kwargs.get('mistral_api_key') or getattr(settings, 'mistral_api_key', None)
            agent = MistralElasticSearchAgent(
                es_host=es_host,
                es_port=es_port,
                mistral_api_key=api_key
            )
        elif agent_type == "ollama":
            model_name = kwargs.get('model_name', 'llama3:8b')
            ollama_url = kwargs.get('ollama_url')
            agent = OllamaElasticSearchAgent(
                es_host=es_host,
                es_port=es_port,
                ollama_url=ollama_url,
                model_name=model_name
            )
        elif agent_type == "bert_spacy":
            model_name = kwargs.get('model_name', 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
            agent = BERTElasticSearchAgent(
                es_host=es_host,
                es_port=es_port,
                model_name=model_name
            )
        else:
            raise ValueError(f"Неизвестный тип агента: {agent_type}")
        
        cls._agents[agent_type] = agent
        return agent
    
    @classmethod
    def get_agent(cls, agent_type: Optional[str] = None) -> Optional[ElasticSearchAgentBase]:
        """Получает активного или указанного агента"""
        if agent_type:
            return cls._agents.get(agent_type)
        elif cls._active_agent:
            return cls._agents.get(cls._active_agent)
        return None
    
    @classmethod
    def set_active_agent(cls, agent_type: str):
        """Устанавливает активного агента"""
        if agent_type not in cls._agents:
            raise ValueError(f"Агент {agent_type} не создан")
        cls._active_agent = agent_type
    
    @classmethod
    def check_elasticsearch_connection(cls, es_host: str = "http://localhost", es_port: int = 9200) -> Dict[str, Any]:
        """Проверяет подключение к Elasticsearch"""
        es_urls = [
            f"{es_host}:{es_port}",
            f"{es_host}:9200",
            f"{es_host}:9300",
            "http://localhost:9200",
            "http://localhost:9300"
        ]
        
        for url in es_urls:
            try:
                es = Elasticsearch(
                    [url], 
                    request_timeout=5,
                    http_compress=True,
                    verify_certs=False
                )
                if es.ping(request_timeout=5):
                    info = es.info()
                    return {
                        "status": "connected",
                        "url": url,
                        "version": info.get("version", {}).get("number", "unknown"),
                        "cluster_name": info.get("cluster_name", "unknown")
                    }
            except Exception as e:
                continue
        
        return {
            "status": "disconnected",
            "message": "Не удалось подключиться к Elasticsearch на портах 9200 или 9300"
        }

