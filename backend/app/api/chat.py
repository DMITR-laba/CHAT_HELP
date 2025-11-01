from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models import get_db
from models.schemas import ChatMessageRequest, ChatMessageResponse, FeedbackRequest
from services.database_service import DatabaseService
from services.rag_service import RAGService
from services.elasticsearch_agent_service import ElasticSearchAgentService
import redis
import json
from app.core.config import settings
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Безопасный fallback для Redis (in-memory), если сервер Redis недоступен
class _MemoryRedis:
    def __init__(self):
        self._kv: dict[str, str] = {}
        self._lists: dict[str, list[str]] = {}

    def get(self, key: str):
        return self._kv.get(key)

    def set(self, key: str, value: str):
        self._kv[key] = str(value)
        return True

    def rpush(self, key: str, value: str):
        self._lists.setdefault(key, []).append(value)
        return True

    def lrange(self, key: str, start: int, end: int):
        lst = self._lists.get(key, [])
        # Redis lrange end inclusive; -1 means end of list
        if end == -1:
            end = len(lst) - 1
        return lst[start:end+1]


def _init_redis_client():
    try:
        client = redis.Redis(host=settings.redis_host, port=settings.redis_port, db=settings.redis_db, decode_responses=True)
        # Ленивая проверка соединения
        client.ping()
        return client
    except Exception:
        return _MemoryRedis()


redis_client = _init_redis_client()


def _session_key(user_id: str, session_id: int) -> str:
    return f"chat:history:{user_id}:{session_id}"


def _current_session_id(user_id: str) -> int:
    cur = redis_client.get(f"chat:current:{user_id}")
    if cur is None:
        # инициализируем первую сессию
        redis_client.set(f"chat:current:{user_id}", 1)
        redis_client.rpush(f"chat:sessions:{user_id}", 1)
        return 1
    return int(cur)


def _start_new_session(user_id: str) -> int:
    cur = _current_session_id(user_id)
    new_id = cur + 1
    redis_client.set(f"chat:current:{user_id}", new_id)
    redis_client.rpush(f"chat:sessions:{user_id}", new_id)
    return new_id


@router.post("/message", response_model=ChatMessageResponse)
async def send_message(
    request: ChatMessageRequest,
    db: Session = Depends(get_db)
):
    """
    Отправляет сообщение в чат и получает ответ от AI
    Если use_elasticsearch=True, сначала ищет релевантные статьи через Elasticsearch агента
    """
    try:
        db_service = DatabaseService(db)
        
        # Проверяем, нужно ли использовать Elasticsearch агента
        es_context = ""
        es_articles = []
        
        # Используем значение из запроса, если указано
        use_elasticsearch = request.use_elasticsearch
        
        if use_elasticsearch is None:
            # Проверяем сохраненные настройки
            try:
                from app.api.elasticsearch_api import get_es_agent_settings
                settings = get_es_agent_settings()
                use_elasticsearch = settings.get("enabled", False)
            except:
                # Fallback: проверяем статус агента по умолчанию
                agent = ElasticSearchAgentService.get_agent()
                use_elasticsearch = agent is not None
        
        if use_elasticsearch:
            try:
                agent = ElasticSearchAgentService.get_agent()
                if not agent:
                    logger.info("Elasticsearch агент не активирован, пытаемся создать автоматически...")
                    # Пытаемся создать агента автоматически
                    try:
                        from app.core.config import settings
                        import os
                        # В Docker используем имя сервиса elasticsearch, локально - localhost
                        default_host = 'elasticsearch' if os.getenv('POSTGRES_HOST') == 'postgres' else 'localhost'
                        es_host = os.getenv('ELASTICSEARCH_HOST', default_host)
                        es_port = int(os.getenv('ELASTICSEARCH_PORT', getattr(settings, 'elasticsearch_port', 9200)))
                        
                        # Формируем URL для Elasticsearch
                        if es_host.startswith('http://') or es_host.startswith('https://'):
                            es_url = es_host
                        else:
                            es_url = f"http://{es_host}"
                        
                        logger.info(f"Автоматическое создание агента: {es_url}:{es_port}")
                        agent = ElasticSearchAgentService.create_agent(
                            "bert_spacy",
                            es_host=es_url,
                            es_port=es_port,
                            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
                        )
                        ElasticSearchAgentService.set_active_agent("bert_spacy")
                        
                        # Сохраняем настройки
                        from app.api.elasticsearch_api import _es_agent_settings
                        _es_agent_settings.update({
                            "enabled": True,
                            "agent_type": "bert_spacy",
                            "model_name": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                            "es_host": es_url,
                            "es_port": es_port
                        })
                        
                        logger.info("✅ Elasticsearch агент успешно создан и активирован автоматически")
                    except Exception as create_error:
                        logger.error(f"Не удалось автоматически создать агента: {create_error}", exc_info=True)
                        # Продолжаем без Elasticsearch контекста
                        agent = None
                
                if agent:
                    # Выполняем поиск по статьям
                    logger.info(f"Выполняем поиск в Elasticsearch для запроса: {request.message[:50]}...")
                    search_results = agent.search(
                        query=request.message,
                        index="articles",
                        size=5
                    )
                    logger.info(f"Найдено результатов: {len(search_results) if search_results else 0}")
                    
                    # Формируем контекст из найденных статей
                    if search_results:
                        es_context = "\n\nРелевантные статьи из базы знаний:\n"
                        article_ids = []
                        
                        for idx, result in enumerate(search_results, 1):
                            data = result.get('data', {})
                            title = data.get('title', '')
                            text = data.get('text', '')
                            if text:
                                text = text[:500]  # Ограничиваем длину для контекста
                            article_id = data.get('article_id')
                            
                            if title:
                                es_context += f"\n{idx}. {title}\n"
                            if text:
                                es_context += f"{text}\n"
                            
                            if article_id:
                                article_ids.append(article_id)
                        
                        # Загружаем полные данные статей из БД для корректной структуры ответа
                        if article_ids:
                            from models.database import Article
                            from models.schemas import Article as ArticleSchema
                            
                            articles = db.query(Article).filter(Article.id.in_(article_ids)).all()
                            # Создаем словарь для быстрого доступа
                            articles_dict = {article.id: article for article in articles}
                            
                            # Формируем список статей в правильном порядке
                            for article_id in article_ids:
                                if article_id in articles_dict:
                                    article = articles_dict[article_id]
                                    # Преобразуем ORM объект в Pydantic схему
                                    article_schema = ArticleSchema.model_validate(article)
                                    es_articles.append(article_schema)
            except Exception as e:
                logger.error(f"Ошибка при поиске через Elasticsearch: {e}", exc_info=True)
                # Продолжаем без Elasticsearch контекста
        
        # Формируем финальное сообщение с контекстом от Elasticsearch
        message_with_context = request.message
        if es_context:
            message_with_context = f"{request.message}\n\n{es_context}"
        
        rag_service = RAGService(db_service)
        result = await rag_service.generate_response(message_with_context, request.user_id)
        
        # Добавляем статьи от Elasticsearch к результатам
        if es_articles:
            result_articles = result.get("related_articles", [])
            # Объединяем и убираем дубликаты
            # result_articles может содержать словари или Pydantic объекты
            existing_ids = {a.get("id") if isinstance(a, dict) else a.id for a in result_articles}
            for es_article in es_articles:
                article_id = es_article.id if hasattr(es_article, 'id') else es_article.get("id") if isinstance(es_article, dict) else None
                if article_id and article_id not in existing_ids:
                    # Преобразуем Pydantic объект в dict если нужно
                    if hasattr(es_article, 'model_dump'):
                        result_articles.append(es_article.model_dump())
                    else:
                        result_articles.append(es_article)
                    existing_ids.add(article_id)
            result["related_articles"] = result_articles
        # Сохраняем историю в Redis (по сессиям)
        sid = _current_session_id(request.user_id)
        history_key = _session_key(request.user_id, sid)
        redis_client.rpush(history_key, json.dumps({
            "q": request.message,
            "a": result["response"],
            "ts": __import__("time").time()
        }))
        
        return ChatMessageResponse(
            response=result["response"],
            related_articles=result.get("related_articles", []),
            related_documents=result.get("related_documents", []),
            model_info=result.get("model_info", {}),
            message_id=result["message_id"]
        )
    
    except Exception as e:
        # Логируем полную ошибку для отладки
        logger.error(f"Критическая ошибка при обработке сообщения: {e}", exc_info=True)
        logger.error(f"Запрос: message={request.message}, use_elasticsearch={request.use_elasticsearch}")
        
        # Мягкий фолбэк: не роняем 500, возвращаем вежливый ответ и сохраняем сообщение
        try:
            db_service = DatabaseService(db)
            fallback_text = f"Извините, произошла ошибка: {str(e)[:100]}. Попробуйте повторить запрос позже."
            chat_message = db_service.save_chat_message(
                user_id=request.user_id,
                message=request.message,
                response=fallback_text,
                related_article_ids=[]
            )
            # Сохраняем историю в Redis
            sid = _current_session_id(request.user_id)
            history_key = _session_key(request.user_id, sid)
            redis_client.rpush(history_key, json.dumps({
                "q": request.message,
                "a": fallback_text,
                "ts": __import__("time").time()
            }))
            return ChatMessageResponse(
                response=fallback_text,
                related_articles=[],
                message_id=chat_message.id
            )
        except Exception as inner_e:
            logger.error(f"Ошибка при сохранении fallback ответа: {inner_e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Критическая ошибка: {str(e)[:200]}")


@router.post("/feedback")
async def submit_feedback(
    request: FeedbackRequest,
    db: Session = Depends(get_db)
):
    """
    Отправляет обратную связь по ответу AI
    """
    try:
        db_service = DatabaseService(db)
        success = db_service.update_feedback(
            message_id=request.message_id,
            feedback=request.feedback,
            comment=request.comment
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Сообщение не найдено")
        
        return {"message": "Обратная связь сохранена"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при сохранении обратной связи: {str(e)}")


@router.get("/history")
async def get_history(user_id: str, session_id: int | None = None):
    """Возвращает историю сообщений текущей или указанной сессии, а также список всех сессий"""
    sid = session_id or _current_session_id(user_id)
    items = redis_client.lrange(_session_key(user_id, sid), 0, -1)
    sessions = [int(x) for x in redis_client.lrange(f"chat:sessions:{user_id}", 0, -1)]
    return {"history": [json.loads(i) for i in items], "current_session": sid, "sessions": sessions}


@router.post("/new_chat")
async def new_chat(user_id: str):
    """Начинает НОВЫЙ чат и сохраняет старые. Возвращает session_id."""
    sid = _start_new_session(user_id)
    return {"ok": True, "session_id": sid}

