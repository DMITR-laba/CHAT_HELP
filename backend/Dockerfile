FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    libpq-dev \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Копирование requirements и установка Python зависимостей
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Установка моделей spaCy
RUN python -m spacy download ru_core_news_sm && \
    python -m spacy download en_core_web_sm

# Копирование кода приложения
COPY . /app

# Делаем скрипты исполняемыми
RUN chmod +x /app/docker_init.sh /app/docker-entrypoint.sh || true

EXPOSE 8000

# Используем entrypoint для инициализации
ENTRYPOINT ["/bin/bash", "/app/docker-entrypoint.sh"]



