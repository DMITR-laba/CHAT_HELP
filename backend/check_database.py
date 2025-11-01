"""
Скрипт для проверки наличия данных в базе данных
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from models.database import (
    User, Article, Category, Tag, ChatMessage, Document, DocumentChunk
)
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_database():
    """Проверка данных в базе данных"""
    print("\n" + "="*60)
    print("ПРОВЕРКА ДАННЫХ В БАЗЕ ДАННЫХ")
    print("="*60)
    
    # Подключение к базе данных
    try:
        db_url = settings.database_url
        print(f"\nПодключение к БД: {db_url.split('@')[1] if '@' in db_url else db_url}")
        
        engine = create_engine(db_url)
        
        # Проверяем подключение
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            if result.fetchone():
                print("✅ Подключение к базе данных успешно")
        
        # Проверяем наличие таблиц и создаем их при необходимости
        from models import Base
        print("Проверка наличия таблиц...")
        try:
            # Пробуем выполнить запрос к таблице users
            with engine.connect() as conn:
                conn.execute(text("SELECT COUNT(*) FROM users LIMIT 1"))
            print("✅ Таблицы существуют")
        except Exception:
            print("⚠️ Таблицы не найдены. Создаю таблицы...")
            Base.metadata.create_all(bind=engine)
            print("✅ Таблицы созданы успешно")
        
        print()
        
        # Создаем сессию
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
        
        # Проверяем каждую таблицу
        tables_info = []
        
        # Users
        users_count = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()
        admins = db.query(User).filter(User.role == 'admin').count()
        tables_info.append({
            'table': 'users',
            'count': users_count,
            'details': f'Активных: {active_users}, Админов: {admins}'
        })
        
        # Articles
        articles_count = db.query(Article).count()
        tables_info.append({
            'table': 'articles',
            'count': articles_count,
            'details': None
        })
        
        # Categories
        categories_count = db.query(Category).count()
        tables_info.append({
            'table': 'categories',
            'count': categories_count,
            'details': None
        })
        
        # Tags
        tags_count = db.query(Tag).count()
        tables_info.append({
            'table': 'tags',
            'count': tags_count,
            'details': None
        })
        
        # Chat Messages
        messages_count = db.query(ChatMessage).count()
        messages_with_feedback = db.query(ChatMessage).filter(ChatMessage.feedback != None).count()
        tables_info.append({
            'table': 'chat_messages',
            'count': messages_count,
            'details': f'С обратной связью: {messages_with_feedback}'
        })
        
        # Documents
        documents_count = db.query(Document).count()
        processed_docs = db.query(Document).filter(Document.processing_status == 'completed').count()
        pending_docs = db.query(Document).filter(Document.processing_status == 'pending').count()
        tables_info.append({
            'table': 'documents',
            'count': documents_count,
            'details': f'Обработано: {processed_docs}, В ожидании: {pending_docs}'
        })
        
        # Document Chunks
        chunks_count = db.query(DocumentChunk).count()
        chunks_with_embedding = db.query(DocumentChunk).filter(DocumentChunk.embedding != None).count()
        tables_info.append({
            'table': 'document_chunks',
            'count': chunks_count,
            'details': f'С эмбеддингами: {chunks_with_embedding}'
        })
        
        # Выводим результаты
        print("📊 СТАТИСТИКА ПО ТАБЛИЦАМ:")
        print("-" * 60)
        total_records = 0
        
        for info in tables_info:
            status = "✅" if info['count'] > 0 else "⚠️"
            print(f"{status} {info['table']:20} : {info['count']:5} записей", end="")
            if info['details']:
                print(f" ({info['details']})")
            else:
                print()
            total_records += info['count']
        
        print("-" * 60)
        print(f"📈 Всего записей в базе данных: {total_records}")
        print()
        
        # Детальная информация по некоторым таблицам
        if articles_count > 0:
            print("\n📄 ПРИМЕРЫ СТАТЕЙ:")
            print("-" * 60)
            articles = db.query(Article).limit(5).all()
            for article in articles:
                print(f"  ID: {article.id}, Заголовок: {article.title[:50]}...")
                print(f"    Категории: {len(article.categories)}, Теги: {len(article.tags)}")
        
        if documents_count > 0:
            print("\n📁 ПРИМЕРЫ ДОКУМЕНТОВ:")
            print("-" * 60)
            documents = db.query(Document).limit(5).all()
            for doc in documents:
                print(f"  ID: {doc.id}, Файл: {doc.filename}")
                print(f"    Статус: {doc.processing_status}, Чанков: {len(doc.chunks)}")
        
        if messages_count > 0:
            print("\n💬 ПОСЛЕДНИЕ СООБЩЕНИЯ:")
            print("-" * 60)
            messages = db.query(ChatMessage).order_by(ChatMessage.created_at.desc()).limit(5).all()
            for msg in messages:
                print(f"  ID: {msg.id}, Пользователь: {msg.user_id}")
                print(f"    Сообщение: {msg.message[:50]}...")
                print(f"    Обратная связь: {'✅' if msg.feedback else '❌'}")
        
        # Проверяем связи
        print("\n🔗 ПРОВЕРКА СВЯЗЕЙ:")
        print("-" * 60)
        
        if articles_count > 0:
            articles_with_categories = db.query(Article).join(Article.categories).distinct().count()
            articles_with_tags = db.query(Article).join(Article.tags).distinct().count()
            print(f"  Статей с категориями: {articles_with_categories}/{articles_count}")
            print(f"  Статей с тегами: {articles_with_tags}/{articles_count}")
        
        if documents_count > 0:
            documents_with_categories = db.query(Document).join(Document.categories).distinct().count()
            documents_with_tags = db.query(Document).join(Document.tags).distinct().count()
            print(f"  Документов с категориями: {documents_with_categories}/{documents_count}")
            print(f"  Документов с тегами: {documents_with_tags}/{documents_count}")
        
        db.close()
        
        print("\n" + "="*60)
        if total_records > 0:
            print("✅ В базе данных есть данные")
        else:
            print("⚠️ База данных пуста. Необходимо добавить данные.")
        print("="*60)
        
        return total_records > 0
        
    except Exception as e:
        print(f"\n❌ Ошибка при подключении к базе данных: {e}")
        logger.exception("Детали ошибки:")
        return False


if __name__ == "__main__":
    try:
        check_database()
    except KeyboardInterrupt:
        print("\n\n⚠️ Проверка прервана")
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {e}")
        logger.exception("Детали ошибки:")

