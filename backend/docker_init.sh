#!/bin/bash
# Скрипт инициализации для Docker контейнера

echo "========================================="
echo "Инициализация базы данных и данных"
echo "========================================="

# Ждем готовности PostgreSQL
echo "Ожидание готовности PostgreSQL..."
max_retries=30
retry=0
while [ $retry -lt $max_retries ]; do
  if python -c "from sqlalchemy import create_engine, text; from app.core.config import settings; engine = create_engine(settings.database_url); engine.connect().execute(text('SELECT 1'))" 2>/dev/null; then
    echo "✅ PostgreSQL готов"
    break
  fi
  retry=$((retry+1))
  echo "   Попытка $retry/$max_retries..."
  sleep 2
done

if [ $retry -eq $max_retries ]; then
  echo "⚠️ PostgreSQL не готов, но продолжаем..."
fi

# Создаем админа (пароль по умолчанию: admin)
echo ""
echo "Создание администратора..."
ADMIN_PASSWORD=admin python create_admin.py || echo "⚠️ Ошибка создания админа (возможно уже существует)"

# Импортируем статьи
echo ""
echo "Импорт статей из articles.json..."
if [ -f "/app/../articles.json" ]; then
  python import_articles_to_db.py || echo "⚠️ Ошибка импорта статей"
elif [ -f "/app/articles.json" ]; then
  python import_articles_to_db.py || echo "⚠️ Ошибка импорта статей"
else
  echo "⚠️ Файл articles.json не найден"
fi

# Индексируем статьи в Elasticsearch (ожидаем готовности ES)
echo ""
echo "Ожидание готовности Elasticsearch..."
max_es_retries=30
es_retry=0
while [ $es_retry -lt $max_es_retries ]; do
  if python -c "from elasticsearch import Elasticsearch; es = Elasticsearch(['http://elasticsearch:9200'], request_timeout=2, headers={'Accept': 'application/vnd.elasticsearch+json; compatible-with=8'}); es.info()" 2>/dev/null; then
    echo "✅ Elasticsearch готов"
    break
  fi
  es_retry=$((es_retry+1))
  if [ $((es_retry % 5)) -eq 0 ]; then
    echo "   Попытка $es_retry/$max_es_retries..."
  fi
  sleep 2
done

if [ $es_retry -lt $max_es_retries ]; then
  echo ""
  echo "Индексация статей в Elasticsearch..."
  ELASTICSEARCH_HOST=elasticsearch python index_articles_to_elasticsearch.py || echo "⚠️ Ошибка индексации в Elasticsearch (может быть агент не создан)"
  
  echo ""
  echo "Активация Elasticsearch агента..."
  ELASTICSEARCH_HOST=elasticsearch python activate_elasticsearch_agent.py || echo "⚠️ Ошибка активации агента (может быть уже активирован)"
fi

echo ""
echo "========================================="
echo "Инициализация завершена!"
echo "========================================="

