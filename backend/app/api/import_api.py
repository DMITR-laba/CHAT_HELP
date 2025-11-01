"""
API endpoints для импорта статей из JSON
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
import httpx
import json

from models import get_db
from models.database import Article
from models.schemas import ImportRequest, ImportFieldMapping
from services.database_service import DatabaseService
from services.import_service import ImportService

router = APIRouter(prefix="/api/import", tags=["import"])


class FieldMapping(BaseModel):
    json_field: str
    db_field: str
    required: bool = False
    
    class Config:
        extra = "allow"


class ImportAnalyzeRequest(BaseModel):
    total_records: int
    sample_records: Optional[List[Dict[str, Any]]] = None
    records: Optional[List[Dict[str, Any]]] = None  # Все записи для импорта
    available_fields: List[str] = []
    required_fields: List[str] = []
    field_mappings: List[FieldMapping] = []
    source_api_url: Optional[str] = None  # URL API для получения всех записей
    
    class Config:
        extra = "allow"  # Разрешаем дополнительные поля для гибкости


@router.post("/analyze")
async def analyze_import(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Анализирует файл JSON и возвращает структуру данных для настройки маппинга полей
    НЕ импортирует данные - только анализирует структуру
    
    Поддерживает два формата:
    1. JSON body (application/json)
    2. Multipart form-data с файлом (multipart/form-data)
    
    Возвращает структуру с:
    - total_records: общее количество записей
    - sample_records: примеры записей для отображения
    - available_fields: доступные поля в данных
    - field_mappings: предложенный маппинг полей
    """
    content_type = request.headers.get("content-type", "")
    
    # Если данные приходят как multipart/form-data
    if "multipart/form-data" in content_type:
        try:
            form = await request.form()
            file_data = None
            
            # Ищем файл в форме
            file = form.get("file")
            if file and hasattr(file, 'read'):
                # Читаем содержимое файла
                content = await file.read()
                # Декодируем содержимое файла
                if isinstance(content, bytes):
                    content_str = content.decode('utf-8')
                else:
                    content_str = content
                
                # Парсим JSON из файла
                file_data = json.loads(content_str)
            else:
                # Если файла нет, ищем поле с данными JSON
                # Проверяем различные возможные имена полей
                for field_name in ["data", "json", "json_data", "file"]:
                    json_data = form.get(field_name)
                    if json_data:
                        # Если это UploadFile, читаем его содержимое
                        if hasattr(json_data, 'read'):
                            content = await json_data.read()
                            if isinstance(content, bytes):
                                content_str = content.decode('utf-8')
                            else:
                                content_str = content
                            file_data = json.loads(content_str)
                        # Если это строка, парсим её напрямую
                        elif isinstance(json_data, str):
                            file_data = json.loads(json_data)
                        break
                
                if not file_data:
                    raise HTTPException(
                        status_code=400,
                        detail="В multipart/form-data необходимо указать поле 'file' с JSON файлом или поле 'data'/'json' с JSON строкой"
                    )
            
            # Создаём объект запроса из данных файла
            # Проверяем тип данных после парсинга
            if isinstance(file_data, list):
                # Если данные пришли как список, это может быть массив записей
                # Обернем их в словарь с ключом "records"
                file_data = {"records": file_data, "total_records": len(file_data)}
            elif not isinstance(file_data, dict):
                raise HTTPException(
                    status_code=400,
                    detail=f"Неожиданный тип данных после парсинга JSON: {type(file_data).__name__}. Ожидается объект или массив."
                )
            
            data = ImportAnalyzeRequest(**file_data)
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Ошибка при парсинге JSON: {str(e)}"
            )
        except TypeError as e:
            # Если ошибка связана с типами данных, выдаем более информативное сообщение
            raise HTTPException(
                status_code=400,
                detail=f"Ошибка типа данных: {str(e)}. Убедитесь, что JSON содержит объект с полями: total_records, records/sample_records, field_mappings и т.д."
            )
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Ошибка при обработке multipart/form-data: {str(e)}"
            )
    # Если данные приходят как JSON body
    else:
        try:
            body = await request.json()
            # Проверяем тип данных
            if isinstance(body, list):
                # Если данные пришли как список, обернем их в словарь
                body = {"records": body, "total_records": len(body)}
            elif not isinstance(body, dict):
                raise HTTPException(
                    status_code=400,
                    detail=f"Неожиданный тип данных: {type(body).__name__}. Ожидается объект или массив."
                )
            
            data = ImportAnalyzeRequest(**body)
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Ошибка при парсинге JSON: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Ошибка при обработке данных: {str(e)}"
            )
    
    # Определяем все записи для анализа
    all_records = []
    
    # Если есть поле 'records' со всеми записями, используем его
    if data.records:
        all_records = data.records
    # Если есть только sample_records, используем его
    elif data.sample_records:
        all_records = data.sample_records
    else:
        raise HTTPException(
            status_code=400,
            detail="Не найдены записи для анализа. Укажите поле 'records' или 'sample_records'"
        )
    
    # Проверяем, что есть хотя бы одна запись
    if not all_records:
        raise HTTPException(
            status_code=400,
            detail="Список записей пуст"
        )
    
    # Определяем доступные поля из первой записи или из available_fields
    if data.available_fields:
        available_fields = data.available_fields
    elif all_records and isinstance(all_records[0], dict):
        available_fields = list(all_records[0].keys())
    else:
        available_fields = []
    
    # Если field_mappings не указан или пуст, создаём автоматический маппинг
    if not data.field_mappings:
        if available_fields:
            # Создаём простой маппинг: название поля -> название поля
            data.field_mappings = [
                FieldMapping(
                    json_field=field,
                    db_field=field,
                    required=field in data.required_fields if data.required_fields else False
                )
                for field in available_fields
            ]
        else:
            raise HTTPException(
                status_code=400,
                detail="Не удалось определить доступные поля. Укажите available_fields или field_mappings в запросе."
            )
    
    # Определяем общее количество записей
    actual_total = data.total_records if data.total_records else len(all_records)
    
    # Возвращаем структуру для анализа (БЕЗ импорта)
    response_data = {
        "total_records": actual_total,
        "sample_records": all_records[:10] if len(all_records) > 10 else all_records,  # Показываем только первые 10 для примера
        "records": all_records,  # Сохраняем все записи для последующего импорта
        "available_fields": available_fields,
        "field_mappings": [
            {
                "json_field": m.json_field,
                "db_field": m.db_field,
                "required": m.required
            }
            for m in data.field_mappings
        ],
        "required_fields": data.required_fields if data.required_fields else []
    }
    
    return response_data


@router.post("/articles")
async def import_articles(
    request: ImportRequest,
    db: Session = Depends(get_db)
):
    """
    Импортирует статьи из JSON данных с указанными сопоставлениями полей
    """
    import_service = ImportService(db)
    
    try:
        result = import_service.import_articles(request)
        
        return {
            "success": True,
            "success_count": result.success_count,
            "error_count": result.error_count,
            "errors": result.errors if result.errors else [],
            "imported_ids": result.imported_ids
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при импорте статей: {str(e)}"
        )


