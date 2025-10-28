from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import json

from models import get_db
from models.schemas import ImportPreview, ImportRequest, ImportResult
from services.import_service import ImportService
from app.api.auth import require_admin

router = APIRouter(prefix="/api/import", tags=["import"])


@router.post("/analyze", response_model=ImportPreview)
async def analyze_json_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: object = Depends(require_admin)
):
    """Анализирует загруженный JSON файл и возвращает превью для импорта"""
    if not file.filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="Файл должен быть в формате JSON")
    
    try:
        # Читаем содержимое файла
        content = await file.read()
        json_data = json.loads(content.decode('utf-8'))
        
        if not isinstance(json_data, list):
            raise HTTPException(status_code=400, detail="JSON должен содержать массив объектов")
        
        # Анализируем данные
        import_service = ImportService(db)
        preview = import_service.analyze_json_data(json_data)
        
        return preview
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Неверный формат JSON")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при анализе файла: {str(e)}")


@router.post("/articles", response_model=ImportResult)
async def import_articles(
    import_request: ImportRequest,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin)
):
    """Импортирует статьи с заданными сопоставлениями полей"""
    try:
        import_service = ImportService(db)
        result = import_service.import_articles(import_request)
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при импорте: {str(e)}")


@router.post("/analyze-data", response_model=ImportPreview)
async def analyze_json_data(
    json_data: List[dict],
    db: Session = Depends(get_db),
    _: object = Depends(require_admin)
):
    """Анализирует переданные JSON данные"""
    try:
        import_service = ImportService(db)
        preview = import_service.analyze_json_data(json_data)
        
        return preview
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при анализе данных: {str(e)}")
