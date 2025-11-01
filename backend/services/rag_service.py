from typing import List, Dict, Any
import time
import os
from app.core.config import settings
from services.database_service import DatabaseService
from services.document_service import DocumentService
from models.database import Article
import json
import chromadb
from chromadb.config import Settings as ChromaSettings
import requests
import httpx


def _load_ai_settings() -> Dict[str, Any]:
    """Загружает настройки AI из файла"""
    try:
        if os.path.exists("ai_settings.json"):
            with open("ai_settings.json", "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"Ошибка загрузки настроек AI: {e}")
    
    # Возвращаем настройки по умолчанию
    return {
        "response_model": "",
        "embedding_model": "",
        "api_service": "mistral",
        "api_key": "",
        "updated_at": None
    }

def _get_current_model_info() -> Dict[str, str]:
    """Возвращает информацию о текущей модели для ответов"""
    ai_settings = _load_ai_settings()
    response_model = ai_settings.get("response_model", "")
    
    if not response_model:
        return {
            "model_name": settings.mistral_model,
            "model_type": "mistral",
            "display_name": f"Mistral: {settings.mistral_model}"
        }
    
    if response_model.startswith("ollama:"):
        model_name = response_model.replace("ollama:", "")
        return {
            "model_name": model_name,
            "model_type": "ollama",
            "display_name": f"Ollama: {model_name}"
        }
    elif response_model.startswith("mistral:"):
        model_name = response_model.replace("mistral:", "")
        return {
            "model_name": model_name,
            "model_type": "mistral",
            "display_name": f"Mistral: {model_name}"
        }
    elif response_model.startswith("openai:"):
        model_name = response_model.replace("openai:", "")
        return {
            "model_name": model_name,
            "model_type": "openai",
            "display_name": f"OpenAI: {model_name}"
        }
    elif response_model.startswith("anthropic:"):
        model_name = response_model.replace("anthropic:", "")
        return {
            "model_name": model_name,
            "model_type": "anthropic",
            "display_name": f"Anthropic: {model_name}"
        }
    else:
        return {
            "model_name": response_model,
            "model_type": "unknown",
            "display_name": response_model
        }

async def _generate_with_ai_settings(prompt: str) -> tuple[str, Dict[str, str]]:
    """Генерирует ответ используя настройки AI и возвращает информацию о модели"""
    ai_settings = _load_ai_settings()
    response_model = ai_settings.get("response_model", "")
    model_info = _get_current_model_info()
    
    # Если модель не настроена, используем Mistral по умолчанию
    if not response_model:
        try:
            response = _generate_with_mistral(prompt)
            return response, model_info
        except Exception as e:
            return f"Ошибка генерации ответа: {str(e)}", model_info
    
    # Генерируем ответ в зависимости от типа модели
    try:
        if response_model.startswith("ollama:"):
            model_name = response_model.replace("ollama:", "")
            response = await _generate_with_ollama_async(model_name, prompt)
            return response, model_info
        elif response_model.startswith("mistral:"):
            model_name = response_model.replace("mistral:", "")
            api_key = ai_settings.get("api_key", settings.mistral_api_key)
            response = await _generate_with_mistral_async(model_name, api_key, prompt)
            return response, model_info
        elif response_model.startswith("openai:"):
            model_name = response_model.replace("openai:", "")
            api_key = ai_settings.get("api_key", "")
            response = await _generate_with_openai_async(model_name, api_key, prompt)
            return response, model_info
        elif response_model.startswith("anthropic:"):
            model_name = response_model.replace("anthropic:", "")
            api_key = ai_settings.get("api_key", "")
            response = await _generate_with_anthropic_async(model_name, api_key, prompt)
            return response, model_info
        else:
            # Фолбэк на Mistral
            response = _generate_with_mistral(prompt)
            return response, model_info
    except Exception as e:
        # Фолбэк на Mistral при ошибке
        try:
            response = _generate_with_mistral(prompt)
            return response, model_info
        except Exception as fallback_e:
            return f"Ошибка генерации ответа: {str(e)}", model_info

async def _generate_with_ollama_async(model_name: str, prompt: str) -> str:
    """Генерация ответа через Ollama"""
    # Пробуем разные адреса Ollama
    ollama_urls = [
        f"{settings.ollama_host}:{settings.ollama_port}",
        "http://localhost:11434",
        "http://host.docker.internal:11434"
    ]

    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False
    }

    for url in ollama_urls:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{url}/api/generate", json=payload, timeout=120)
                resp.raise_for_status()
                data = resp.json()
                return data.get("response", "")
        except:
            continue

    raise Exception("Не удается подключиться к Ollama ни по одному из адресов")

async def _generate_with_mistral_async(model_name: str, api_key: str, prompt: str) -> str:
    """Генерация ответа через Mistral API"""
    url = f"{settings.mistral_base_url}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "Ты — полезный ассистент, отвечай кратко и по-русски."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 1024,
        "stream": False,
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices", [])
        if choices:
            message = choices[0].get("message", {}).get("content", "")
            return message or ""
        return ""

async def _generate_with_openai_async(model_name: str, api_key: str, prompt: str) -> str:
    """Генерация ответа через OpenAI API"""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "Ты — полезный ассистент, отвечай кратко и по-русски."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 1024,
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices", [])
        if choices:
            message = choices[0].get("message", {}).get("content", "")
            return message or ""
        return ""

async def _generate_with_anthropic_async(model_name: str, api_key: str, prompt: str) -> str:
    """Генерация ответа через Anthropic API"""
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01"
    }
    payload = {
        "model": model_name,
        "max_tokens": 1024,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        content = data.get("content", [])
        if content:
            return content[0].get("text", "")
        return ""

def _generate_with_mistral(prompt: str) -> str:
    url = f"{settings.mistral_base_url}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.mistral_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.mistral_model,
        "messages": [
            {"role": "system", "content": "Ты — полезный ассистент, отвечай кратко и по-русски."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 1024,
        "stream": False,
    }
    last_err = None
    for attempt in range(4):  # до 4 попыток с экспоненциальной задержкой
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=120)
            # Специальная обработка 429
            if resp.status_code == 429:
                # Попробуем учесть Retry-After
                retry_after = resp.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else (0.5 * (2 ** attempt))
                time.sleep(min(delay, 5.0))
                continue
            resp.raise_for_status()
            data = resp.json() or {}
            choices = data.get("choices") or []
            if choices:
                message = (choices[0].get("message") or {}).get("content", "")
                return message or ""
            return ""
        except Exception as e:
            last_err = e
            time.sleep(0.5 * (2 ** attempt))
    # Фолбэк на локальный Ollama при перманентной ошибке/лимите
    try:
        return _generate_with_ollama(prompt)
    except Exception:
        # Возвращаем вежливый ответ вместо исключения
        return "Извините, временно недоступен сервис генерации. Повторите попытку позже."


class RAGService:
    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service
        self.doc_service = DocumentService(db_service.db)
        # Инициализация Chroma (локальный embedded режим) без телеметрии
        try:
            chroma_settings = ChromaSettings(anonymized_telemetry=False)
        except TypeError:
            # На случай несовместимой версии - просто создадим без дополнительных настроек
            chroma_settings = None
        if chroma_settings is not None:
            self.chroma_client = chromadb.PersistentClient(
                path=settings.chroma_persist_dir,
                settings=chroma_settings,
            )
        else:
            self.chroma_client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        self.collection = self.chroma_client.get_or_create_collection(name="kb_articles")
    
    async def generate_response(self, user_question: str, user_id: str) -> Dict[str, Any]:
        """
        Генерирует ответ на вопрос пользователя используя RAG подход
        """
        # 0. Предобработка и расширение вариантов запроса (для опечаток/синонимов/жаргона)
        normalized = self._normalize_query(user_question)
        variants = self._expand_query_variants(normalized)

        # 1. Гибридный поиск: семантика + текст + метаданные (теги/категории) + документы по нескольким вариантам
        collected: Dict[int, Article] = {}
        collected_docs: Dict[int, Any] = {}
        
        for q in variants:
            # Семантический поиск по статьям
            for art in self._search_semantic(q, k=5):
                collected.setdefault(art.id, art)
            # Текстовый поиск по статьям
            for art in self.db_service.search_articles_for_rag(q, limit=5):
                collected.setdefault(art.id, art)
            # Поиск по метаданным статей
            for art in self._search_by_meta(q, limit=5):
                collected.setdefault(art.id, art)
            # Поиск по документам
            for doc in self.doc_service.search_documents_for_rag(q, limit=5):
                collected_docs.setdefault(doc.id, doc)

            if len(collected) >= 5 and len(collected_docs) >= 3:
                break

        relevant_articles = list(collected.values())[:5]
        relevant_documents = list(collected_docs.values())[:3]
        
        if not relevant_articles and not relevant_documents:
            # Нет релевантов — ответим через AI без контекста кратко
            try:
                ai_response, model_info = await _generate_with_ai_settings(self._create_prompt(user_question, ""))
            except Exception as e:
                ai_response = f"Извините, сейчас не удалось обработать запрос: {e}"
                model_info = _get_current_model_info()
            chat_message = self.db_service.save_chat_message(
                user_id=user_id,
                message=user_question,
                response=ai_response,
                related_article_ids=[]
            )
            return {
                "response": ai_response,
                "related_articles": [],
                "model_info": model_info,
                "message_id": chat_message.id
            }
        
        # 2. Формирование контекста
        context = self._build_context(relevant_articles, relevant_documents)
        
        # 3. Создание промта для LLM
        prompt = self._create_prompt(user_question, context)
        
        # 4. Генерация ответа с использованием настроек AI
        try:
            ai_response, model_info = await _generate_with_ai_settings(prompt)
        except Exception as e:
            ai_response = f"Произошла ошибка при обработке запроса: {str(e)}. Пожалуйста, обратитесь к службе поддержки."
            model_info = _get_current_model_info()
        
        # 5. Сохранение сообщения в БД
        related_article_ids = [article.id for article in relevant_articles]
        related_document_ids = [doc.id for doc in relevant_documents]
        all_related_ids = related_article_ids + related_document_ids
        
        chat_message = self.db_service.save_chat_message(
            user_id=user_id,
            message=user_question,
            response=ai_response,
            related_article_ids=all_related_ids
        )
        
        return {
            "response": ai_response,
            "related_articles": relevant_articles,
            "related_documents": relevant_documents,
            "model_info": model_info,
            "message_id": chat_message.id
        }

    def _normalize_query(self, text: str) -> str:
        """Нормализует запрос: тримминг, приведение регистра, базовые замены брендов/жаргона."""
        if not text:
            return ""
        t = (text or "").strip()
        # Не понижаем регистр полностью, чтобы не портить аббревиатуры, но делаем точечные замены
        replacements = {
            "автокад": "AutoCAD",
            "ауто кад": "AutoCAD",
            "виндовс": "Windows",
            "эксель": "Excel",
            "оутлук": "Outlook",
            "аутлук": "Outlook",
            "мс офис": "MS Office",
            "мсо": "MSO",
            "гит": "GIT",
            "сбп": "СБП",
            "мт ": "МТ ",
            " диадок": " Диадок",
        }
        low = t.lower()
        for k, v in replacements.items():
            if k in low:
                # заменить, сохранив оригинальные куски через простую стратегию
                t = t.lower().replace(k, v)
                low = t.lower()
        # Нормализуем множественные пробелы
        while "  " in t:
            t = t.replace("  ", " ")
        return t.strip()

    def _expand_query_variants(self, text: str) -> List[str]:
        """Создает набор вариантов запроса для устойчивого поиска (опечатки, аббревиатуры, синонимы)."""
        variants = []
        base = text.strip()
        if not base:
            return [""]
        variants.append(base)

        # Карты синонимов/аббревиатур
        synonym_groups = [
            ["AutoCAD", "Автокад", "Autodesk AutoCAD"],
            ["Excel", "Эксель", "MS Excel"],
            ["Outlook", "Аутлук", "MS Outlook"],
            ["Windows", "Виндовс", "MS Windows"],
            ["GIT", "Git", "Система контроля версий GIT"],
            ["МТ", "MT", "МойСклад?", "МТ кассы"],
            ["GLPI", "глпи"],
            ["ОФД", "офд"],
            ["Диадок", "Diadoc"],
        ]

        def add_replaced(orig: str, a: str, b: str):
            if a in orig:
                variants.append(orig.replace(a, b))

        # Сформировать варианты замен по группам
        for group in synonym_groups:
            for a in group:
                for b in group:
                    if a != b:
                        add_replaced(base, a, b)

        # Упростить некоторые фразы
        simplifications = [
            ("Не могу ", "Не удается "),
            ("Ошибка ", "Сбой "),
            ("не работает", "не функционирует"),
        ]
        for a, b in simplifications:
            add_replaced(base, a, b)

        # Добавить англо/рус варианты ключевых слов
        keyword_variants = {
            "dialog": ["dialog", "диалог", "диалоговое окно"],
            "save": ["save", "сохранение", "сохранить"],
            "sync": ["sync", "синхронизация", "синхронизируются"],
        }
        for lst in keyword_variants.values():
            for a in lst:
                for b in lst:
                    if a != b:
                        add_replaced(base, a, b)

        # Дедупликация, ограничение
        seen = set()
        deduped = []
        for v in variants:
            vv = v.strip()
            if vv and vv.lower() not in seen:
                deduped.append(vv)
                seen.add(vv.lower())
            if len(deduped) >= 8:
                break
        return deduped
    
    def _build_context(self, articles: List[Article], documents: List[Any] = None) -> str:
        """Строит контекст из найденных статей и документов"""
        context_parts = []
        
        # Добавляем статьи
        for i, article in enumerate(articles, 1):
            context_part = f"""
Статья {i}:
Заголовок: {article.title}
Текст: {article.text[:1000]}{'...' if len(article.text) > 1000 else ''}
URL: {article.url or 'Не указан'}
"""
            context_parts.append(context_part)
        
        # Добавляем документы с поиском по чанкам
        if documents:
            for i, doc in enumerate(documents, len(articles) + 1):
                # Ищем релевантные чанки для документа
                relevant_chunks = self._search_document_chunks(doc.id, articles[0].text if articles else "")
                
                context_part = f"""
Документ {i}:
Заголовок: {doc.title or doc.original_filename}
Тема: {doc.topic or 'Не указана'}
Путь: {doc.path or 'Не указан'}
"""
                
                # Добавляем релевантные чанки
                if relevant_chunks:
                    context_part += "Релевантные фрагменты:\n"
                    for j, chunk in enumerate(relevant_chunks[:3], 1):  # Берем до 3 чанков
                        context_part += f"  Фрагмент {j}: {chunk.text[:500]}{'...' if len(chunk.text) > 500 else ''}\n"
                else:
                    # Если чанки не найдены, используем общее содержание
                    context_part += f"Содержание: {doc.extracted_text[:1000] if doc.extracted_text else 'Не извлечено'}{'...' if doc.extracted_text and len(doc.extracted_text) > 1000 else ''}\n"
                
                context_part += f"Краткое содержание: {doc.summary or 'Не создано'}\n"
                context_parts.append(context_part)
        
        return "\n".join(context_parts)
    
    def _search_document_chunks(self, document_id: int, query: str) -> List[Any]:
        """Ищет релевантные чанки в документе"""
        try:
            # Получаем чанки документа
            chunks = self.doc_service.get_document_chunks(document_id)
            if not chunks:
                return []
            
            # Простой поиск по тексту чанков (можно улучшить с помощью семантического поиска)
            relevant_chunks = []
            query_lower = query.lower()
            
            for chunk in chunks:
                if chunk.text and query_lower in chunk.text.lower():
                    relevant_chunks.append(chunk)
            
            # Если точного совпадения нет, берем первые несколько чанков
            if not relevant_chunks and chunks:
                relevant_chunks = chunks[:2]
            
            return relevant_chunks
        except Exception as e:
            print(f"Ошибка при поиске чанков документа {document_id}: {e}")
            return []
    
    def _create_prompt(self, question: str, context: str) -> str:
        """Создает промт для LLM"""
        return f"""
Контекст из базы знаний:
{context}

Вопрос пользователя: {question}

Ответ (отвечай на русском языке, будь конкретным и полезным):
"""

    def _search_by_meta(self, query: str, limit: int = 5) -> List[Article]:
        # Простая токенизация по пробелам и пунктуации
        import re
        tokens = re.findall(r"[\w\-]{2,32}", query, flags=re.UNICODE)
        try:
            return self.db_service.search_articles_by_meta(tokens, limit=limit)
        except Exception:
            return []
    
    def reindex_articles(self) -> Dict[str, Any]:
        """
        Переиндексирует все статьи в ChromaDB, используя встроенную модель ChromaDB
        """
        articles, total = self.db_service.get_articles(skip=0, limit=10000)
        
        # Удаляем старую коллекцию и создаем новую
        try:
            self.chroma_client.delete_collection("kb_articles")
        except Exception:
            pass
        
        # Создаем новую коллекцию без указания эмбеддингов - ChromaDB будет использовать свою модель
        self.collection = self.chroma_client.create_collection(name="kb_articles")
        
        if total == 0:
            return {"message": "Нет статей для индексации", "total_articles": 0, "status": "success"}
        
        # Обрабатываем статьи батчами по 10
        batch_size = 10
        processed = 0
        
        for i in range(0, len(articles), batch_size):
            batch_articles = articles[i:i + batch_size]
            ids = []
            documents = []
            metadatas = []
            
            for a in batch_articles:
                ids.append(str(a.id))
                documents.append((a.title or "") + "\n\n" + (a.text or ""))
                metadatas.append({"url": a.url or "", "language": a.language or "ru", "title": a.title})
            
            # Добавляем в коллекцию без эмбеддингов - ChromaDB сам их сгенерирует
            self.collection.add(ids=ids, documents=documents, metadatas=metadatas)
            processed += len(batch_articles)
            print(f"Processed {processed}/{total} articles")
        
        return {"message": "Переиндексация завершена", "total_articles": total, "status": "success"}

    def _embed_mistral_batch(self, texts: List[str]) -> List[List[float]]:
        """Получает эмбеддинги у Mistral для списка текстов"""
        url = f"{settings.mistral_base_url}/v1/embeddings"
        headers = {
            "Authorization": f"Bearer {settings.mistral_api_key}",
            "Content-Type": "application/json",
        }
        vectors: List[List[float]] = []
        # Mistral API поддерживает батчи; отправим одним запросом, если возможно
        try:
            payload = {"model": settings.mistral_embed_model, "input": texts}
            resp = requests.post(url, headers=headers, json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json() or {}
            items = data.get("data") or []
            for item in items:
                emb = item.get("embedding", [])
                if len(emb) == 1024:  # Проверяем правильную размерность
                    vectors.append(emb)
                else:
                    vectors.append([0.0] * 1024)  # Fallback с правильной размерностью
        except Exception:
            # Фолбэк: попробуем по одному, чтобы вернуть хоть что-то
            for t in texts:
                try:
                    payload = {"model": settings.mistral_embed_model, "input": t}
                    r = requests.post(url, headers=headers, json=payload, timeout=60)
                    r.raise_for_status()
                    dd = r.json() or {}
                    emb = ((dd.get("data") or [{}])[0]).get("embedding", [])
                    if len(emb) == 1024:
                        vectors.append(emb)
                    else:
                        vectors.append([0.0] * 1024)
                except Exception:
                    vectors.append([0.0] * 1024)  # Fallback с правильной размерностью
        return vectors

    def _search_semantic(self, query: str, k: int = 5) -> List[Article]:
        # Пытаемся выполнить семантический поиск; при ошибке возвращаем пусто
        try:
            # Используем query_texts вместо query_embeddings, чтобы ChromaDB сам генерировал эмбеддинги
            res = self.collection.query(query_texts=[query], n_results=k)
        except Exception as e:
            print(f"Semantic search error: {e}")
            return []
        ids = [int(i) for i in (res.get("ids", [[]])[0])] if res and res.get("ids") else []
        results: List[Article] = []
        for id_ in ids:
            art = self.db_service.get_article(id_)
            if art:
                results.append(art)
        return results

    def _generate_with_ollama(self, prompt: str) -> str:
        # Сохранено для обратной совместимости; сейчас генерация идёт через Mistral
        import requests
        
        # Пробуем разные адреса Ollama
        ollama_urls = [
            f"{settings.ollama_host}:{settings.ollama_port}",
            "http://localhost:11434",
            "http://host.docker.internal:11434"
        ]
        
        payload = {
            "model": settings.ollama_model,
            "prompt": prompt,
            "stream": False
        }
        
        for url in ollama_urls:
            try:
                resp = requests.post(f"{url}/api/generate", json=payload, timeout=120)
                resp.raise_for_status()
                data = resp.json()
                return data.get("response", "")
            except:
                continue
        
        raise Exception("Не удается подключиться к Ollama ни по одному из адресов")
