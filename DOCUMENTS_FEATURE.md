# Функциональность работы с документами

## 🎯 Обзор

Добавлена новая функциональность для загрузки и обработки документов в админ-панели. Система поддерживает автоматическое извлечение текста, генерацию тем, тегов и кратких содержаний с помощью AI.

## 📁 Поддерживаемые форматы

- **PDF** - документы Adobe PDF
- **DOC** - документы Microsoft Word (старый формат)
- **DOCX** - документы Microsoft Word (новый формат)
- **TXT** - текстовые файлы

## 🚀 Возможности

### Загрузка документов
- Загрузка файлов до 50MB
- Автоматическое определение типа файла
- Выбор языка документа (русский/английский)
- Привязка к категориям и тегам

### Автоматическая обработка
- **Извлечение текста** из документов
- **Генерация темы** документа с помощью Mistral AI
- **Создание тегов** на основе содержания
- **Краткое содержание** документа
- **Статус обработки** (pending, processing, completed, failed)

### Поиск и RAG
- Документы интегрированы в RAG систему
- Семантический поиск по содержимому
- Поиск по темам и тегам
- Использование в ответах AI

## 🛠 Технические детали

### База данных
```sql
-- Таблица документов
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_type VARCHAR(10) NOT NULL,
    file_size INTEGER NOT NULL,
    file_content BYTEA,
    title VARCHAR(1024),
    extracted_text TEXT,
    topic VARCHAR(255),
    summary TEXT,
    language VARCHAR(10) DEFAULT 'ru',
    processing_status VARCHAR(20) DEFAULT 'pending',
    error_message TEXT,
    uploaded_at TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Связи с категориями и тегами
CREATE TABLE document_categories (
    document_id INTEGER REFERENCES documents(id),
    category_id INTEGER REFERENCES categories(id),
    PRIMARY KEY (document_id, category_id)
);

CREATE TABLE document_tags (
    document_id INTEGER REFERENCES documents(id),
    tag_id INTEGER REFERENCES tags(id),
    PRIMARY KEY (document_id, tag_id)
);
```

### API Эндпоинты

#### Загрузка документа
```http
POST /api/documents/upload
Content-Type: multipart/form-data

file: [файл]
language: ru
category_ids: [1,2,3]
tag_names: ["тег1", "тег2"]
```

#### Получение списка документов
```http
GET /api/documents/?skip=0&limit=100&search=поиск
```

#### Обработка документа
```http
POST /api/documents/{id}/process
```

#### Скачивание документа
```http
GET /api/documents/{id}/download
```

#### Просмотр текста
```http
GET /api/documents/{id}/text
```

### Обработка файлов

#### PDF файлы
```python
import PyPDF2
pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
text = ""
for page in pdf_reader.pages:
    text += page.extract_text() + "\n"
```

#### DOC/DOCX файлы
```python
import docx
doc = docx.Document(io.BytesIO(file_content))
text = ""
for paragraph in doc.paragraphs:
    text += paragraph.text + "\n"
```

#### TXT файлы
```python
text = file_content.decode('utf-8', errors='ignore')
```

## 🎨 Интерфейс

### Админ-панель
- **Табы** для переключения между статьями и документами
- **Таблица документов** с информацией о статусе
- **Модальное окно** для загрузки документов
- **Действия**: просмотр, обработка, скачивание, удаление

### Статусы документов
- 🟡 **pending** - ожидает обработки
- 🟠 **processing** - в процессе обработки
- 🟢 **completed** - успешно обработан
- 🔴 **failed** - ошибка обработки

## 🔧 Установка и настройка

### 1. Установка зависимостей
```bash
pip install PyPDF2==3.0.1 python-docx==0.8.11
```

### 2. Миграция базы данных
```bash
cd backend
python migrate_documents.py
```

### 3. Запуск системы
```bash
python run_project.py
```

## 📊 Использование

### Загрузка документа
1. Откройте админ-панель
2. Перейдите на вкладку "Документы"
3. Нажмите "Загрузить документ"
4. Выберите файл и настройки
5. Нажмите "Загрузить"

### Просмотр результатов
- **Тема** - автоматически сгенерированная тема документа
- **Теги** - ключевые слова из содержимого
- **Краткое содержание** - резюме документа
- **Полный текст** - извлеченный текст

### Интеграция с RAG
Документы автоматически включаются в поиск:
- По содержимому текста
- По теме документа
- По тегам
- По краткому содержанию

## 🚨 Ограничения

- Максимальный размер файла: 50MB
- Поддерживаемые форматы: PDF, DOC, DOCX, TXT
- Обработка может занять время для больших файлов
- Требуется подключение к Mistral AI для генерации метаданных

## 🔍 Отладка

### Проверка статуса обработки
```python
# В админ-панели или через API
GET /api/documents/{id}/text
```

### Логи обработки
Ошибки обработки сохраняются в поле `error_message` таблицы документов.

### Ручная обработка
```python
# Через API
POST /api/documents/{id}/process
```

## 🎯 Будущие улучшения

- [ ] Поддержка больше форматов (RTF, ODT)
- [ ] Пакетная загрузка файлов
- [ ] Улучшенная обработка изображений в PDF
- [ ] Кеширование результатов обработки
- [ ] Асинхронная обработка в фоне
- [ ] Версионирование документов
- [ ] Полнотекстовый поиск по содержимому

## 📝 Примеры использования

### Загрузка технической документации
1. Загрузите PDF с инструкциями
2. Система автоматически извлечет текст
3. Сгенерирует тему "Техническая документация"
4. Создаст теги: "инструкция", "настройка", "установка"
5. Документ станет доступен для поиска в чате

### Обработка корпоративных документов
1. Загрузите DOCX с политиками компании
2. Система определит тему "Корпоративная политика"
3. Создаст релевантные теги
4. Документ будет использоваться в ответах AI

---

**Версия**: 1.0.0  
**Дата**: 2024  
**Автор**: AI Assistant



