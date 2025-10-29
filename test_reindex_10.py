#!/usr/bin/env python3

from services.rag_service import RAGService
from services.database_service import DatabaseService
from models import get_db

def test_reindex_10():
    db = next(get_db())
    db_service = DatabaseService(db)
    rag = RAGService(db_service)
    
    print('Testing reindex with 10 articles...')
    articles, total = db_service.get_articles(skip=0, limit=10)
    print(f'Articles: {total}')
    
    batch_size = 10
    batch_articles = articles[0:batch_size]
    ids = [str(a.id) for a in batch_articles]
    documents = [(a.title or '') + '\n\n' + (a.text or '') for a in batch_articles]
    metadatas = [{'url': a.url or '', 'language': a.language or 'ru', 'title': a.title} for a in batch_articles]
    
    embeddings = rag._embed_mistral_batch(documents)
    print(f'Embeddings: {len(embeddings)}, dimensions: {[len(r) for r in embeddings]}')
    
    valid_embeddings = []
    for j, emb in enumerate(embeddings):
        if len(emb) == 1024:
            valid_embeddings.append(emb)
        else:
            print(f"Warning: Article {ids[j]} has invalid embedding dimension {len(emb)}, using fallback")
            valid_embeddings.append([0.0] * 1024)
    
    print(f'Valid embeddings: {len(valid_embeddings)}, dimensions: {[len(r) for r in valid_embeddings]}')
    
    rag.collection.add(ids=ids, documents=documents, metadatas=metadatas, embeddings=valid_embeddings)
    print('Success!')

if __name__ == '__main__':
    test_reindex_10()
