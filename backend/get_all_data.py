"""
Получение всех данных из текущей базы данных (SQLite или PostgreSQL)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from models.database import (
    User, Article, Category, Tag, ChatMessage, Document, DocumentChunk
)
import json

# Используем рабочее подключение из models
from models import engine, SessionLocal

def get_all_data():
    """Получение всех данных из базы"""
    print("\n" + "="*60)
    print("ПОЛУЧЕНИЕ ДАННЫХ ИЗ БАЗЫ ДАННЫХ")
    print("="*60)
    
    db = SessionLocal()
    
    try:
        # Определяем тип БД
        db_url = str(engine.url)
        db_type = "SQLite" if "sqlite" in db_url.lower() else "PostgreSQL"
        print(f"\nТип БД: {db_type}")
        print(f"URL: {db_url.split('@')[1] if '@' in db_url else db_url}")
        
        # Получаем данные из всех таблиц
        data_summary = {}
        
        # Users
        users = db.query(User).all()
        data_summary['users'] = {
            'count': len(users),
            'data': [{'id': u.id, 'email': u.email, 'name': u.full_name, 'role': u.role, 'active': u.is_active} for u in users]
        }
        
        # Articles
        articles = db.query(Article).all()
        data_summary['articles'] = {
            'count': len(articles),
            'data': [{'id': a.id, 'title': a.title[:50] + '...' if len(a.title) > 50 else a.title, 'url': a.url} for a in articles]
        }
        
        # Categories
        categories = db.query(Category).all()
        data_summary['categories'] = {
            'count': len(categories),
            'data': [{'id': c.id, 'name': c.name} for c in categories]
        }
        
        # Tags
        tags = db.query(Tag).all()
        data_summary['tags'] = {
            'count': len(tags),
            'data': [{'id': t.id, 'name': t.name} for t in tags]
        }
        
        # Chat Messages
        messages = db.query(ChatMessage).all()
        data_summary['chat_messages'] = {
            'count': len(messages),
            'data': [{'id': m.id, 'user_id': m.user_id, 'message': m.message[:50] + '...' if len(m.message) > 50 else m.message} for m in messages]
        }
        
        # Documents
        documents = db.query(Document).all()
        data_summary['documents'] = {
            'count': len(documents),
            'data': [{'id': d.id, 'filename': d.filename, 'status': d.processing_status, 'title': d.title[:30] + '...' if d.title and len(d.title) > 30 else d.title} for d in documents]
        }
        
        # Document Chunks
        chunks = db.query(DocumentChunk).all()
        data_summary['document_chunks'] = {
            'count': len(chunks),
            'data': [{'id': c.id, 'document_id': c.document_id, 'chunk_index': c.chunk_index} for c in chunks[:10]]
        }
        
        # Выводим результаты
        print("\n📊 РЕЗУЛЬТАТЫ:")
        print("="*60)
        
        total = 0
        for table_name, info in data_summary.items():
            count = info['count']
            total += count
            status = "✅" if count > 0 else "⚠️"
            print(f"\n{status} {table_name}: {count} записей")
            
            if count > 0 and info['data']:
                print("   Примеры записей:")
                for item in info['data'][:3]:
                    print(f"      {item}")
                if count > 3:
                    print(f"      ... и еще {count - 3} записей")
        
        print("\n" + "="*60)
        print(f"📈 ВСЕГО ЗАПИСЕЙ: {total}")
        print("="*60)
        
        if total > 0:
            print("\n✅ Данные успешно получены!")
            
            # Сохраняем в JSON
            output_file = "database_data_export.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data_summary, f, ensure_ascii=False, indent=2, default=str)
            print(f"💾 Данные сохранены в {output_file}")
        else:
            print("\n⚠️ База данных пуста")
        
        db.close()
        return data_summary
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        db.close()
        return None


if __name__ == "__main__":
    get_all_data()

