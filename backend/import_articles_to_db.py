"""
Скрипт для импорта статей из articles.json в базу данных
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy.orm import Session
from models import SessionLocal, engine, Base
from models.database import Article, Category, Tag
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def import_articles():
    """Импорт статей из articles.json"""
    print("\n" + "="*60)
    print("ИМПОРТ СТАТЕЙ ИЗ articles.json")
    print("="*60)
    
    # Находим файл articles.json (пробуем разные пути)
    articles_file = None
    possible_paths = [
        Path(__file__).parent / "articles.json",  # В папке backend
        Path(__file__).parent.parent / "articles.json",  # В корне проекта
        Path("/app/articles.json"),  # В Docker контейнере
    ]
    
    for path in possible_paths:
        if path.exists():
            articles_file = path
            break
    
    if not articles_file:
        print(f"❌ Файл articles.json не найден!")
        print(f"   Проверенные пути: {possible_paths}")
        return False
    
    print(f"\nЧтение файла: {articles_file}")
    
    # Читаем JSON
    try:
        with open(articles_file, 'r', encoding='utf-8') as f:
            articles_data = json.load(f)
    except Exception as e:
        print(f"❌ Ошибка чтения файла: {e}")
        return False
    
    print(f"✅ Загружено статей: {len(articles_data)}")
    
    # Создаем таблицы если их нет
    Base.metadata.create_all(bind=engine)
    
    # Создаем сессию
    db: Session = SessionLocal()
    
    try:
        imported = 0
        updated = 0
        errors = []
        
        for idx, article_data in enumerate(articles_data, 1):
            try:
                title = article_data.get('title', '')
                text = article_data.get('text', '')
                url = article_data.get('url', '')
                language = article_data.get('language', 'ru')
                
                if not title or not text:
                    errors.append(f"Статья #{idx}: отсутствует title или text")
                    continue
                
                # Проверяем, существует ли статья с таким URL
                existing_article = db.query(Article).filter(Article.url == url).first()
                
                if existing_article:
                    # Обновляем существующую
                    existing_article.title = title
                    existing_article.text = text
                    existing_article.language = language
                    updated += 1
                    print(f"  [{idx}/{len(articles_data)}] Обновлена: {title[:50]}...")
                else:
                    # Создаем новую
                    new_article = Article(
                        title=title,
                        text=text,
                        url=url,
                        language=language
                    )
                    db.add(new_article)
                    imported += 1
                    print(f"  [{idx}/{len(articles_data)}] Импортирована: {title[:50]}...")
                
                # Коммитим каждые 10 записей
                if (idx % 10) == 0:
                    db.commit()
                    
            except Exception as e:
                errors.append(f"Статья #{idx}: {str(e)}")
                logger.error(f"Ошибка при импорте статьи #{idx}: {e}")
                continue
        
        # Финальный коммит
        db.commit()
        
        print("\n" + "="*60)
        print("РЕЗУЛЬТАТЫ ИМПОРТА:")
        print("="*60)
        print(f"✅ Импортировано новых: {imported}")
        print(f"🔄 Обновлено существующих: {updated}")
        print(f"❌ Ошибок: {len(errors)}")
        
        if errors:
            print(f"\nОшибки:")
            for error in errors[:10]:  # Показываем первые 10 ошибок
                print(f"  - {error}")
            if len(errors) > 10:
                print(f"  ... и еще {len(errors) - 10} ошибок")
        
        print("\n✅ Импорт завершен!")
        return True
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Критическая ошибка: {e}")
        logger.exception("Детали ошибки:")
        return False
    finally:
        db.close()


if __name__ == "__main__":
    try:
        import_articles()
    except KeyboardInterrupt:
        print("\n\n⚠️ Импорт прерван пользователем")
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {e}")
        logger.exception("Детали ошибки:")

