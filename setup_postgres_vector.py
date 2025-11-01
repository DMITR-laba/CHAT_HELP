#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для настройки PostgreSQL с расширением pgvector
Запускается отдельно, не требует Docker для backend
"""
import sys
import os
from pathlib import Path

# Настройка кодировки для Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent / "backend"))

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Настройки подключения (можно переопределить через переменные окружения)
POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', 5432))
POSTGRES_DB = os.getenv('POSTGRES_DB', 'vectordb')
POSTGRES_USER = os.getenv('POSTGRES_USER', 'postgres')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'password')


def setup_postgres_vector():
    """Настройка PostgreSQL с расширением pgvector"""
    print("\n" + "="*60)
    print("НАСТРОЙКА POSTGRESQL С PGVECTOR")
    print("="*60)
    
    # Формируем список URL для подключения
    hosts_to_try = [
        POSTGRES_HOST,
        "localhost",
        "127.0.0.1",
    ]
    
    database_urls = []
    for host in hosts_to_try:
        url = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{host}:{POSTGRES_PORT}/{POSTGRES_DB}"
        database_urls.append(url)
    
    engine = None
    working_url = None
    
    for url in database_urls:
        try:
            print(f"\nПопытка подключения к: {url.replace(POSTGRES_PASSWORD, '***')}")
            engine = create_engine(url, pool_pre_ping=True)
            
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            
            working_url = url
            print(f"✅ Подключение установлено!")
            break
        except OperationalError as e:
            print(f"❌ Не удалось подключиться: {e}")
            continue
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            continue
    
    if not engine or not working_url:
        print("\n❌ Не удалось подключиться к PostgreSQL!")
        print("Убедитесь, что PostgreSQL запущен и доступен.")
        print("Проверьте настройки:")
        print(f"  POSTGRES_HOST={POSTGRES_HOST}")
        print(f"  POSTGRES_PORT={POSTGRES_PORT}")
        print(f"  POSTGRES_DB={POSTGRES_DB}")
        print(f"  POSTGRES_USER={POSTGRES_USER}")
        return False
    
    print(f"\nРабочий URL: {working_url.replace(POSTGRES_PASSWORD, '***')}")
    
    try:
        # Создаем расширение vector
        print("\n📦 Создание расширения pgvector...")
        with engine.connect() as connection:
            try:
                connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                connection.commit()
                print("✅ Расширение pgvector установлено")
            except Exception as e:
                if "already exists" in str(e).lower() or "уже существует" in str(e).lower():
                    print("✅ Расширение pgvector уже установлено")
                else:
                    print(f"⚠️ Предупреждение при создании расширения: {e}")
                    # Продолжаем, если расширение уже есть
        
        # Создаем все таблицы
        print("\n📋 Создание таблиц...")
        from models import Base
        Base.metadata.create_all(bind=engine)
        print("✅ Таблицы созданы/проверены")
        
        # Проверяем расширение
        print("\n🔍 Проверка установленных расширений...")
        with engine.connect() as connection:
            result = connection.execute(text("""
                SELECT extname, extversion 
                FROM pg_extension 
                WHERE extname = 'vector'
            """))
            row = result.fetchone()
            if row:
                print(f"✅ Расширение vector версии {row[1]} установлено")
            else:
                print("⚠️ Расширение vector не найдено (но это может быть нормально)")
        
        print("\n" + "="*60)
        print("✅ Настройка PostgreSQL завершена успешно!")
        print("="*60)
        return True
        
    except Exception as e:
        print(f"\n❌ Ошибка при настройке: {e}")
        logger.exception("Детали ошибки:")
        return False


if __name__ == "__main__":
    try:
        setup_postgres_vector()
    except KeyboardInterrupt:
        print("\n\n⚠️ Настройка прервана")
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {e}")
        logger.exception("Детали ошибки:")

