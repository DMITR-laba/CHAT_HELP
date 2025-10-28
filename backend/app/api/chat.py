from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models import get_db
from models.schemas import ChatMessageRequest, ChatMessageResponse, FeedbackRequest
from services.database_service import DatabaseService
from services.rag_service import RAGService
import redis
import json
from app.core.config import settings

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
    """
    try:
        db_service = DatabaseService(db)
        rag_service = RAGService(db_service)
        
        result = await rag_service.generate_response(request.message, request.user_id)
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
        # Мягкий фолбэк: не роняем 500, возвращаем вежливый ответ и сохраняем сообщение
        try:
            db_service = DatabaseService(db)
            fallback_text = "Извините, сервис временно недоступен. Попробуйте повторить запрос позже."
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
        except Exception:
            raise HTTPException(status_code=200, detail="Извините, сервис временно недоступен. Попробуйте повторить запрос позже.")


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

