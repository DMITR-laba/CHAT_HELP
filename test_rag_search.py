#!/usr/bin/env python3

from services.rag_service import RAGService
from services.database_service import DatabaseService
from models import get_db

def test_rag_search():
    db = next(get_db())
    db_service = DatabaseService(db)
    rag = RAGService(db_service)
    
    print('Testing semantic search...')
    results = rag._search_semantic('AutoCAD', 3)
    print(f'Semantic search results: {len(results)}')
    for r in results:
        print(f'ID: {r.id}, Title: {r.title[:50]}...')
    
    print('\nTesting text search...')
    text_results = db_service.search_articles_for_rag('AutoCAD', limit=3)
    print(f'Text search results: {len(text_results)}')
    for r in text_results:
        print(f'ID: {r.id}, Title: {r.title[:50]}...')
    
    print('\nTesting meta search...')
    meta_results = rag._search_by_meta('AutoCAD', limit=3)
    print(f'Meta search results: {len(meta_results)}')
    for r in meta_results:
        print(f'ID: {r.id}, Title: {r.title[:50]}...')

if __name__ == '__main__':
    test_rag_search()
