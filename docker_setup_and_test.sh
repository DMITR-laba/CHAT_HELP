#!/bin/bash
# Скрипт для полной настройки и тестирования проекта в Docker

echo "========================================="
echo "ПОЛНАЯ НАСТРОЙКА И ТЕСТИРОВАНИЕ ПРОЕКТА"
echo "========================================="

# Останавливаем существующие контейнеры
echo ""
echo "1. Остановка существующих контейнеров..."
docker-compose down

# Собираем образы
echo ""
echo "2. Сборка Docker образов..."
docker-compose build

# Запускаем контейнеры
echo ""
echo "3. Запуск контейнеров..."
docker-compose up -d

# Ждем готовности сервисов
echo ""
echo "4. Ожидание готовности сервисов..."
sleep 10

# Проверяем статус
echo ""
echo "5. Статус контейнеров:"
docker-compose ps

# Ждем полной готовности
echo ""
echo "6. Ожидание полной готовности (30 секунд)..."
sleep 30

# Создаем админа
echo ""
echo "7. Создание администратора..."
docker-compose exec -T backend python create_admin.py

# Импортируем статьи
echo ""
echo "8. Импорт статей..."
docker-compose exec -T backend python import_articles_to_db.py

# Тестируем Elasticsearch агента
echo ""
echo "9. Тестирование Elasticsearch агента..."
docker-compose exec -T backend python test_elasticsearch_docker.py

echo ""
echo "========================================="
echo "НАСТРОЙКА ЗАВЕРШЕНА!"
echo "========================================="
echo ""
echo "Доступные сервисы:"
echo "  - Backend API: http://localhost:8000"
echo "  - Frontend: http://localhost:3000"
echo "  - Elasticsearch: http://localhost:9200"
echo "  - PostgreSQL: localhost:5432"
echo ""
echo "Учетные данные администратора:"
echo "  - Email: admin@example.com"
echo "  - Password: admin123"
echo ""
echo "Логи: docker-compose logs -f"
echo "Остановка: docker-compose down"

