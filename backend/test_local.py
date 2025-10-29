import os
import json
from typing import List

os.environ["DATABASE_URL_ENV"] = os.getenv("DATABASE_URL_ENV", "sqlite:///./local.db")
os.environ["OLLAMA_HOST"] = os.getenv("OLLAMA_HOST", "http://localhost")

from models import SessionLocal, Base, engine
from models.database import Article, Tag, Category
from services.database_service import DatabaseService
from services.rag_service import RAGService
from import_articles import extract_tags_from_text, generate_tags_with_ollama


def print_header(title: str):
    print("\n===" + title + "===")


def test_tag_generation():
    print_header("TAG GENERATION")
    db = SessionLocal()
    svc = DatabaseService(db)
    # Возьмём первые 5 статей без тегов или с малым количеством
    arts: List[Article] = db.query(Article).all()[:5]
    for a in arts:
        base_text = f"{a.title}\n{a.text}"
        tags = extract_tags_from_text(base_text)
        if not tags:
            try:
                tags = generate_tags_with_ollama(a.title or "", a.text or "")
            except Exception:
                tags = []
        print(f"Article {a.id}: {a.title[:60]} -> {tags[:8]}")
    db.close()


def test_search_semantic():
    print_header("SEMANTIC SEARCH")
    db = SessionLocal()
    rsvc = RAGService(DatabaseService(db))
    # Переиндексируем минимум для теста
    stats = rsvc.reindex_articles()
    print("Reindex:", stats)
    # Запросы
    queries = [
        "AutoCAD диалоги сохранения",
        "Ошибка проводника не удалось найти этот элемент",
        "версия SQL Server узнать",
    ]
    for q in queries:
        res = rsvc._search_semantic(q, k=3)
        print(f"\nQuery: {q}")
        for art in res:
            print(f" - [{art.id}] {art.title[:100]}")
    db.close()


def test_fulltext_fallback():
    print_header("FTS FALLBACK")
    db = SessionLocal()
    dsvc = DatabaseService(db)
    q = "СБП возврат платежа"
    res = dsvc.search_articles_for_rag(q, limit=3)
    for art in res:
        print(f" - [{art.id}] {art.title[:100]}")
    db.close()


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    test_tag_generation()
    test_search_semantic()
    test_fulltext_fallback()





