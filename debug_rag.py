#!/usr/bin/env python3

from services.rag_service import RAGService
from services.database_service import DatabaseService
from models import get_db

def debug_rag():
    db = next(get_db())
    db_service = DatabaseService(db)
    rag = RAGService(db_service)
    
    query = "AutoCAD"
    print(f'Testing query: {query}')
    
    # Тестируем каждый тип поиска отдельно
    print('\n1. Semantic search:')
    semantic_results = rag._search_semantic(query, k=5)
    print(f'Found {len(semantic_results)} articles')
    for r in semantic_results:
        print(f'  - ID: {r.id}, Title: {r.title[:50]}...')
    
    print('\n2. Text search:')
    text_results = db_service.search_articles_for_rag(query, limit=5)
    print(f'Found {len(text_results)} articles')
    for r in text_results:
        print(f'  - ID: {r.id}, Title: {r.title[:50]}...')
    
    print('\n3. Meta search:')
    meta_results = rag._search_by_meta(query, limit=5)
    print(f'Found {len(meta_results)} articles')
    for r in meta_results:
        print(f'  - ID: {r.id}, Title: {r.title[:50]}...')
    
    # Тестируем расширение запроса
    print('\n4. Query variants:')
    variants = rag._expand_query_variants(query)
    print(f'Variants: {variants}')
    
    # Тестируем гибридный поиск
    print('\n5. Hybrid search:')
    collected = {}
    for q in variants[:3]:  # Только первые 3 варианта
        print(f'  Testing variant: {q}')
        for art in rag._search_semantic(q, k=3):
            collected.setdefault(art.id, art)
            print(f'    Found: ID {art.id}, Title: {art.title[:30]}...')
        for art in db_service.search_articles_for_rag(q, limit=3):
            collected.setdefault(art.id, art)
            print(f'    Found: ID {art.id}, Title: {art.title[:30]}...')
        for art in rag._search_by_meta(q, limit=3):
            collected.setdefault(art.id, art)
            print(f'    Found: ID {art.id}, Title: {art.title[:30]}...')
    
    print(f'\nTotal collected articles: {len(collected)}')
    for art in list(collected.values())[:5]:
        print(f'  - ID: {art.id}, Title: {art.title[:50]}...')

if __name__ == '__main__':
    debug_rag()
