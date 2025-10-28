from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from models import get_db
from models.schemas import (
    Article, ArticleCreate, ArticleUpdate, ArticleListResponse,
    Category, CategoryCreate, Tag, TagCreate, ArticleImportRequest
)
from services.database_service import DatabaseService
from services.rag_service import RAGService
from app.api.auth import require_admin
from import_articles import extract_tags_from_text, generate_tags_with_ollama, choose_category_by_keywords, generate_category_with_ollama

router = APIRouter(prefix="/api/admin", tags=["admin"])


# Статьи
@router.get("/articles", response_model=ArticleListResponse)
async def get_articles(
    skip: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=5000),
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin)
):
    """Получает список статей с пагинацией и поиском"""
    db_service = DatabaseService(db)
    articles, total = db_service.get_articles(skip=skip, limit=limit, search=search)
    
    return ArticleListResponse(
        articles=articles,
        total=total,
        page=1,
        size=limit
    )


@router.get("/articles/{article_id}", response_model=Article)
async def get_article(article_id: int, db: Session = Depends(get_db), _: object = Depends(require_admin)):
    """Получает статью по ID"""
    db_service = DatabaseService(db)
    article = db_service.get_article(article_id)
    
    if not article:
        raise HTTPException(status_code=404, detail="Статья не найдена")
    
    return article


@router.post("/articles", response_model=Article)
async def create_article(article_data: ArticleCreate, db: Session = Depends(get_db), _: object = Depends(require_admin)):
    """Создает новую статью"""
    db_service = DatabaseService(db)
    return db_service.create_article(article_data)


@router.put("/articles/{article_id}", response_model=Article)
async def update_article(
    article_id: int,
    article_data: ArticleUpdate,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin)
):
    """Обновляет статью"""
    db_service = DatabaseService(db)
    article = db_service.update_article(article_id, article_data)
    
    if not article:
        raise HTTPException(status_code=404, detail="Статья не найдена")
    
    return article


@router.delete("/articles/{article_id}")
async def delete_article(article_id: int, db: Session = Depends(get_db), _: object = Depends(require_admin)):
    """Удаляет статью"""
    db_service = DatabaseService(db)
    success = db_service.delete_article(article_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Статья не найдена")
    
    return {"message": "Статья удалена"}


# Категории
@router.get("/categories", response_model=List[Category])
async def get_categories(db: Session = Depends(get_db), _: object = Depends(require_admin)):
    """Получает список всех категорий"""
    db_service = DatabaseService(db)
    return db_service.get_categories()


@router.post("/categories", response_model=Category)
async def create_category(category_data: CategoryCreate, db: Session = Depends(get_db), _: object = Depends(require_admin)):
    """Создает новую категорию"""
    db_service = DatabaseService(db)
    return db_service.create_category(category_data)


# Теги
@router.get("/tags", response_model=List[Tag])
async def get_tags(db: Session = Depends(get_db), _: object = Depends(require_admin)):
    """Получает список всех тегов"""
    db_service = DatabaseService(db)
    return db_service.get_tags()


@router.post("/tags", response_model=Tag)
async def create_tag(tag_data: TagCreate, db: Session = Depends(get_db), _: object = Depends(require_admin)):
    """Создает новый тег"""
    db_service = DatabaseService(db)
    return db_service.create_tag(tag_data)


# Импорт и переиндексация
@router.post("/import")
async def import_articles(request: ArticleImportRequest, db: Session = Depends(get_db), _: object = Depends(require_admin)):
    """Импортирует статьи из JSON"""
    db_service = DatabaseService(db)
    
    imported_count = 0
    for article_data in request.data:
        try:
            db_service.create_article(article_data)
            imported_count += 1
        except Exception as e:
            # Логируем ошибку, но продолжаем импорт
            print(f"Ошибка при импорте статьи '{article_data.title}': {str(e)}")
    
    return {
        "message": f"Импорт завершен. Обработано {imported_count} из {len(request.data)} статей",
        "imported_count": imported_count,
        "total_count": len(request.data)
    }


@router.post("/reindex")
async def reindex_articles(db: Session = Depends(get_db), _: object = Depends(require_admin)):
    """Переиндексирует базу знаний"""
    db_service = DatabaseService(db)
    rag_service = RAGService(db_service)
    
    result = rag_service.reindex_articles()
    return result


@router.post("/articles/{article_id}/generate_meta")
async def generate_article_meta(article_id: int, db: Session = Depends(get_db), _: object = Depends(require_admin)):
    """Генерирует теги и категорию для статьи в реальном времени и сохраняет"""
    dsvc = DatabaseService(db)
    art = dsvc.get_article(article_id)
    if not art:
        raise HTTPException(status_code=404, detail="Статья не найдена")

    base_text = f"{art.title}\n{art.text}"
    # Теги
    tags = extract_tags_from_text(base_text)
    if not tags:
        try:
            tags = generate_tags_with_ollama(art.title or "", art.text or "")
        except Exception:
            tags = []
    # Сохраним теги
    from models.database import Tag
    art.tags.clear()
    for name in tags[:8]:
        tag = db.query(Tag).filter(Tag.name == name).first()
        if not tag:
            tag = Tag(name=name)
            db.add(tag)
            db.flush()
        art.tags.append(tag)

    # Категория
    cats = dsvc.get_categories()
    cat_names = [c.name for c in cats]
    chosen = choose_category_by_keywords(base_text, cat_names)
    if not chosen:
        try:
            chosen = generate_category_with_ollama(art.title or "", art.text or "", cat_names)
        except Exception:
            chosen = None
    if chosen:
        # установить одну категорию
        art.categories.clear()
        match = next((c for c in cats if c.name == chosen), None)
        if match:
            art.categories.append(match)

    db.commit()
    db.refresh(art)
    return {"ok": True, "tags": [t.name for t in art.tags], "categories": [c.name for c in art.categories]}
