import socket
import time
import pymongo
import psycopg2 
from datetime import datetime

# --- CONFIGURAÇÕES DO ASTERISK (AMI) ---
AMI_HOST = '127.0.0.1'
AMI_PORT = 5038
AMI_USER = 'admin'
AMI_PASS = 'amp111'

# --- CONEXÃO MONGO ---
client = pymongo.MongoClient('mongodb://localhost:27017/')
db = client['asterisk_realtime']
col_queues = db['queues']

def get_extension_names():
    """Busca nomes do Postgres"""
    names_map = {}
    conn = None
    try:
        conn = psycopg2.connect(
            host="127.0.0.1",      
            database="asterisk",
            user="asterisk",
            password="asterisk"
        )
        cur = conn.cursor()
        cur.execute("SELECT extension, name FROM extensions")
        rows = cur.fetchall()
        for r in rows:
            ext = str(r[0]) if isinstance(r, tuple) else str(r['extension'])
            nom = r[1] if isinstance(r, tuple) else r['name']
            names_map[ext] = nom
    except Exception as e:
        print(f"Erro Postgres: {e}")
    finally:
        if conn: conn.close()
    return names_map

def get_mongo_state():
    """Lê o estado atual do Mongo para preservar os tempos"""
    state = {}
    try:
        docs = col_queues.find()
        for d in docs:
            if 'members' in d:
                for m in d['members']:
                    # Chave única: Fila + Interface
                    key = f"{d['name']}-{m['interface']}"
                    state[key] = {
                        'last_status': m.get('status'),
                        'last_paused': m.get('paused'),
                        'state_timestamp': m.get('state_timestamp', time.time())
                    }
    except:
        pass
    return state

def get_queue_status(previous_state):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    try:
        s.connect((AMI_HOST, AMI_PORT))
        s.send(f"Action: Login\r\nUsername: {AMI_USER}\r\nSecret: {AMI_PASS}\r\n\r\n".encode())
        s.recv(1024)
        s.send(b"Action: QueueStatus\r\n\r\n")
        
        buffer = ""
        while True:
            try:
                chunk = s.recv(4096).decode('utf-8', errors='ignore')
                if not chunk: break
                buffer += chunk
                if "Event: QueueStatusComplete" in buffer: break
            except socket.timeout:
                break
        
        s.send(b"Action: Logoff\r\n\r\n")
        s.close()
        
        return parse_ami_data(buffer, previous_state)
    except Exception as e:
        print(f"Erro Conexão AMI: {e}")
        return {}

def parse_ami_data(buffer, previous_state):
    name_map = get_extension_names()
    queues = {}
    events = buffer.split('\r\n\r\n')
    
    # 1. Identifica Filas
    for e in events:
        if 'Event: QueueParams' in e:
            lines = e.split('\r\n')
            data = {}
            for line in lines:
                if ': ' in line:
                    k, v = line.split(': ', 1)
                    data[k] = v
            
            qname = data.get('Queue')
            if qname:
                queues[qname] = {
                    'name': qname,
                    'calls': int(data.get('Calls', 0)),
                    'completed': int(data.get('Completed', 0)),
                    'abandoned': int(data.get('Abandoned', 0)),
                    'servicelevel': data.get('ServiceLevel', '0'),
                    'strategy': data.get('Strategy', ''),
                    'members': [],
                    'callers': [],
                    'last_update': datetime.now().strftime('%H:%M:%S')
                }

    # 2. Preencher Detalhes
    for e in events:
        lines = e.split('\r\n')
        data = {}
        for line in lines:
            if ': ' in line:
                k, v = line.split(': ', 1)
                data[k] = v
        
        evt = data.get('Event')
        qname = data.get('Queue')
        
        if qname and qname in queues:
            if evt == 'QueueMember':
                interface = data.get('Name') 
                clean_ext = interface.split('/')[-1] if '/' in interface else interface
                
                db_name = name_map.get(clean_ext)
                ami_name = data.get('MemberName')
                
                if db_name: real_name = f"{clean_ext} - {db_name}"
                elif ami_name and ami_name != interface: real_name = f"{clean_ext} - {ami_name}"
                else: real_name = clean_ext

                # LÓGICA DO CRONÔMETRO
                status = data.get('Status')
                paused = data.get('Paused')
                
                # Recupera estado anterior
                key = f"{qname}-{interface}"
                prev = previous_state.get(key)
                
                timestamp = time.time() # Default para agora (se mudou ou é novo)
                
                if prev:
                    # Se o status E a pausa forem iguais, mantemos o tempo antigo
                    if prev['last_status'] == status and prev['last_paused'] == paused:
                        timestamp = prev['state_timestamp']

                queues[qname]['members'].append({
                    'interface': interface,
                    'membername': real_name,
                    'location': data.get('Location'),
                    'status': status,
                    'paused': paused,
                    'calls_taken': data.get('CallsTaken'),
                    'state_timestamp': timestamp # Envia a hora que o status começou
                })
            elif evt == 'QueueEntry':
                queues[qname]['callers'].append({
                    'callerid': data.get('CallerIDNum'),
                    'wait': data.get('Wait'),
                    'position': data.get('Position')
                })

    return queues

if __name__ == "__main__":
    print("--- Queue Listener Iniciado (Com Timer) ---")
    while True:
        try:
            # 1. Pega estado atual do banco (para não zerar timer)
            prev_state = get_mongo_state()
            
            # 2. Pega novos dados do Asterisk
            data = get_queue_status(prev_state)
            
            if data:
                for qname, qdata in data.items():
                    col_queues.update_one(
                        {'name': qname}, 
                        {'$set': qdata}, 
                        upsert=True
                    )
            time.sleep(1) 
        except Exception as e:
            print(f"Erro Loop: {e}")
            time.sleep(5)
