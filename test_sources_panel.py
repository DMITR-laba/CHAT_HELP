#!/usr/bin/env python3
"""
Тестовый скрипт для проверки панели источников в чате
"""

import requests
import json
import time

API_BASE = "http://localhost:8000"

def test_chat_with_sources():
    """Тестируем чат с источниками"""
    
    # Тестовые запросы, которые должны найти статьи в БД
    test_queries = [
        "Не могу вставить строку в Excel",
        "Ошибка PICT_USER", 
        "Инструкция по настройке новой площадки в МТ",
        "Выгрузка в Диадок не работает",
        "Как установить фикс в МТ",
        "AutoCAD не отображает диалоги",
        "СБП настройка",
        "Ошибка 0x80040610"
    ]
    
    print("🧪 Тестирование панели источников...")
    print("=" * 50)
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n📝 Тест {i}: {query}")
        
        try:
            # Отправляем запрос в чат
            response = requests.post(
                f"{API_BASE}/api/chat/message",
                json={
                    "message": query,
                    "user_id": "test-user"
                },
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Ответ получен: {len(data.get('response', ''))} символов")
                
                # Проверяем наличие источников
                related_articles = data.get('related_articles', [])
                print(f"📚 Найдено источников: {len(related_articles)}")
                
                if related_articles:
                    print("   Источники:")
                    for j, article in enumerate(related_articles[:3], 1):  # Показываем первые 3
                        title = article.get('title', 'Без заголовка')[:50]
                        url = article.get('url', 'Без URL')
                        print(f"   {j}. {title}... ({url})")
                else:
                    print("   ⚠️ Источники не найдены")
                    
            else:
                print(f"❌ Ошибка: {response.status_code}")
                print(f"   Ответ: {response.text}")
                
        except Exception as e:
            print(f"❌ Исключение: {e}")
        
        time.sleep(1)  # Пауза между запросами
    
    print("\n" + "=" * 50)
    print("🏁 Тестирование завершено!")

def test_admin_endpoints():
    """Тестируем админские эндпоинты"""
    
    print("\n🔧 Тестирование админских эндпоинтов...")
    print("=" * 50)
    
    try:
        # Проверяем статьи
        response = requests.get(f"{API_BASE}/api/admin/articles?skip=0&limit=10")
        if response.status_code == 200:
            data = response.json()
            articles = data.get('articles', [])
            print(f"📄 Найдено статей в БД: {len(articles)}")
            
            if articles:
                print("   Примеры статей:")
                for article in articles[:3]:
                    title = article.get('title', 'Без заголовка')[:50]
                    tags = [tag.get('name', '') for tag in article.get('tags', [])]
                    categories = [cat.get('name', '') for cat in article.get('categories', [])]
                    print(f"   - {title}... (теги: {', '.join(tags)}, категории: {', '.join(categories)})")
        else:
            print(f"❌ Ошибка получения статей: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Исключение при тестировании админки: {e}")

if __name__ == "__main__":
    print("🚀 Запуск тестов панели источников")
    print("Убедитесь, что backend запущен на localhost:8000")
    print("Убедитесь, что frontend запущен на localhost:3000")
    print()
    
    # Проверяем доступность API
    try:
        response = requests.get(f"{API_BASE}/docs", timeout=5)
        print("✅ Backend доступен")
    except:
        print("❌ Backend недоступен! Запустите: cd backend && python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload")
        exit(1)
    
    # Запускаем тесты
    test_admin_endpoints()
    test_chat_with_sources()
    
    print("\n🌐 Откройте http://localhost:3000 в браузере")
    print("📝 Попробуйте задать вопросы из тестов выше")
    print("👆 Кликните на мини-бар источников для открытия панели")

