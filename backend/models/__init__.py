from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
import logging
from sqlalchemy.exc import OperationalError
from sqlalchemy import text

logger = logging.getLogger(__name__)


def find_working_database_url():
    """Пытается найти рабочее подключение к базе данных"""
    # Если указан прямой URL через переменную окружения, используем его
    if settings.database_url_env:
        try:
            # Для SQLite не используем connect_timeout
            if settings.database_url_env.startswith('sqlite'):
                test_engine = create_engine(settings.database_url_env, pool_pre_ping=True)
            else:
                test_engine = create_engine(settings.database_url_env, pool_pre_ping=True, 
                                           connect_args={"connect_timeout": 3})
            with test_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info(f"Подключение к БД установлено через database_url_env")
            return settings.database_url_env
        except Exception as e:
            logger.warning(f"Не удалось подключиться через database_url_env: {e}")
            # Продолжаем попытки с другими вариантами
    
    # Пробуем разные варианты хостов
    urls = settings.get_database_urls()
    
    for url in urls:
        try:
            # Для SQLite не используем connect_timeout
            if url.startswith('sqlite'):
                test_engine = create_engine(url, pool_pre_ping=True)
            else:
                test_engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 3})
            
            with test_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            safe_url = url.split('@')[1] if '@' in url else url
            logger.info(f"Подключение к БД установлено: {safe_url}")
            return url
        except Exception as e:
            safe_url = url.split('@')[1] if '@' in url else url
            logger.debug(f"Не удалось подключиться к {safe_url}: {e}")
            continue
    
    # Если ничего не сработало, возвращаем основной URL
    logger.warning("Не удалось установить подключение, используем основной URL")
    return settings.database_url


# Получаем рабочий URL для подключения
working_database_url = find_working_database_url()

# Создаем движок с дополнительными параметрами для надежности
engine = create_engine(
    working_database_url, 
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=10,
    max_overflow=20,
    echo=False  # Установите в True для отладки SQL запросов
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
