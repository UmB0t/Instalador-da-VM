from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.modules.ferramentas import get_db_connection, registrar_log
import socket

bp = Blueprint('monitoramento', __name__)

# Configurações do AMI
AMI_HOST = '127.0.0.1'
AMI_PORT = 5038
AMI_USER = 'admin'
AMI_PASS = 'amp111'

def send_ami_action(action_text):
    """Conecta no AMI, envia um comando e desconecta rápido"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    try:
        s.connect((AMI_HOST, AMI_PORT))
        # Login
        s.send(f"Action: Login\r\nUsername: {AMI_USER}\r\nSecret: {AMI_PASS}\r\n\r\n".encode())
        s.recv(1024) 
        
        # Envia Ação
        s.send(f"{action_text}\r\n\r\n".encode())
        response = s.recv(1024).decode()
        
        s.send(b"Action: Logoff\r\n\r\n")
        s.close()
        
        if "Response: Error" in response:
            return False, response
        return True, "Comando enviado."
    except Exception as e:
        return False, str(e)

# --- ROTAS DE AÇÃO ---

@bp.route('/monitor/ramais', methods=['GET'])
@login_required
def listar_ramais_db():
    """Busca ramais no banco para preencher o Select do Modal"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT extension, name, technology FROM extensions ORDER BY extension ASC")
        rows = cur.fetchall()
        conn.close()
        
        lista = []
        for r in rows:
            # Compatibilidade Tupla/Dict
            if isinstance(r, tuple):
                ext, name, tech = r[0], r[1], r[2]
            else:
                ext, name, tech = r['extension'], r['name'], r['technology']
            
            lista.append({
                'extension': ext,
                'name': name,
                'technology': tech or 'pjsip'
            })
        return jsonify(lista)
    except Exception as e:
        return jsonify([]), 500

@bp.route('/monitor/pausar', methods=['POST'])
@login_required
def pausar_agente():
    data = request.json
    interface = data.get('interface')
    paused = data.get('paused') # 'true' ou 'false' (string ou bool)
    
    # Normaliza booleano
    is_paused = str(paused).lower() == 'true'
    
    cmd = f"Action: QueuePause\r\nInterface: {interface}\r\nPaused: {paused}"
    success, msg = send_ami_action(cmd)
    
    if success: 
        acao = "Pausou" if is_paused else "Despausou"
        registrar_log(current_user, f"{acao} o agente '{interface}'.")
        return jsonify({'status': 'ok'})
        
    return jsonify({'status': 'error', 'msg': msg}), 500

@bp.route('/monitor/remover', methods=['POST'])
@login_required
def remover_agente():
    data = request.json
    raw_interface = str(data.get('interface', '')).strip()
    queue = data.get('queue')
    
    if not raw_interface or not queue:
        return jsonify({'status': 'error', 'msg': 'Dados incompletos'}), 400

    if '/' in raw_interface:
        ext_number = raw_interface.split('/')[-1]
        if '@' in ext_number: ext_number = ext_number.split('@')[0]
    else:
        ext_number = raw_interface

    candidates = [
        raw_interface,
        f"PJSIP/{ext_number}",
        f"SIP/{ext_number}",
        f"Local/{ext_number}@from-queue/n",
        f"Local/{ext_number}@from-internal/n"
    ]

    success = False
    last_msg = ""

    for iface in candidates:
        cmd = f"Action: QueueRemove\r\nQueue: {queue}\r\nInterface: {iface}"
        ok, msg = send_ami_action(cmd)
        
        if ok:
            success = True
            break
        else:
            last_msg = msg

    if success: 
        registrar_log(current_user, f"removeu o agente '{ext_number}' da fila '{queue}'.")
        return jsonify({'status': 'ok'})
    
    return jsonify({'status': 'error', 'msg': f"Não foi possível remover {ext_number}. Erro: {last_msg}"}), 500

@bp.route('/monitor/adicionar', methods=['POST'])
@login_required
def adicionar_agente():
    data = request.json
    interface = data.get('interface') 
    queue = data.get('queue')
    member_name = data.get('member_name')
    
    if '/' not in interface:
        interface = f"PJSIP/{interface}"

    cmd = f"Action: QueueAdd\r\nQueue: {queue}\r\nInterface: {interface}\r\nMemberName: {member_name}\r\nStateInterface: {interface}"
    success, msg = send_ami_action(cmd)
    
    if success: 
        registrar_log(current_user, f"adicionou o agente '{member_name}' na fila '{queue}'.")
        return jsonify({'status': 'ok'})
        
    return jsonify({'status': 'error', 'msg': msg}), 500
