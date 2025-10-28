from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime


# Базовые схемы
class ArticleBase(BaseModel):
    title: str
    text: str
    url: Optional[str] = None
    language: str = "ru"


class ArticleCreate(ArticleBase):
    category_ids: List[int] = []
    tag_names: List[str] = []


class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    text: Optional[str] = None
    url: Optional[str] = None
    language: Optional[str] = None
    category_ids: Optional[List[int]] = None
    tag_names: Optional[List[str]] = None


class CategoryOut(BaseModel):
    id: int
    name: str
    
    class Config:
        from_attributes = True


class TagOut(BaseModel):
    id: int
    name: str
    
    class Config:
        from_attributes = True


class Article(ArticleBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    categories: List[CategoryOut] = []
    tags: List[TagOut] = []
    
    class Config:
        from_attributes = True


# Схемы для импорта статей
class ImportFieldMapping(BaseModel):
    json_field: str
    db_field: str
    required: bool = False


class ImportPreview(BaseModel):
    total_records: int
    sample_records: List[dict]
    available_fields: List[str]
    required_fields: List[str]
    field_mappings: List[ImportFieldMapping]


class ImportRequest(BaseModel):
    json_data: List[dict]
    field_mappings: List[ImportFieldMapping]
    default_language: str = "ru"


class ImportResult(BaseModel):
    success_count: int
    error_count: int
    errors: List[str]
    imported_ids: List[int]


class CategoryBase(BaseModel):
    name: str
    description: Optional[str] = None


class CategoryCreate(CategoryBase):
    pass


class Category(CategoryBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class TagBase(BaseModel):
    name: str


class TagCreate(TagBase):
    pass


class Tag(TagBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# Схемы для чата
class ChatMessageRequest(BaseModel):
    message: str
    user_id: str


class ChatMessageResponse(BaseModel):
    response: str
    related_articles: List[Article] = []
    related_documents: List['Document'] = []
    model_info: Dict[str, str] = {}
    message_id: int


class FeedbackRequest(BaseModel):
    message_id: int
    feedback: int  # 1 - полезно, -1 - неполезно
    comment: Optional[str] = None


# Схемы для админки
class ArticleListResponse(BaseModel):
    articles: List[Article]
    total: int
    page: int
    size: int


class ArticleImportRequest(BaseModel):
    mode: str  # "add", "update", "replace"
    data: List[ArticleCreate]


# Схемы для документов
class DocumentBase(BaseModel):
    original_filename: str
    file_type: str
    language: str = "ru"
    path: Optional[str] = None


class DocumentCreate(DocumentBase):
    category_ids: List[int] = []
    tag_names: List[str] = []


class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    topic: Optional[str] = None
    summary: Optional[str] = None
    path: Optional[str] = None
    category_ids: Optional[List[int]] = None
    tag_names: Optional[List[str]] = None


class Document(DocumentBase):
    id: int
    filename: str
    file_size: int
    title: Optional[str] = None
    extracted_text: Optional[str] = None
    topic: Optional[str] = None
    summary: Optional[str] = None
    processing_status: str
    error_message: Optional[str] = None
    uploaded_at: datetime
    processed_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    categories: List[CategoryOut] = []
    tags: List[TagOut] = []
    
    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    documents: List[Document]
    total: int
    page: int
    size: int


class DocumentUploadResponse(BaseModel):
    document_id: int
    message: str
    processing_status: str


# Обновляем forward references
Article.model_rebuild()
Category.model_rebuild()
Tag.model_rebuild()
Document.model_rebuild()


# Пользователи / аутентификация
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    sub: Optional[str] = None
    role: Optional[str] = None


class UserBase(BaseModel):
    email: str
    full_name: Optional[str] = None
    role: str = "user"
    is_active: bool = True


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# Схемы для чанков документов
class DocumentChunkBase(BaseModel):
    chunk_index: int
    text: str
    embedding: Optional[str] = None


class DocumentChunkCreate(DocumentChunkBase):
    document_id: int


class DocumentChunkUpdate(BaseModel):
    text: Optional[str] = None
    embedding: Optional[str] = None


class DocumentChunk(DocumentChunkBase):
    id: int
    document_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentChunkListResponse(BaseModel):
    chunks: List[DocumentChunk]
    total: int

# AI API Schemas
class AIConnectionTest(BaseModel):
    service: str
    key: str

class AIModelSettings(BaseModel):
    response_model: str
    embedding_model: str
    api_service: Optional[str] = None
    api_key: Optional[str] = None

class OllamaModel(BaseModel):
    name: str
    size: Optional[str] = None
    modified_at: Optional[str] = None
