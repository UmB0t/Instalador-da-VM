from flask import Blueprint, render_template, jsonify
from flask_login import login_required
from app.modules.ramais import listar_todos as listar_ramais
from app.modules.ferramentas import get_db_connection
from pymongo import MongoClient
import datetime

# Setup conexão Mongo direta para buscar dados em tempo real
MONGO_URI = 'mongodb://localhost:27017/'
mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
db_mongo = mongo_client['asterisk_realtime']

bp = Blueprint('admin_monitor', __name__, url_prefix='/admin')

# --- FUNÇÕES AUXILIARES ---

def formatar_data(dt):
    """
    Recebe um objeto datetime (ou string, ou None) e retorna uma tupla:
    (Data Formatada para Leitura, Data ISO para Cálculo JS)
    """
    if isinstance(dt, datetime.datetime):
        return dt.strftime('%d/%m/%Y %H:%M:%S'), dt.isoformat()
    
    # Fallback para string antiga (caso exista no banco)
    if isinstance(dt, str):
        try:
            # Tenta converter string para objeto para gerar o ISO
            dt_obj = datetime.datetime.strptime(dt, '%d/%m/%Y %H:%M:%S')
            return dt, dt_obj.isoformat()
        except:
            return dt, None
            
    return '-', None

def get_status_ramais():
    """
    Cruza dados do PostgreSQL (Extensions) com MongoDB (Status Realtime)
    """
    # 1. Busca Ramais Estáticos (SQL)
    estaticos = listar_ramais()
    
    # 2. Busca Status Dinâmico (Mongo)
    try:
        cursor = db_mongo['extensions'].find({})
        dinamicos = {d['extension']: d for d in cursor}
    except: 
        dinamicos = {}

    lista = []
    for r in estaticos:
        ext = r['extension']
        d = dinamicos.get(ext, {})
        
        txt_date, iso_date = formatar_data(d.get('last_update'))
        status_atual = d.get('status', 'Unavailable')
        
        lista.append({
            'extension': ext, 
            'name': r['name'], 
            'technology': r['technology'],
            'status': status_atual,
            'last_update': txt_date, 
            'last_update_iso': iso_date,
            'ip_address': d.get('address', '-')
        })
    return lista

def get_status_troncos():
    """
    Cruza dados do PostgreSQL (Trunks) com MongoDB (Status Realtime)
    """
    # 1. Busca Troncos do SQL
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, technology, host, port FROM trunks ORDER BY name ASC")
    sql_trunks = cur.fetchall()
    conn.close()
    
    # 2. Busca Status do Mongo
    try:
        cursor = db_mongo['trunks'].find({})
        mongo_trunks = {t['name']: t for t in cursor}
    except: 
        mongo_trunks = {}
    
    lista = []
    for t in sql_trunks:
        # Tratamento Híbrido (Tupla ou Dict dependendo do driver)
        if isinstance(t, tuple): 
            name, tech, host, port = t[0], t[1], t[2], t[3]
        else: 
            name, tech, host, port = t['name'], t['technology'], t['host'], t['port']
        
        d = mongo_trunks.get(name, {})
        
        # Formata datas
        txt_date, iso_date = formatar_data(d.get('last_update'))
        
        status_raw = d.get('status', 'Offline')
        latency = d.get('latency', '-')
        
        # Define cor baseada no status
        cor = 'secondary'
        if status_raw == 'Online': cor = 'success'
        elif status_raw == 'Lagged': cor = 'warning'
        elif status_raw == 'Offline': cor = 'danger'

        lista.append({
            'name': name,
            'technology': tech.upper(),
            'host': f"{host}:{port}",
            'status': status_raw,
            'latency': latency,
            'color': cor,
            'last_update': txt_date,
            'last_update_iso': iso_date  # Essencial para o cronômetro
        })
    return lista

# ==========================================
# --- ROTAS: MONITORAMENTO DE RAMAIS ---
# ==========================================

@bp.route('/monitoramento')
@login_required
def monitoramento():
    data = get_status_ramais()
    
    # Calcula Resumo
    total = len(data)
    online = sum(1 for x in data if x['status'] in ['Idle', 'Not in use'])
    falando = sum(1 for x in data if x['status'] in ['In use', 'Busy', 'Ringing'])
    indisp = total - online - falando
    
    resumo = {
        'total': total, 
        'online': online, 
        'falando': falando, 
        'indisponivel': indisp
    }

    return render_template('monitoramento_ramais.html', ramais=data, resumo=resumo)

@bp.route('/api/dados_tempo_real')
@login_required
def api_ramais():
    data = get_status_ramais()
    
    total = len(data)
    online = sum(1 for x in data if x['status'] in ['Idle', 'Not in use'])
    falando = sum(1 for x in data if x['status'] in ['In use', 'Busy', 'Ringing'])
    indisp = total - online - falando
    
    return jsonify({
        'ramais': data,
        'resumo': {
            'total': total, 
            'online': online, 
            'falando': falando, 
            'indisponivel': indisp
        }
    })

# ==========================================
# --- ROTAS: MONITORAMENTO DE TRONCOS ---
# ==========================================

@bp.route('/monitoramento_troncos')
@login_required
def monitoramento_troncos_page():
    dados = get_status_troncos()
    
    total = len(dados)
    online = sum(1 for x in dados if x['status'] == 'Online')
    offline = total - online
    
    return render_template('monitoramento_troncos.html', 
                           troncos=dados, 
                           resumo={'total': total, 'online': online, 'offline': offline})

@bp.route('/api/troncos_tempo_real')
@login_required
def api_troncos():
    dados = get_status_troncos()
    
    total = len(dados)
    online = sum(1 for x in dados if x['status'] == 'Online')
    offline = total - online
    
    return jsonify({
        'troncos': dados,
        'resumo': {'total': total, 'online': online, 'offline': offline}
    })

# ==========================================
# ---    ROTAS: MONITORAMENTO DE FILAS   ---
# ==========================================

@bp.route('/monitoramento_filas')
@login_required
def monitoramento_filas_page():
    # Busca nomes das filas no Banco SQL (tabela queues) para o filtro
    conn = get_db_connection()
    cur = conn.cursor()
    # Verifica se a tabela existe para evitar erro
    try:
        cur.execute("SELECT name FROM queues ORDER BY name")
        rows = cur.fetchall()
        filas_db = [r[0] if isinstance(r, tuple) else r['name'] for r in rows]
    except:
        filas_db = []
    conn.close()
    
    return render_template('monitor_filas.html', filas_db=filas_db)

@bp.route('/api/filas_tempo_real')
@login_required
def api_filas():
    # Busca dados no Mongo (populados pelo queue_listener.py)
    try:
        cursor = db_mongo['queues'].find({})
        dados = {q['name']: q for q in cursor}
        
        # Limpeza para JSON
        for k, v in dados.items():
            if '_id' in v: del v['_id']
            
        return jsonify(dados)
    except Exception as e:
        return jsonify({'error': str(e)})
