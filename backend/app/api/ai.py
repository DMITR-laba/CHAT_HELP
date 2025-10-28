from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import httpx
import os
from datetime import datetime
from models import get_db
from models.schemas import AIConnectionTest, AIModelSettings, OllamaModel
from services.ai_service import AIService
from app.api.auth import require_admin

router = APIRouter()

@router.post("/test-connection")
async def test_connection(
    request: AIConnectionTest,
    db: Session = Depends(get_db)
):
    """Тестирование подключения к внешнему API"""
    try:
        ai_service = AIService()
        result = await ai_service.test_api_connection(request.service, request.key)
        return {"success": True, "message": "Подключение успешно", "details": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка подключения: {str(e)}")

@router.get("/ollama/models")
async def get_ollama_models(db: Session = Depends(get_db), _: object = Depends(require_admin)):
    """Получение списка моделей Ollama"""
    try:
        ai_service = AIService()
        models = await ai_service.get_ollama_models()
        return {"models": models}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка получения моделей: {str(e)}")

@router.post("/ollama/pull")
async def pull_ollama_model(
    model_name: str,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin)
):
    """Загрузка модели в Ollama"""
    try:
        ai_service = AIService()
        result = await ai_service.pull_ollama_model(model_name)
        return {"success": True, "message": f"Модель {model_name} загружается", "details": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка загрузки модели: {str(e)}")

@router.get("/ollama/status")
async def get_ollama_status(db: Session = Depends(get_db)):
    """Проверка статуса Ollama"""
    try:
        ai_service = AIService()
        status = await ai_service.check_ollama_status()
        return {"status": status}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка проверки статуса: {str(e)}")

@router.post("/settings/save")
async def save_ai_settings(
    settings: AIModelSettings,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin)
):
    """Сохранение настроек AI"""
    try:
        ai_service = AIService()
        # Преобразуем Pydantic модель в словарь
        settings_dict = {
            "response_model": settings.response_model,
            "embedding_model": settings.embedding_model,
            "api_service": settings.api_service,
            "api_key": settings.api_key,
            "updated_at": datetime.now().isoformat()
        }
        result = await ai_service.save_settings_dict(settings_dict)
        return {"success": True, "message": "Настройки сохранены", "settings": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка сохранения настроек: {str(e)}")

@router.get("/settings")
async def get_ai_settings(db: Session = Depends(get_db), _: object = Depends(require_admin)):
    """Получение текущих настроек AI"""
    try:
        ai_service = AIService()
        settings = await ai_service.get_settings()
        return {"settings": settings}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка получения настроек: {str(e)}")

@router.post("/test-model")
async def test_model(
    model_name: str,
    model_type: str,  # "response" или "embedding"
    db: Session = Depends(get_db),
    _: object = Depends(require_admin)
):
    """Тестирование конкретной модели"""
    try:
        ai_service = AIService()
        
        if model_type == "response":
            result = await ai_service.test_response_model(model_name)
        elif model_type == "embedding":
            result = await ai_service.test_embedding_model(model_name)
        else:
            raise HTTPException(status_code=400, detail="Неверный тип модели")
        
        return {"success": True, "message": f"Модель {model_name} работает корректно", "details": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка тестирования модели: {str(e)}")
