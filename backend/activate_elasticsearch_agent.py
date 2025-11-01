#!/usr/bin/env python3
"""
Скрипт для активации Elasticsearch агента
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from services.elasticsearch_agent_service import ElasticSearchAgentService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def activate_agent():
    """Активирует Elasticsearch агента"""
    print("\n" + "="*60)
    print("АКТИВАЦИЯ ELASTICSEARCH АГЕНТА")
    print("="*60)
    
    # В Docker используем имя сервиса, локально - localhost
    default_host = 'elasticsearch' if os.getenv('POSTGRES_HOST') == 'postgres' else 'localhost'
    es_host = os.getenv('ELASTICSEARCH_HOST', default_host)
    es_port = int(os.getenv('ELASTICSEARCH_PORT', 9200))
    
    # Формируем URL
    if not es_host.startswith('http'):
        es_url = f"http://{es_host}"
    else:
        es_url = es_host
    
    try:
        print(f"\nПодключение к Elasticsearch: {es_url}:{es_port}")
        
        # Создаем BERT+spaCy агента (самый универсальный)
        agent = ElasticSearchAgentService.create_agent(
            "bert_spacy",
            es_host=es_url,
            es_port=es_port,
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )
        
        # Активируем агента
        ElasticSearchAgentService.set_active_agent("bert_spacy")
        
        print("✅ Elasticsearch агент успешно активирован!")
        print(f"   Тип: bert_spacy")
        print(f"   Elasticsearch: {es_url}:{es_port}")
        
        # Сохраняем настройки
        from app.api.elasticsearch_api import _es_agent_settings
        _es_agent_settings.update({
            "enabled": True,  # Включено по умолчанию
            "agent_type": "bert_spacy",
            "model_name": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            "es_host": es_url,
            "es_port": es_port
        })
        
        print("\n✅ Настройки сохранены")
        return True
        
    except Exception as e:
        print(f"\n❌ Ошибка активации агента: {e}")
        logger.exception("Детали ошибки:")
        return False

if __name__ == "__main__":
    activate_agent()

