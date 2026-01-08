# Arquivo: /opt/application/app/modules/realtime.py

from pymongo import MongoClient
import logging
import datetime

# Configuração de Log
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# URI do MongoDB
MONGO_URI = 'mongodb://localhost:27017/' 
DB_NAME = 'asterisk_realtime'

def get_mongo_client():
    """Tenta conectar ao cliente MongoDB."""
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command('ping') 
        return client
    except Exception as e:
        logger.error(f"ERRO DE CONEXÃO AO MONGODB: {e}")
        return None

def get_realtime_db():
    """Retorna a instância do banco de dados de tempo real."""
    client = get_mongo_client()
    # CORREÇÃO: Comparar explicitamente com None
    if client is not None:
        return client[DB_NAME]
    return None

def update_extension_status(extension, status_name, status_time=None):
    """Atualiza o status de um ramal."""
    db = get_realtime_db()
    
    # CORREÇÃO CRÍTICA AQUI: Usar 'is not None'
    if db is not None:
        extensions_collection = db['extensions']
        
        status_data = {
            'status': status_name,
            'last_update': status_time if status_time else datetime.datetime.now()
        }
        
        extensions_collection.update_one(
            {'extension': extension},
            {'$set': status_data},
            upsert=True
        )
        return True
    return False

def get_all_extension_status():
    """Retorna todos os status de ramais armazenados."""
    db = get_realtime_db()
    
    # CORREÇÃO CRÍTICA AQUI (Linha 61 do erro): Usar 'is not None'
    if db is not None:
        extensions_collection = db['extensions']
        return list(extensions_collection.find({}))
    
    return []
