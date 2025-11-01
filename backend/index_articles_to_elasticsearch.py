"""
Скрипт для индексации статей из БД в Elasticsearch
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy.orm import Session
from models import SessionLocal
from models.database import Article
from services.elasticsearch_agent_service import BERTElasticSearchAgent, ElasticSearchAgentService
from elasticsearch import Elasticsearch
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def wait_for_elasticsearch(host="elasticsearch", port=9200, max_retries=30):
    """Ожидание готовности Elasticsearch"""
    # Если host уже содержит http://, используем как есть
    if host.startswith('http://') or host.startswith('https://'):
        es_url = host
        if ':' not in host.split('//')[1]:  # Если нет порта в URL
            es_url = f"{host}:{port}"
    else:
        es_url = f"http://{host}:{port}"
    
    for i in range(max_retries):
        try:
            es = Elasticsearch(
                [es_url], 
                request_timeout=5,
                headers={"Accept": "application/vnd.elasticsearch+json; compatible-with=8"}
            )
            info = es.info()
            logger.info(f"Elasticsearch готов: {info.get('version', {}).get('number', 'unknown')}")
            return True
        except Exception:
            if i < max_retries - 1:
                time.sleep(2)
            else:
                return False
    
    return False


def index_articles():
    """Индексация статей в Elasticsearch"""
    print("\n" + "="*60)
    print("ИНДЕКСАЦИЯ СТАТЕЙ В ELASTICSEARCH")
    print("="*60)
    
    # Проверяем наличие агента
    agent = ElasticSearchAgentService.get_agent()
    if not agent:
        print("⚠️ Elasticsearch агент не создан. Создаем BERT+spaCy агента...")
        
        # Ожидаем готовности Elasticsearch
        # В Docker используем имя сервиса, локально - localhost
        default_host = 'elasticsearch' if os.getenv('POSTGRES_HOST') == 'postgres' else 'localhost'
        es_host = os.getenv('ELASTICSEARCH_HOST', default_host).replace('http://', '').replace('https://', '')
        es_port = int(os.getenv('ELASTICSEARCH_PORT', 9200))
        
        if not wait_for_elasticsearch(es_host, es_port):
            print("❌ Elasticsearch недоступен. Пропускаем индексацию.")
            return
        
        # Создаем агента через сервис
        try:
            es_url = f"http://{es_host}" if not es_host.startswith('http') else es_host
            agent = ElasticSearchAgentService.create_agent(
                "bert_spacy",
                es_host=es_url,
                es_port=es_port,
                model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            )
            ElasticSearchAgentService.set_active_agent("bert_spacy")
            print("✅ Агент создан")
        except Exception as e:
            print(f"❌ Ошибка создания агента: {e}")
            import traceback
            traceback.print_exc()
            return
    
    # Подключаемся к БД
    db: Session = SessionLocal()
    
    try:
        # Получаем все статьи
        articles = db.query(Article).limit(50).all()
        print(f"\nНайдено статей для индексации: {len(articles)}")
        
        if not articles:
            print("⚠️ В базе данных нет статей")
            return
        
        index_name = "articles"
        
        # Проверяем существование индекса
        if agent.es.indices.exists(index=index_name):
            print(f"Индекс {index_name} существует, обновляем...")
        else:
            # Создаем индекс с mapping
            mapping = {
                "mappings": {
                    "properties": {
                        "article_id": {"type": "integer"},
                        "title": {"type": "text", "analyzer": "russian"},
                        "text": {"type": "text", "analyzer": "russian"},
                        "url": {"type": "keyword"},
                        "language": {"type": "keyword"},
                        "embedding": {
                            "type": "dense_vector",
                            "dims": 384
                        },
                        "created_at": {"type": "date"}
                    }
                }
            }
            agent.es.indices.create(index=index_name, body=mapping, ignore=[400])
            print(f"✅ Индекс {index_name} создан")
        
        indexed = 0
        errors = []
        
        for article in articles:
            try:
                doc = {
                    "article_id": article.id,
                    "title": article.title or "",
                    "text": article.text or "",
                    "url": article.url or "",
                    "language": article.language or "ru",
                    "created_at": article.created_at.isoformat() if article.created_at else None
                }
                
                # Создаем эмбеддинг
                content = f"{doc['title']} {doc['text']}"
                if content.strip():
                    embedding = agent.get_embedding(content)
                    doc['embedding'] = embedding.tolist()
                    
                    # Индексируем
                    agent.es.index(index=index_name, id=article.id, document=doc)
                    indexed += 1
                    if indexed % 10 == 0:
                        print(f"  [{indexed}/{len(articles)}] Индексировано...")
                else:
                    errors.append(f"Статья {article.id}: пустой контент")
                    
            except Exception as e:
                errors.append(f"Статья {article.id}: {str(e)}")
                logger.error(f"Ошибка индексации статьи {article.id}: {e}")
        
        # Обновляем индекс
        agent.es.indices.refresh(index=index_name)
        count = agent.es.count(index=index_name)['count']
        
        print(f"\n✅ Индексировано статей: {indexed}")
        print(f"✅ Всего документов в индексе: {count}")
        if errors:
            print(f"⚠️ Ошибок: {len(errors)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        logger.exception("Детали ошибки:")
        return False
    finally:
        db.close()


if __name__ == "__main__":
    try:
        index_articles()
    except KeyboardInterrupt:
        print("\n\n⚠️ Индексация прервана")
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {e}")
        logger.exception("Детали ошибки:")

