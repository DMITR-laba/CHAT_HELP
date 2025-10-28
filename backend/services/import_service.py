import json
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from models.database import Article, Category, Tag
from models.schemas import ImportPreview, ImportRequest, ImportResult, ImportFieldMapping, ArticleCreate
from services.database_service import DatabaseService


class ImportService:
    def __init__(self, db: Session):
        self.db = db
        self.db_service = DatabaseService(db)
    
    def analyze_json_data(self, json_data: List[dict]) -> ImportPreview:
        """Анализирует JSON данные и возвращает превью для импорта"""
        if not json_data:
            return ImportPreview(
                total_records=0,
                sample_records=[],
                available_fields=[],
                required_fields=['title', 'text', 'url'],
                field_mappings=[]
            )
        
        # Получаем все уникальные поля из JSON
        all_fields = set()
        for record in json_data:
            all_fields.update(record.keys())
        
        available_fields = list(all_fields)
        
        # Обязательные поля
        required_fields = ['title', 'text', 'url']
        
        # Автоматическое сопоставление полей
        field_mappings = self._auto_map_fields(available_fields)
        
        # Берем первые 3 записи как примеры
        sample_records = json_data[:3]
        
        return ImportPreview(
            total_records=len(json_data),
            sample_records=sample_records,
            available_fields=available_fields,
            required_fields=required_fields,
            field_mappings=field_mappings
        )
    
    def _auto_map_fields(self, available_fields: List[str]) -> List[ImportFieldMapping]:
        """Автоматически сопоставляет поля JSON с полями базы данных"""
        mappings = []
        
        # Словарь для автоматического сопоставления
        auto_mapping = {
            'title': ['title', 'name', 'subject', 'header', 'заголовок', 'название'],
            'text': ['text', 'content', 'body', 'description', 'текст', 'содержание', 'описание'],
            'url': ['url', 'link', 'href', 'ссылка', 'адрес'],
            'language': ['language', 'lang', 'язык', 'locale']
        }
        
        for db_field, possible_json_fields in auto_mapping.items():
            for json_field in available_fields:
                if json_field.lower() in [f.lower() for f in possible_json_fields]:
                    mappings.append(ImportFieldMapping(
                        json_field=json_field,
                        db_field=db_field,
                        required=db_field in ['title', 'text', 'url']
                    ))
                    break
        
        return mappings
    
    def import_articles(self, import_request: ImportRequest) -> ImportResult:
        """Импортирует статьи с заданными сопоставлениями полей"""
        success_count = 0
        error_count = 0
        errors = []
        imported_ids = []
        
        # Создаем словарь сопоставлений для быстрого доступа
        field_map = {mapping.json_field: mapping.db_field for mapping in import_request.field_mappings}
        
        for i, record in enumerate(import_request.json_data):
            try:
                # Преобразуем JSON запись в данные статьи
                article_data = self._convert_record_to_article(record, field_map, import_request.default_language)
                
                # Создаем статью
                article = self.db_service.create_article(article_data)
                imported_ids.append(article.id)
                success_count += 1
                
            except Exception as e:
                error_count += 1
                # Добавляем информацию о записи для лучшей диагностики
                title_preview = record.get('title', 'Без заголовка')[:50]
                errors.append(f"Запись {i+1} ('{title_preview}...'): {str(e)}")
        
        return ImportResult(
            success_count=success_count,
            error_count=error_count,
            errors=errors,
            imported_ids=imported_ids
        )
    
    def _convert_record_to_article(self, record: dict, field_map: dict, default_language: str) -> ArticleCreate:
        """Преобразует JSON запись в данные для создания статьи"""
        article_data = {}
        
        # Обрабатываем сопоставленные поля
        for json_field, db_field in field_map.items():
            if json_field in record:
                article_data[db_field] = record[json_field]
        
        # Проверяем обязательные поля
        if 'title' not in article_data or not article_data['title'] or not article_data['title'].strip():
            raise ValueError("Поле 'title' обязательно и не может быть пустым")
        
        if 'text' not in article_data or not article_data['text'] or not article_data['text'].strip():
            raise ValueError("Поле 'text' обязательно и не может быть пустым")
        
        # Обрезаем длинные поля до максимально допустимых размеров
        article_data['title'] = self._truncate_field(article_data['title'], 1000)
        if 'url' in article_data and article_data['url']:
            article_data['url'] = self._truncate_field(article_data['url'], 1000)
        
        # Устанавливаем язык по умолчанию если не указан
        if 'language' not in article_data or not article_data['language']:
            article_data['language'] = default_language
        
        # URL не обязателен, но если есть - добавляем
        if 'url' not in article_data:
            article_data['url'] = None
        
        return ArticleCreate(
            title=article_data['title'],
            text=article_data['text'],
            url=article_data.get('url'),
            language=article_data['language'],
            category_ids=[],
            tag_names=[]
        )
    
    def _truncate_field(self, value: str, max_length: int) -> str:
        """Обрезает строковое поле до максимальной длины"""
        if not value:
            return value
        
        if len(value) <= max_length:
            return value
        
        # Обрезаем и добавляем многоточие
        return value[:max_length-3] + "..."




