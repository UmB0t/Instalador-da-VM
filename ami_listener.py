import asyncio
import logging
from panoramisk import Manager
from pymongo import MongoClient
import datetime
import re

# --- CONFIGURAÇÕES ---
AMI_HOST = '127.0.0.1'
AMI_PORT = 5038
AMI_USER = 'admin'
AMI_SECRET = 'amp111' 

MONGO_URI = 'mongodb://localhost:27017/'
DB_NAME = 'asterisk_realtime'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Conexão MongoDB
try:
    mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = mongo_client[DB_NAME]
    extensions_collection = db['extensions']
    trunks_collection = db['trunks'] # Nova coleção para troncos
    mongo_client.admin.command('ping')
except Exception as e:
    logger.error(f"Erro Mongo: {e}")
    exit(1)

# --- FUNÇÕES DE ATUALIZAÇÃO ---

def update_extension_status(extension, status_text):
    try:
        extensions_collection.update_one(
            {'extension': extension},
            {'$set': {'status': status_text, 'last_update': datetime.datetime.now()}},
            upsert=True
        )
    except Exception as e:
        logger.error(f"Erro Update Ramal: {e}")

def update_trunk_status(name, tech, status, latency=None):
    """Atualiza status do tronco no MongoDB"""
    try:
        data = {
            'name': name,
            'technology': tech,
            'status': status,
            'last_update': datetime.datetime.now()
        }
        if latency:
            data['latency'] = latency
            
        trunks_collection.update_one(
            {'name': name},
            {'$set': data},
            upsert=True
        )
        logger.info(f"Tronco [{tech}] {name} -> {status} ({latency})")
    except Exception as e:
        logger.error(f"Erro Update Tronco: {e}")

# Mapeamento Ramais
STATUS_MAP = {
    '0': 'Idle', '1': 'In use', '2': 'Busy', 
    '4': 'Unavailable', '8': 'Ringing', '16': 'On Hold'
}

async def main():
    manager = Manager(loop=asyncio.get_event_loop(),
                      host=AMI_HOST, port=AMI_PORT,
                      username=AMI_USER, secret=AMI_SECRET)

    # --- EVENTO DE RAMAIS ---
    @manager.register_event('ExtensionStatus')
    async def callback_extension(manager, event):
        ext = event.get('Exten')
        stat = STATUS_MAP.get(event.get('Status'), 'Unknown')
        if ext and ext.isdigit():
            update_extension_status(ext, stat)

    # --- EVENTO DE TRONCOS SIP/IAX (PeerStatus) ---
    @manager.register_event('PeerStatus')
    async def callback_peer(manager, event):
        # Peer: "SIP/vivo-fixo" ou "IAX2/tim"
        peer_full = event.get('Peer', '')
        status = event.get('PeerStatus', '') # Registered, Unreachable, Reachable
        time = event.get('Time', '') # Latência "24 ms"

        if '/' in peer_full:
            tech, name = peer_full.split('/', 1)
            tech = tech.lower()
            
            # Filtra apenas tecnologias de tronco (ignora ramais SIP/IAX se houver)
            # Assumimos que ramais são numéricos e troncos são nomes.
            # Se seus troncos forem numéricos, precisaremos de outra lógica.
            if not name.isdigit(): 
                # Normaliza Status
                final_status = 'Offline'
                if 'Reachable' in status or 'Registered' in status:
                    final_status = 'Online'
                elif 'Lagged' in status:
                    final_status = 'Lagged'
                
                update_trunk_status(name, tech, final_status, time)

    # --- EVENTO DE TRONCOS PJSIP (ContactStatus) ---
    @manager.register_event('ContactStatus')
    async def callback_contact(manager, event):
        # AOR: "vivo-aor" -> precisamos limpar sufixos se houver
        aor = event.get('AOR', '')
        status = event.get('ContactStatus', '') # Reachable, Unreachable
        rtt = event.get('RoundtripUsec', '') # Microsegundos
        
        # O nome do tronco no nosso banco é limpo (ex: "vivo"). 
        # Se definimos o AOR como "vivo-aor", precisamos limpar.
        # Mas no nosso script troncos.py definimos: aors={nm}-aor. 
        # Então o evento virá como "vivo-aor".
        
        clean_name = aor.replace('-aor', '')
        
        final_status = 'Online' if status == 'Reachable' else 'Offline'
        latency = f"{int(rtt)/1000:.0f} ms" if rtt and rtt.isdigit() else None
        
        update_trunk_status(clean_name, 'pjsip', final_status, latency)

    logger.info("Conectando ao AMI...")
    try:
        await manager.connect()
        logger.info("AMI Conectado! Monitorando Ramais e Troncos.")
        
        # Força atualização inicial (Opcional, gera carga)
        # await manager.send_action({'Action': 'SIPpeers'})
        # await manager.send_action({'Action': 'PJSIPShowContacts'})
        
        while True:
            await asyncio.sleep(10)
    except Exception as e:
        logger.error(f"Falha AMI: {e}")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
