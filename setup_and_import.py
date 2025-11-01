#!/usr/bin/env python3
"""
Комплексный скрипт для:
1. Настройки PostgreSQL с pgvector
2. Импорта статей
3. Создания администратора
"""
import sys
from pathlib import Path

# Добавляем путь к backend
sys.path.insert(0, str(Path(__file__).parent / "backend"))

import subprocess
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_script(script_name, description):
    """Запускает скрипт и выводит результаты"""
    print(f"\n{'='*60}")
    print(f"{description}")
    print(f"{'='*60}")
    
    script_path = Path(__file__).parent / script_name
    
    if not script_path.exists():
        print(f"❌ Скрипт {script_name} не найден!")
        return False
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=False,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Ошибка при запуске {script_name}: {e}")
        return False


def main():
    """Основная функция"""
    print("\n" + "="*60)
    print("НАСТРОЙКА ПРОЕКТА")
    print("="*60)
    
    # 1. Настройка PostgreSQL
    if not run_script("setup_postgres_vector.py", "Настройка PostgreSQL с pgvector"):
        print("\n⚠️ Ошибка при настройке PostgreSQL, но продолжаем...")
    
    # 2. Импорт статей
    if not run_script("backend/import_articles_to_db.py", "Импорт статей в базу данных"):
        print("\n⚠️ Ошибка при импорте статей, но продолжаем...")
    
    # 3. Создание админа
    if not run_script("backend/create_admin.py", "Создание администратора"):
        print("\n⚠️ Ошибка при создании администратора, но продолжаем...")
    
    print("\n" + "="*60)
    print("✅ Настройка завершена!")
    print("="*60)
    print("\nСледующие шаги:")
    print("1. Запустите backend: cd backend && python main.py")
    print("2. Или запустите фронтенд и проверьте работу")
    print("3. Войдите как администратор: admin@example.com / admin123")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Настройка прервана")
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {e}")
        logger.exception("Детали ошибки:")

