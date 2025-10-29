#!/usr/bin/env python3
"""
Скрипт для создания таблиц документов в базе данных
"""
import sys
from pathlib import Path

# Добавляем путь к модулям
sys.path.append(str(Path(__file__).parent))

from models import Base, engine

def migrate_database():
    """Создает таблицы для документов"""
    print("Создание таблиц для документов...")
    
    try:
        # Создаем все таблицы
        Base.metadata.create_all(bind=engine)
        print("✅ Таблицы успешно созданы!")
        print("Созданные таблицы:")
        print("- documents (основная таблица документов)")
        print("- document_categories (связь документов с категориями)")
        print("- document_tags (связь документов с тегами)")
        
    except Exception as e:
        print(f"❌ Ошибка при создании таблиц: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("=== Миграция базы данных для документов ===")
    success = migrate_database()
    
    if success:
        print("\n🎉 Миграция завершена успешно!")
        print("Теперь вы можете:")
        print("1. Загружать документы через админ-панель")
        print("2. Использовать документы в RAG поиске")
        print("3. Обрабатывать документы с помощью AI")
    else:
        print("\n💥 Миграция завершилась с ошибкой!")
        sys.exit(1)







