# 🚀 Инструкция по установке и настройке AI-Портала техподдержки

## 📋 Содержание
1. [Предварительные требования](#предварительные-требования)
2. [Установка Docker](#установка-docker)
3. [Клонирование проекта](#клонирование-проекта)
4. [Настройка окружения](#настройка-окружения)
5. [Запуск системы](#запуск-системы)
6. [Создание администратора](#создание-администратора)
7. [Проверка работы](#проверка-работы)
8. [Управление пользователями](#управление-пользователями)
9. [Импорт данных](#импорт-данных)
10. [Устранение неполадок](#устранение-неполадок)

---

## 🔧 Предварительные требования

### Системные требования:
- **ОС**: Windows 10/11, macOS, или Linux
- **RAM**: минимум 4GB (рекомендуется 8GB+)
- **Диск**: минимум 10GB свободного места
- **Процессор**: x64 архитектура

### Необходимое ПО:
- **Docker Desktop** (обязательно)
- **Git** (для клонирования репозитория)
- **Текстовый редактор** (VS Code, Notepad++, и т.д.)

---

## 🐳 Установка Docker

### Windows:
1. Скачайте Docker Desktop с [официального сайта](https://www.docker.com/products/docker-desktop/)
2. Запустите установщик `Docker Desktop Installer.exe`
3. Следуйте инструкциям установщика
4. Перезагрузите компьютер
5. Запустите Docker Desktop
6. Дождитесь полной загрузки (иконка в трее станет зеленой)

### macOS:
1. Скачайте Docker Desktop для Mac с [официального сайта](https://www.docker.com/products/docker-desktop/)
2. Перетащите Docker.app в папку Applications
3. Запустите Docker Desktop
4. Следуйте инструкциям настройки

### Linux (Ubuntu/Debian):
```bash
# Обновляем пакеты
sudo apt update

# Устанавливаем зависимости
sudo apt install apt-transport-https ca-certificates curl gnupg lsb-release

# Добавляем официальный GPG ключ Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Добавляем репозиторий Docker
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Устанавливаем Docker
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Добавляем пользователя в группу docker
sudo usermod -aG docker $USER

# Перезагружаемся для применения изменений
sudo reboot
```

---

## 📁 Клонирование проекта

### Через Git:
```bash
# Клонируем репозиторий
git clone <URL_РЕПОЗИТОРИЯ> chat-assistant
cd chat-assistant
```

### Через архив:
1. Скачайте архив проекта
2. Распакуйте в папку `chat-assistant`
3. Откройте терминал в этой папке

---

## ⚙️ Настройка окружения

### 1. Создание файла конфигурации:
Создайте файл `.env` в корневой папке проекта:

```bash
# Скопируйте пример конфигурации
cp env.example .env
```

### 2. Редактирование .env файла:
Откройте файл `.env` и настройте параметры:

```ini
# Настройки PostgreSQL
POSTGRES_DB=vectordb
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
POSTGRES_PORT=5432
POSTGRES_HOST=postgres

# Настройки FastAPI
API_HOST=0.0.0.0
API_PORT=8000
SECRET_KEY=your-secret-key-here-change-this
DEBUG=True

# Mistral AI (обязательно для работы AI)
MISTRAL_API_KEY=your-mistral-api-key-here
MISTRAL_MODEL=mistral-large-latest
MISTRAL_BASE_URL=https://api.mistral.ai
MISTRAL_EMBED_MODEL=mistral-embed

# Настройки Ollama (опционально)
OLLAMA_HOST=http://host.docker.internal
OLLAMA_PORT=11434
OLLAMA_MODEL=llama3:8b

# Настройки аутентификации
KEYCLOAK_URL=http://localhost:8080
KEYCLOAK_REALM=your-realm
KEYCLOAK_CLIENT_ID=your-client-id
```

### 3. Получение API ключа Mistral:
1. Зарегистрируйтесь на [Mistral AI](https://console.mistral.ai/)
2. Создайте API ключ
3. Скопируйте ключ в поле `MISTRAL_API_KEY`

---

## 🚀 Запуск системы

### 1. Сборка и запуск контейнеров:
```bash
# Собираем и запускаем все сервисы
docker-compose up -d --build
```

### 2. Проверка статуса:
```bash
# Проверяем, что все контейнеры запущены
docker-compose ps
```

Должны быть запущены:
- `chat-assistant-postgres-1` (База данных)
- `chat-assistant-backend-1` (API сервер)
- `chat-assistant-frontend-1` (Веб-интерфейс)

### 3. Просмотр логов:
```bash
# Логи всех сервисов
docker-compose logs

# Логи конкретного сервиса
docker-compose logs backend
docker-compose logs frontend
docker-compose logs postgres
```

---

## 👤 Создание администратора

### Автоматическое создание:
Система автоматически создает администратора при первом запуске.

**Данные для входа:**
- **Email**: `admin@example.com`
- **Пароль**: `admin`

### Ручное создание (если нужно):
```bash
# Создаем администратора через API
curl -X POST http://localhost:8000/api/auth/bootstrap-admin
```

### Проверка создания:
```bash
# Проверяем, что админ создан
curl -X POST http://localhost:8000/api/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=admin"
```

---

## ✅ Проверка работы

### 1. Веб-интерфейс:
Откройте браузер и перейдите по адресу:
```
http://localhost:3000
```

### 2. API сервер:
Проверьте API по адресу:
```
http://localhost:8000/docs
```

### 3. База данных:
```bash
# Подключаемся к базе данных
docker-compose exec postgres psql -U postgres -d vectordb

# Проверяем таблицы
\dt

# Выходим
\q
```

---

## 👥 Управление пользователями

### Через веб-интерфейс:
1. Войдите в систему как администратор
2. Нажмите на кнопку настроек (⚙️) в правом верхнем углу
3. Перейдите на вкладку **"Пользователи"**
4. Используйте кнопку **"Создать пользователя"** для добавления новых пользователей

### Через API:
```bash
# Получение списка пользователей
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/auth/users

# Создание нового пользователя
curl -X POST http://localhost:8000/api/auth/users \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "full_name": "Пользователь",
    "password": "password123",
    "role": "user"
  }'
```

---

## 📊 Импорт данных

### Импорт статей:
1. Откройте админ панель
2. Перейдите на вкладку **"Статьи"**
3. Нажмите **"Импорт JSON"**
4. Загрузите JSON файл со статьями
5. Настройте сопоставление полей
6. Запустите импорт

### Импорт документов:
1. Перейдите на вкладку **"Документы"**
2. Нажмите **"Загрузить документ"**
3. Выберите файл (PDF, DOC, DOCX, TXT)
4. Укажите метаданные
5. Загрузите документ

---

## 🔧 Устранение неполадок

### Проблема: Контейнеры не запускаются
```bash
# Проверяем логи
docker-compose logs

# Перезапускаем все сервисы
docker-compose down
docker-compose up -d --build
```

### Проблема: База данных недоступна
```bash
# Проверяем статус PostgreSQL
docker-compose exec postgres pg_isready -U postgres

# Перезапускаем только базу данных
docker-compose restart postgres
```

### Проблема: Frontend не загружается
```bash
# Проверяем статус frontend
docker-compose logs frontend

# Пересобираем frontend
docker-compose build frontend
docker-compose up -d frontend
```

### Проблема: API не отвечает
```bash
# Проверяем статус backend
docker-compose logs backend

# Перезапускаем backend
docker-compose restart backend
```

### Проблема: Ошибки авторизации
1. Проверьте правильность данных для входа
2. Убедитесь, что администратор создан:
```bash
curl -X POST http://localhost:8000/api/auth/bootstrap-admin
```

### Проблема: Ошибки с AI
1. Проверьте правильность API ключа Mistral
2. Убедитесь, что ключ активен
3. Проверьте баланс на аккаунте Mistral

---

## 📞 Поддержка

### Полезные команды:
```bash
# Остановка всех сервисов
docker-compose down

# Остановка с удалением данных
docker-compose down -v

# Просмотр использования ресурсов
docker stats

# Очистка неиспользуемых образов
docker system prune -a
```

### Логи и отладка:
```bash
# Подробные логи
docker-compose logs -f

# Логи конкретного сервиса
docker-compose logs -f backend

# Вход в контейнер для отладки
docker-compose exec backend bash
docker-compose exec postgres psql -U postgres -d vectordb
```

---

## 🎯 Следующие шаги

После успешной установки:

1. **Смените пароль администратора** через веб-интерфейс
2. **Создайте дополнительных пользователей** при необходимости
3. **Импортируйте ваши данные** (статьи, документы)
4. **Настройте AI модели** в разделе AI
5. **Протестируйте функциональность** чата

---

## 📝 Примечания

- **Первый запуск** может занять несколько минут из-за загрузки зависимостей
- **База данных** сохраняется в Docker volume, данные не теряются при перезапуске
- **API ключи** храните в безопасности и не публикуйте в открытом доступе
- **Регулярно обновляйте** систему для получения новых функций и исправлений

---

**🎉 Поздравляем! Система AI-Портала техподдержки успешно установлена и готова к работе!**
