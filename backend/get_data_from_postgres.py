"""
Скрипт для получения данных из PostgreSQL
Пробует подключиться к PostgreSQL и получить данные
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Параметры подключения к PostgreSQL
POSTGRES_CONFIGS = [
    {
        "host": "localhost",
        "port": 5432,
        "db": "vectordb",
        "user": "postgres",
        "password": "password"
    },
    {
        "host": "127.0.0.1",
        "port": 5432,
        "db": "vectordb",
        "user": "postgres",
        "password": "password"
    },
    {
        "host": "postgres",
        "port": 5432,
        "db": "vectordb",
        "user": "postgres",
        "password": "password"
    },
    {
        "host": "db",
        "port": 5432,
        "db": "vectordb",
        "user": "postgres",
        "password": "password"
    }
]


def try_connect_postgres():
    """Попытка подключиться к PostgreSQL"""
    print("\n" + "="*60)
    print("ПОПЫТКА ПОДКЛЮЧЕНИЯ К POSTGRESQL")
    print("="*60)
    
    connected = False
    working_config = None
    
    for i, config in enumerate(POSTGRES_CONFIGS, 1):
        url = f"postgresql://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['db']}"
        print(f"\nПопытка {i}/{len(POSTGRES_CONFIGS)}: {config['host']}:{config['port']}...")
        
        try:
            engine = create_engine(
                url, 
                pool_pre_ping=True, 
                connect_args={
                    "connect_timeout": 3,
                    "client_encoding": "utf8"
                }
            )
            with engine.connect() as conn:
                # Проверяем версию PostgreSQL
                result = conn.execute(text("SELECT version()"))
                version = result.fetchone()[0]
                
            print(f"✅ УСПЕШНО подключено!")
            print(f"   Версия: {version.split(',')[0]}")
            connected = True
            working_config = config
            working_url = url
            break
            
        except Exception as e:
            # Пробуем получить более понятное сообщение об ошибке
            error_str = repr(e) if hasattr(e, '__repr__') else str(e)
            # Убираем проблемные символы для вывода
            try:
                error_msg = error_str.encode('ascii', 'ignore').decode('ascii')
            except:
                error_msg = str(type(e).__name__)
            
            # Проверяем, есть ли реальное подключение
            if "could not translate host name" in error_str or "could not connect" in error_str.lower():
                print(f"❌ Ошибка подключения: {error_msg[:60]}...")
            else:
                # Возможно, это ошибка авторизации или другие проблемы
                print(f"⚠️ Ошибка (возможно подключение частично): {error_msg[:60]}...")
                # Пробуем еще раз с более детальным выводом
                try:
                    import psycopg2
                    conn = psycopg2.connect(
                        host=config['host'],
                        port=config['port'],
                        database=config['db'],
                        user=config['user'],
                        password=config['password'],
                        connect_timeout=3
                    )
                    print(f"   Но прямое подключение через psycopg2 работает!")
                    conn.close()
                    # Продолжаем с этим подключением
                    engine = create_engine(
                        url, 
                        pool_pre_ping=True,
                        connect_args={"client_encoding": "utf8"}
                    )
                    connected = True
                    working_config = config
                    working_url = url
                    break
                except Exception as e2:
                    continue
            continue
    
    if not connected:
        print("\n❌ Не удалось подключиться к PostgreSQL ни с одним конфигом")
        print("\n💡 Возможные причины:")
        print("   1. PostgreSQL не запущен")
        print("   2. Неправильные параметры подключения")
        print("   3. Порт 5432 не доступен")
        print("   4. Для Docker: контейнер не запущен или порт не проброшен")
        return None
    
    print(f"\n✅ Подключение установлено!")
    print(f"   Хост: {working_config['host']}")
    print(f"   Порт: {working_config['port']}")
    print(f"   База данных: {working_config['db']}")
    
    # Создаем сессию
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # Получаем список всех таблиц
        print("\n📋 ПОЛУЧЕНИЕ СПИСКА ТАБЛИЦ:")
        print("-" * 60)
        
        result = db.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """))
        tables = [row[0] for row in result.fetchall()]
        
        if not tables:
            print("⚠️ Таблицы не найдены в базе данных")
            return None
        
        print(f"Найдено таблиц: {len(tables)}")
        for table in tables:
            print(f"  - {table}")
        
        # Получаем данные из каждой таблицы
        print("\n📊 ДАННЫЕ ИЗ ТАБЛИЦ:")
        print("="*60)
        
        total_records = 0
        
        for table_name in tables:
            try:
                # Получаем количество записей
                result = db.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                count = result.fetchone()[0]
                total_records += count
                
                status = "✅" if count > 0 else "⚠️"
                print(f"\n{status} {table_name}: {count} записей")
                
                if count > 0:
                    # Получаем первые записи
                    result = db.execute(text(f"SELECT * FROM {table_name} LIMIT 3"))
                    rows = result.fetchall()
                    columns = result.keys()
                    
                    print(f"   Столбцы: {', '.join(columns)}")
                    print(f"   Примеры записей:")
                    
                    for idx, row in enumerate(rows, 1):
                        row_dict = dict(zip(columns, row))
                        # Показываем только первые несколько полей
                        preview = {}
                        for key in list(row_dict.keys())[:5]:
                            value = row_dict[key]
                            if isinstance(value, str) and len(value) > 50:
                                preview[key] = value[:50] + "..."
                            elif isinstance(value, (bytes, memoryview)):
                                preview[key] = f"<binary {len(value)} bytes>"
                            else:
                                preview[key] = value
                        
                        print(f"      {idx}. {preview}")
                        
                        if idx >= 3:
                            break
                    
                    if count > 3:
                        print(f"      ... и еще {count - 3} записей")
                        
            except Exception as e:
                print(f"   ⚠️ Ошибка при чтении таблицы {table_name}: {e}")
                continue
        
        print("\n" + "="*60)
        print(f"📈 Всего записей в базе данных: {total_records}")
        print("="*60)
        
        if total_records == 0:
            print("\n⚠️ База данных пуста")
        else:
            print("\n✅ Данные успешно получены!")
        
        db.close()
        return working_url
        
    except Exception as e:
        print(f"\n❌ Ошибка при получении данных: {e}")
        logger.exception("Детали ошибки:")
        db.close()
        return None


if __name__ == "__main__":
    try:
        url = try_connect_postgres()
        if url:
            print(f"\n💡 Для использования этого подключения добавьте в .env:")
            print(f"   DATABASE_URL_ENV={url}")
    except KeyboardInterrupt:
        print("\n\n⚠️ Прервано пользователем")
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {e}")
        logger.exception("Детали ошибки:")

