#!/usr/bin/env python3
"""
Скрипт для тестирования подключения к PostgreSQL базе данных
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import engine, Base
from sqlalchemy.exc import OperationalError
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_connection():
    """Тестирует подключение к базе данных"""
    try:
        with engine.connect() as connection:
            result = connection.execute("SELECT version()")
            version = result.fetchone()[0]
            logger.info(f"Подключение к PostgreSQL успешно! Версия: {version}")
            
            # Проверяем существование таблиц
            result = connection.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            tables = [row[0] for row in result.fetchall()]
            logger.info(f"Найденные таблицы: {tables}")
            
            return True
            
    except OperationalError as e:
        logger.error(f"Ошибка подключения к базе данных: {e}")
        return False
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        return False

def create_tables():
    """Создает все таблицы"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Все таблицы созданы успешно!")
        return True
    except Exception as e:
        logger.error(f"Ошибка при создании таблиц: {e}")
        return False

if __name__ == "__main__":
    logger.info("Тестирование подключения к базе данных...")
    
    if test_connection():
        logger.info("Создание таблиц...")
        if create_tables():
            logger.info("Тест завершен успешно!")
            sys.exit(0)
        else:
            logger.error("Ошибка при создании таблиц")
            sys.exit(1)
    else:
        logger.error("Не удалось подключиться к базе данных")
        sys.exit(1)

