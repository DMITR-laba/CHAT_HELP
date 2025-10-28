#!/usr/bin/env python3
"""
Локальный тест без API:
- Проверяет наличие статей, при отсутствии добавляет несколько тестовых
- Переиндексирует Chroma (эмбеддинги Mistral)
- Запускает список запросов и печатает ответы и найденные статьи
"""
import os
import sys
from typing import List


def main() -> None:
    # Используем локальную SQLite в каталоге backend
    os.environ.setdefault("DATABASE_URL_ENV", "sqlite:///./local.db")

    # Локальные импорты после установки переменных окружения
    from models import SessionLocal, Base, engine
    from services.database_service import DatabaseService
    from services.rag_service import RAGService
    from models.schemas import ArticleCreate

    # Инициализируем БД
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    dsvc = DatabaseService(db)

    # Если статей нет — добавим минимальный набор, соответствующий вашим вопросам
    articles, total = dsvc.get_articles(skip=0, limit=5)
    if total == 0:
        seed: List[ArticleCreate] = [
            ArticleCreate(
                title="Excel: Не могу вставить строку — что делать",
                text=(
                    "В Excel ошибка при вставке строк может возникать из-за включённых фильтров, слияния ячеек "
                    "или форматов таблицы. Решение: 1) Очистить фильтры; 2) Проверить объединённые ячейки; "
                    "3) Преобразовать таблицу в диапазон; 4) Проверить, хватает ли свободного места на листе."
                ),
                url="",
                language="ru",
                category_ids=[],
                tag_names=["EXCEL", "ВСТАВКА СТРОКИ", "ФИЛЬТР", "ОБЪЕДИНЁННЫЕ ЯЧЕЙКИ"],
            ),
            ArticleCreate(
                title="Ошибка PICT_USER в приложении",
                text=(
                    "Ошибка PICT_USER возникает при отсутствии прав на каталог кэша изображений или при битом "
                    "профиле. Проверьте права пользователя, почистите кэш в %AppData%, перезапустите приложение."
                ),
                url="",
                language="ru",
                category_ids=[],
                tag_names=["PICT_USER", "ПРАВА", "КЭШ"],
            ),
            ArticleCreate(
                title="МТ: Инструкция по настройке новой площадки",
                text=(
                    "Для настройки новой площадки в МТ: создать площадку в админке, привязать кассы, указать "
                    "параметры ОФД и ЭДО, проверить доступы операторов. Перезапустить сервисы синхронизации."
                ),
                url="",
                language="ru",
                category_ids=[],
                tag_names=["МТ", "ПЛОЩАДКА", "НАСТРОЙКА", "ОФД", "ЭДО"],
            ),
            ArticleCreate(
                title="Диадок: Выгрузка не работает",
                text=(
                    "Если выгрузка в Диадок не работает: проверьте токен интеграции, доступы организации, "
                    "сетевые ограничения, очередь задач. Повторите попытку после обновления токена."
                ),
                url="",
                language="ru",
                category_ids=[],
                tag_names=["ДИАДОК", "ВЫГРУЗКА", "ТОКЕН", "ИНТЕГРАЦИЯ"],
            ),
            ArticleCreate(
                title="МТ: Как установить фикс",
                text=(
                    "Для установки фикса в МТ: получить архив фикса, сделать бэкап, остановить сервисы, "
                    "распаковать файлы в каталог приложения, запустить миграции БД при необходимости, "
                    "перезапустить сервисы и выполнить smoke-тест."
                ),
                url="",
                language="ru",
                category_ids=[],
                tag_names=["МТ", "ФИКС", "ОБНОВЛЕНИЕ", "МИГРАЦИИ"],
            ),
        ]

        for a in seed:
            dsvc.create_article(a)

    # Переиндексация
    rag = RAGService(dsvc)
    try:
        idx = rag.reindex_articles()
        print(f"Переиндексация: {idx}")
    except Exception as e:
        print(f"Переиндексация не выполнена: {e}")

    # Тестовые запросы
    queries = [
        "Не могу вставить строку в Excel",
        "Ошибка PICT_USER",
        "Инструкция по настройке новой площадки в МТ",
        "Выгрузка в Диадок не работает",
        "Как установить фикс в МТ",
    ]

    for q in queries:
        print("\n=== ВОПРОС ===")
        print(q)
        res = rag.generate_response(q, user_id="local-test-user")
        print("--- ОТВЕТ ---")
        print(res.get("response", ""))
        arts = res.get("related_articles", []) or []
        if arts:
            print("--- РЕЛЕВАНТНЫЕ СТАТЬИ ---")
            for a in arts:
                # a может быть ORM-объектом; безопасно достанем поля
                title = getattr(a, "title", "")
                aid = getattr(a, "id", None)
                print(f"[{aid}] {title[:100]}{'...' if title and len(title) > 100 else ''}")

    db.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Ошибка локального теста: {exc}")
        sys.exit(1)



