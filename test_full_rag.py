#!/usr/bin/env python3

from services.rag_service import RAGService
from services.database_service import DatabaseService
from models import get_db

def test_full_rag():
    db = next(get_db())
    db_service = DatabaseService(db)
    rag = RAGService(db_service)
    
    print('Testing full RAG process...')
    result = rag.generate_response('Как исправить проблему с AutoCAD?', 'test-user')
    
    print(f'Response: {result["response"][:500]}...')
    print(f'Related articles count: {len(result["related_articles"])}')
    for article in result["related_articles"]:
        print(f'  - ID: {article.id}, Title: {article.title[:50]}...')

if __name__ == '__main__':
    test_full_rag()
