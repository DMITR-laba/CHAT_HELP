from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Table, Boolean, LargeBinary
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from models import Base

# Пользователи
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    role = Column(String(50), default="user")  # user | admin
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# Связующие таблицы для many-to-many отношений
article_categories = Table(
    'article_categories',
    Base.metadata,
    Column('article_id', Integer, ForeignKey('articles.id'), primary_key=True),
    Column('category_id', Integer, ForeignKey('categories.id'), primary_key=True)
)

article_tags = Table(
    'article_tags',
    Base.metadata,
    Column('article_id', Integer, ForeignKey('articles.id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id'), primary_key=True)
)


class Article(Base):
    __tablename__ = "articles"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(1024), nullable=False, index=True)
    text = Column(Text, nullable=False)
    url = Column(String(1024), nullable=True)
    language = Column(String(10), default="ru")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Связи
    categories = relationship("Category", secondary=article_categories, back_populates="articles")
    tags = relationship("Tag", secondary=article_tags, back_populates="articles")


class Category(Base):
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Связи
    articles = relationship("Article", secondary=article_categories, back_populates="categories")


class Tag(Base):
    __tablename__ = "tags"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Связи
    articles = relationship("Article", secondary=article_tags, back_populates="tags")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100), nullable=False, index=True)
    message = Column(Text, nullable=False)
    response = Column(Text, nullable=True)
    feedback = Column(Integer, nullable=True)  # 1 - полезно, -1 - неполезно
    feedback_comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Связанные статьи (для RAG)
    related_article_ids = Column(Text, nullable=True)  # JSON строка с ID статей


# Связующие таблицы для документов
document_categories = Table(
    'document_categories',
    Base.metadata,
    Column('document_id', Integer, ForeignKey('documents.id'), primary_key=True),
    Column('category_id', Integer, ForeignKey('categories.id'), primary_key=True)
)

document_tags = Table(
    'document_tags',
    Base.metadata,
    Column('document_id', Integer, ForeignKey('documents.id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id'), primary_key=True)
)


class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    file_type = Column(String(10), nullable=False)  # pdf, doc, docx, txt
    file_size = Column(Integer, nullable=False)
    file_content = Column(LargeBinary, nullable=True)  # Бинарные данные файла
    
    # Обработанный контент
    title = Column(String(1024), nullable=True, index=True)
    extracted_text = Column(Text, nullable=True)
    topic = Column(String(255), nullable=True, index=True)  # Сгенерированная тема
    summary = Column(Text, nullable=True)
    path = Column(String(512), nullable=True)  # Путь к файлу для контекста
    
    # Метаданные
    language = Column(String(10), default="ru")
    processing_status = Column(String(20), default="pending")  # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)
    
    # Временные метки
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Связи
    categories = relationship("Category", secondary=document_categories, back_populates="documents")
    tags = relationship("Tag", secondary=document_tags, back_populates="documents")


# Обновляем связи для Category и Tag
Category.documents = relationship("Document", secondary=document_categories, back_populates="categories")
Tag.documents = relationship("Document", secondary=document_tags, back_populates="tags")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)  # Порядковый номер чанка
    text = Column(Text, nullable=False)  # Текст чанка
    embedding = Column(Text, nullable=True)  # JSON с эмбеддингом
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Связь с документом
    document = relationship("Document", back_populates="chunks")


# Добавляем связь с чанками в модель Document
Document.chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
