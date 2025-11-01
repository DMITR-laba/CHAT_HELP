"""
API endpoints для работы с Elasticsearch агентом
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from models import get_db
from services.elasticsearch_agent_service import ElasticSearchAgentService
from models.database import Article, Document
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/elasticsearch", tags=["elasticsearch"])


class ElasticSearchConnectionRequest(BaseModel):
    es_host: str = "http://localhost"
    es_port: int = 9200


class CreateAgentRequest(BaseModel):
    agent_type: str  # mistral, ollama, bert_spacy
    es_host: str = "http://localhost"
    es_port: int = 9200
    mistral_api_key: Optional[str] = None
    ollama_url: Optional[str] = None
    ollama_model: Optional[str] = "llama3:8b"
    bert_model: Optional[str] = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class SearchRequest(BaseModel):
    query: str
    index: str = "articles"  # Используем индекс articles вместо logs
    size: int = 10
    search_type: str = "keyword"  # keyword, semantic, hybrid
    agent_type: Optional[str] = None  # Если не указан, используется активный агент


class IndexDocumentRequest(BaseModel):
    index: str
    document: Dict[str, Any]


@router.post("/check-connection")
async def check_elasticsearch_connection(
    request: ElasticSearchConnectionRequest,
    db: Session = Depends(get_db)
):
    """Проверка подключения к Elasticsearch"""
    try:
        result = ElasticSearchAgentService.check_elasticsearch_connection(
            es_host=request.es_host,
            es_port=request.es_port
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка проверки подключения: {str(e)}")


@router.post("/agent/create")
async def create_agent(
    request: CreateAgentRequest,
    db: Session = Depends(get_db)
):
    """Создание и активация Elasticsearch агента"""
    try:
        kwargs = {
            'es_host': request.es_host,
            'es_port': request.es_port
        }
        
        if request.agent_type == "mistral":
            kwargs['mistral_api_key'] = request.mistral_api_key
        elif request.agent_type == "ollama":
            kwargs['ollama_url'] = request.ollama_url
            kwargs['model_name'] = request.ollama_model
        elif request.agent_type == "bert_spacy":
            kwargs['model_name'] = request.bert_model
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Неизвестный тип агента: {request.agent_type}. Доступны: mistral, ollama, bert_spacy"
            )
        
        agent = ElasticSearchAgentService.create_agent(request.agent_type, **kwargs)
        ElasticSearchAgentService.set_active_agent(request.agent_type)
        
        return {
            "success": True,
            "message": f"Агент {request.agent_type} успешно создан и активирован",
            "agent_type": request.agent_type
        }
    except Exception as e:
        logger.error(f"Ошибка создания агента: {e}")
        raise HTTPException(status_code=400, detail=f"Ошибка создания агента: {str(e)}")


@router.get("/agent/status")
async def get_agent_status(db: Session = Depends(get_db)):
    """Получение статуса активного агента"""
    try:
        agent = ElasticSearchAgentService.get_agent()
        if not agent:
            return {
                "active": False,
                "message": "Агент не активирован"
            }
        
        return {
            "active": True,
            "agent_type": ElasticSearchAgentService._active_agent,
            "elasticsearch_connected": True if agent.es else False
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка получения статуса: {str(e)}")


@router.post("/search")
async def search(
    request: SearchRequest,
    db: Session = Depends(get_db)
):
    """Выполнение поиска через Elasticsearch агента"""
    try:
        # Определяем, какой агент использовать
        if request.agent_type:
            agent = ElasticSearchAgentService.get_agent(request.agent_type)
            if not agent:
                raise HTTPException(
                    status_code=400,
                    detail=f"Агент {request.agent_type} не найден. Сначала создайте агента."
                )
        else:
            agent = ElasticSearchAgentService.get_agent()
            if not agent:
                raise HTTPException(
                    status_code=400,
                    detail="Агент не активирован. Сначала создайте и активируйте агента."
                )
        
        # Выполняем поиск в зависимости от типа
        if request.search_type == "keyword":
            results = agent.search(request.query, request.index, request.size)
            return {
                "success": True,
                "results": results,
                "total": len(results),
                "search_type": "keyword"
            }
        elif request.search_type == "semantic":
            if hasattr(agent, 'semantic_search'):
                if hasattr(agent.semantic_search, '__call__'):
                    # Проверяем, является ли метод async
                    import inspect
                    if inspect.iscoroutinefunction(agent.semantic_search):
                        results = await agent.semantic_search(request.query, request.index, request.size)
                    else:
                        results = agent.semantic_search(request.query, request.index, request.size)
                else:
                    results = agent.semantic_search(request.query, request.index, request.size)
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Текущий агент не поддерживает семантический поиск"
                )
            return {
                "success": True,
                "results": results,
                "total": len(results),
                "search_type": "semantic"
            }
        elif request.search_type == "hybrid":
            if hasattr(agent, 'hybrid_search'):
                import inspect
                if inspect.iscoroutinefunction(agent.hybrid_search):
                    results = await agent.hybrid_search(request.query, request.index)
                else:
                    results = agent.hybrid_search(request.query, request.index)
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Текущий агент не поддерживает гибридный поиск"
                )
            return {
                "success": True,
                "results": results,
                "search_type": "hybrid"
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Неизвестный тип поиска: {request.search_type}. Доступны: keyword, semantic, hybrid"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка поиска: {e}")
        raise HTTPException(status_code=400, detail=f"Ошибка поиска: {str(e)}")


@router.post("/index/document")
async def index_document(
    request: IndexDocumentRequest,
    db: Session = Depends(get_db)
):
    """Индексация документа через агента"""
    try:
        agent = ElasticSearchAgentService.get_agent()
        if not agent:
            raise HTTPException(
                status_code=400,
                detail="Агент не активирован. Сначала создайте и активируйте агента."
            )
        
        # Если агент поддерживает индексацию с эмбеддингами
        if hasattr(agent, 'index_document_with_embedding'):
            result = agent.index_document_with_embedding(request.index, request.document)
        else:
            # Обычная индексация
            result = agent.es.index(index=request.index, body=request.document)
        
        return {
            "success": True,
            "message": "Документ успешно проиндексирован",
            "result": result
        }
    except Exception as e:
        logger.error(f"Ошибка индексации: {e}")
        raise HTTPException(status_code=400, detail=f"Ошибка индексации: {str(e)}")


@router.get("/indices")
async def list_indices(db: Session = Depends(get_db)):
    """Получение списка индексов Elasticsearch"""
    try:
        agent = ElasticSearchAgentService.get_agent()
        if not agent:
            raise HTTPException(
                status_code=400,
                detail="Агент не активирован. Сначала создайте и активируйте агента."
            )
        
        indices = agent.es.cat.indices(format="json")
        return {
            "success": True,
            "indices": indices
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка получения списка индексов: {str(e)}")


@router.get("/available-models")
async def get_available_models(db: Session = Depends(get_db)):
    """Получение списка доступных моделей для разных типов агентов"""
    return {
        "mistral": {
            "embedding_model": "mistral-embed",
            "description": "Использует Mistral AI для создания эмбеддингов"
        },
        "ollama": {
            "models": [
                "llama3:8b",
                "llama3:70b",
                "mistral",
                "codellama",
                "neural-chat",
                "starling-lm",
                "nous-hermes",
                "llama2",
                "gemma:2b",
                "gemma:7b"
            ],
            "description": "Использует локальные модели Ollama"
        },
        "bert_spacy": {
            "models": [
                "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
                "sentence-transformers/all-MiniLM-L6-v2",
                "intfloat/multilingual-e5-base",
                "intfloat/multilingual-e5-large"
            ],
            "description": "Использует BERT для эмбеддингов и spaCy для NER"
        }
    }


class ElasticSearchAgentSettingsRequest(BaseModel):
    """Запрос на сохранение настроек Elasticsearch агента"""
    enabled: bool  # Включен ли агент для использования в чате
    agent_type: Optional[str] = None  # Тип агента (mistral, ollama, bert_spacy)
    model_name: Optional[str] = None  # Название модели
    es_host: Optional[str] = None
    es_port: Optional[int] = None


# Хранилище настроек в памяти (можно заменить на БД или файл)
_es_agent_settings = {
    "enabled": False,
    "agent_type": None,
    "model_name": None,
    "es_host": "http://localhost",
    "es_port": 9200
}


def get_es_agent_settings() -> dict:
    """Получение настроек Elasticsearch агента (синхронная функция для использования в других модулях)"""
    return _es_agent_settings.copy()


@router.post("/agent/settings")
async def save_agent_settings(
    request: ElasticSearchAgentSettingsRequest,
    db: Session = Depends(get_db)
):
    """Сохранение настроек Elasticsearch агента"""
    try:
        global _es_agent_settings
        _es_agent_settings.update({
            "enabled": request.enabled,
            "agent_type": request.agent_type or _es_agent_settings.get("agent_type"),
            "model_name": request.model_name or _es_agent_settings.get("model_name"),
            "es_host": request.es_host or _es_agent_settings.get("es_host"),
            "es_port": request.es_port or _es_agent_settings.get("es_port")
        })
        return {
            "success": True,
            "message": "Настройки сохранены",
            "settings": _es_agent_settings
        }
    except Exception as e:
        logger.error(f"Ошибка сохранения настроек: {e}")
        raise HTTPException(status_code=400, detail=f"Ошибка сохранения настроек: {str(e)}")


@router.get("/agent/settings")
async def get_agent_settings(db: Session = Depends(get_db)):
    """Получение настроек Elasticsearch агента"""
    try:
        # Проверяем статус активного агента
        agent = ElasticSearchAgentService.get_agent()
        agent_status = {
            "active": agent is not None,
            "agent_type": ElasticSearchAgentService._active_agent if agent else None
        }
        
        return {
            "success": True,
            "settings": _es_agent_settings,
            "agent_status": agent_status
        }
    except Exception as e:
        logger.error(f"Ошибка получения настроек: {e}")
        raise HTTPException(status_code=400, detail=f"Ошибка получения настроек: {str(e)}")


def _index_all_articles_task():
    """Фоновая задача для индексации всех статей"""
    # Создаем новую сессию для фоновой задачи
    from models import SessionLocal
    db = SessionLocal()
    try:
        agent = ElasticSearchAgentService.get_agent()
        if not agent:
            # Пытаемся создать агента автоматически
            default_host = 'elasticsearch' if os.getenv('POSTGRES_HOST') == 'postgres' else 'localhost'
            es_host = os.getenv('ELASTICSEARCH_HOST', default_host)
            es_port = int(os.getenv('ELASTICSEARCH_PORT', 9200))
            
            if not es_host.startswith('http'):
                es_url = f"http://{es_host}"
            else:
                es_url = es_host
            
            agent = ElasticSearchAgentService.create_agent(
                "bert_spacy",
                es_host=es_url,
                es_port=es_port,
                model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            )
            ElasticSearchAgentService.set_active_agent("bert_spacy")
        
        # Получаем все статьи
        articles = db.query(Article).all()
        logger.info(f"Найдено статей для индексации: {len(articles)}")
        
        if not articles:
            logger.warning("В базе данных нет статей")
            return
        
        index_name = "articles"
        
        # Проверяем существование индекса
        if agent.es.indices.exists(index=index_name):
            logger.info(f"Индекс {index_name} существует, обновляем...")
        else:
            # Создаем индекс с mapping
            mapping = {
                "mappings": {
                    "properties": {
                        "article_id": {"type": "integer"},
                        "title": {"type": "text", "analyzer": "russian"},
                        "text": {"type": "text", "analyzer": "russian"},
                        "url": {"type": "keyword"},
                        "language": {"type": "keyword"},
                        "embedding": {
                            "type": "dense_vector",
                            "dims": 384
                        },
                        "created_at": {"type": "date"}
                    }
                }
            }
            agent.es.indices.create(index=index_name, body=mapping, ignore=[400])
            logger.info(f"✅ Индекс {index_name} создан")
        
        indexed = 0
        errors = []
        
        for article in articles:
            try:
                doc = {
                    "article_id": article.id,
                    "title": article.title or "",
                    "text": article.text or "",
                    "url": article.url or "",
                    "language": article.language or "ru",
                    "created_at": article.created_at.isoformat() if article.created_at else None
                }
                
                # Создаем эмбеддинг
                content = f"{doc['title']} {doc['text']}"
                if content.strip():
                    embedding = agent.get_embedding(content)
                    doc['embedding'] = embedding.tolist()
                    
                    # Индексируем
                    agent.es.index(index=index_name, id=article.id, document=doc)
                    indexed += 1
                    if indexed % 10 == 0:
                        logger.info(f"  [{indexed}/{len(articles)}] Индексировано...")
                else:
                    errors.append(f"Статья {article.id}: пустой контент")
                    
            except Exception as e:
                errors.append(f"Статья {article.id}: {str(e)}")
                logger.error(f"Ошибка индексации статьи {article.id}: {e}")
        
        # Обновляем индекс
        agent.es.indices.refresh(index=index_name)
        count = agent.es.count(index=index_name)['count']
        
        logger.info(f"✅ Индексировано статей: {indexed}")
        logger.info(f"✅ Всего документов в индексе: {count}")
        if errors:
            logger.warning(f"⚠️ Ошибок: {len(errors)}")
        
    except Exception as e:
        logger.error(f"Критическая ошибка при индексации статей: {e}", exc_info=True)
    finally:
        db.close()


def _index_all_documents_task():
    """Фоновая задача для индексации всех документов"""
    # Создаем новую сессию для фоновой задачи
    from models import SessionLocal
    db = SessionLocal()
    try:
        agent = ElasticSearchAgentService.get_agent()
        if not agent:
            # Пытаемся создать агента автоматически
            default_host = 'elasticsearch' if os.getenv('POSTGRES_HOST') == 'postgres' else 'localhost'
            es_host = os.getenv('ELASTICSEARCH_HOST', default_host)
            es_port = int(os.getenv('ELASTICSEARCH_PORT', 9200))
            
            if not es_host.startswith('http'):
                es_url = f"http://{es_host}"
            else:
                es_url = es_host
            
            agent = ElasticSearchAgentService.create_agent(
                "bert_spacy",
                es_host=es_url,
                es_port=es_port,
                model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            )
            ElasticSearchAgentService.set_active_agent("bert_spacy")
        
        # Получаем все документы
        documents = db.query(Document).filter(Document.extracted_text.isnot(None)).all()
        logger.info(f"Найдено документов для индексации: {len(documents)}")
        
        if not documents:
            logger.warning("В базе данных нет документов с извлеченным текстом")
            return
        
        index_name = "documents"
        
        # Проверяем существование индекса
        if agent.es.indices.exists(index=index_name):
            logger.info(f"Индекс {index_name} существует, обновляем...")
        else:
            # Создаем индекс с mapping
            mapping = {
                "mappings": {
                    "properties": {
                        "document_id": {"type": "integer"},
                        "title": {"type": "text", "analyzer": "russian"},
                        "text": {"type": "text", "analyzer": "russian"},
                        "filename": {"type": "keyword"},
                        "file_type": {"type": "keyword"},
                        "language": {"type": "keyword"},
                        "embedding": {
                            "type": "dense_vector",
                            "dims": 384
                        },
                        "uploaded_at": {"type": "date"}
                    }
                }
            }
            agent.es.indices.create(index=index_name, body=mapping, ignore=[400])
            logger.info(f"✅ Индекс {index_name} создан")
        
        indexed = 0
        errors = []
        
        for document in documents:
            try:
                if not document.extracted_text:
                    continue
                    
                doc = {
                    "document_id": document.id,
                    "title": document.title or document.original_filename or "",
                    "text": document.extracted_text or "",
                    "filename": document.filename or "",
                    "file_type": document.file_type or "",
                    "language": document.language or "ru",
                    "uploaded_at": document.uploaded_at.isoformat() if document.uploaded_at else None
                }
                
                # Создаем эмбеддинг
                content = f"{doc['title']} {doc['text'][:5000]}"  # Ограничиваем длину для эмбеддинга
                if content.strip():
                    embedding = agent.get_embedding(content)
                    doc['embedding'] = embedding.tolist()
                    
                    # Индексируем
                    agent.es.index(index=index_name, id=document.id, document=doc)
                    indexed += 1
                    if indexed % 10 == 0:
                        logger.info(f"  [{indexed}/{len(documents)}] Индексировано...")
                else:
                    errors.append(f"Документ {document.id}: пустой контент")
                    
            except Exception as e:
                errors.append(f"Документ {document.id}: {str(e)}")
                logger.error(f"Ошибка индексации документа {document.id}: {e}")
        
        # Обновляем индекс
        agent.es.indices.refresh(index=index_name)
        count = agent.es.count(index=index_name)['count']
        
        logger.info(f"✅ Индексировано документов: {indexed}")
        logger.info(f"✅ Всего документов в индексе: {count}")
        if errors:
            logger.warning(f"⚠️ Ошибок: {len(errors)}")
        
    except Exception as e:
        logger.error(f"Критическая ошибка при индексации документов: {e}", exc_info=True)
    finally:
        db.close()


@router.post("/index/all-articles")
async def index_all_articles(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Запуск индексации всех статей в Elasticsearch"""
    try:
        agent = ElasticSearchAgentService.get_agent()
        if not agent:
            raise HTTPException(
                status_code=400,
                detail="Агент не активирован. Сначала создайте и активируйте агента."
            )
        
        # Запускаем задачу в фоне
        background_tasks.add_task(_index_all_articles_task)
        
        return {
            "success": True,
            "message": "Запущена индексация всех статей. Процесс выполняется в фоновом режиме."
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка запуска индексации статей: {e}")
        raise HTTPException(status_code=400, detail=f"Ошибка запуска индексации: {str(e)}")


@router.post("/index/all-documents")
async def index_all_documents(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Запуск индексации всех документов в Elasticsearch"""
    try:
        agent = ElasticSearchAgentService.get_agent()
        if not agent:
            raise HTTPException(
                status_code=400,
                detail="Агент не активирован. Сначала создайте и активируйте агента."
            )
        
        # Запускаем задачу в фоне
        background_tasks.add_task(_index_all_documents_task)
        
        return {
            "success": True,
            "message": "Запущена индексация всех документов. Процесс выполняется в фоновом режиме."
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка запуска индексации документов: {e}")
        raise HTTPException(status_code=400, detail=f"Ошибка запуска индексации: {str(e)}")