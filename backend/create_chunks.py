#!/usr/bin/env python3
"""
Скрипт для создания чанков для существующих документов
"""
import sys
import time
from pathlib import Path

# Добавляем путь к проекту
sys.path.append(str(Path(__file__).parent))

from models import get_db
from models.database import Document, DocumentChunk
from services.document_service import DocumentService

def show_progress(current, total, prefix="", suffix="", length=50):
    """Отображает прогресс-бар"""
    percent = ("{0:.1f}").format(100 * (current / float(total)))
    filled_length = int(length * current // total)
    bar = '█' * filled_length + '-' * (length - filled_length)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end='', flush=True)
    if current == total:
        print()

def create_chunks_for_documents():
    """Создает чанки для всех документов"""
    db = next(get_db())
    doc_service = DocumentService(db)
    
    try:
        # Получаем все документы
        documents = db.query(Document).all()
        print(f"📄 Найдено документов: {len(documents)}")
        print("=" * 60)
        
        total_documents = len(documents)
        processed_documents = 0
        total_chunks_created = 0
        
        for doc_idx, doc in enumerate(documents, 1):
            print(f"\n📋 Документ {doc_idx}/{total_documents}: {doc.original_filename}")
            print(f"   ID: {doc.id} | Статус: {doc.processing_status}")
            
            if doc.extracted_text and len(doc.extracted_text) > 0:
                text_length = len(doc.extracted_text)
                estimated_chunks = (text_length // 500) + 1
                print(f"   📝 Текст: {text_length:,} символов (~{estimated_chunks} чанков)")
                
                # Показываем прогресс создания чанков
                print("   🔄 Создание чанков...")
                start_time = time.time()
                
                # Создаем чанки с прогрессом
                chunks = doc_service.create_document_chunks(doc.id, show_progress=True)
                
                end_time = time.time()
                processing_time = end_time - start_time
                
                print(f"   ✅ Создано {len(chunks)} чанков за {processing_time:.1f}с")
                total_chunks_created += len(chunks)
                
                # Показываем прогресс для текущего документа
                if len(chunks) > 0:
                    print("   📊 Примеры чанков:")
                    for i, chunk in enumerate(chunks[:3]):
                        print(f"      Чанк {i+1}: {chunk.text[:80]}...")
                    if len(chunks) > 3:
                        print(f"      ... и еще {len(chunks) - 3} чанков")
            else:
                print("   ❌ Нет текста для обработки")
            
            # Общий прогресс
            processed_documents += 1
            show_progress(
                processed_documents, 
                total_documents, 
                "📈 Общий прогресс", 
                f"({processed_documents}/{total_documents})"
            )
        
        print(f"\n🎉 Обработка завершена!")
        print(f"📊 Статистика:")
        print(f"   • Обработано документов: {processed_documents}")
        print(f"   • Создано чанков: {total_chunks_created}")
        
        # Проверяем общее количество чанков в базе
        total_chunks_in_db = db.query(DocumentChunk).count()
        print(f"   • Всего чанков в базе: {total_chunks_in_db}")
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_chunks_for_documents()
