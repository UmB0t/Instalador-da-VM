import psycopg2
import os
import logging
import sys
import datetime
from app.modules.config import DB_CONFIG, FILES_CONFIG
from psycopg2.extras import RealDictCursor

# --- CONFIGURAÇÃO DE LOGS (NOVO) ---
# Configura o logger para escrever no stdout (console), 
# assim o PM2 captura e salva nos logs dele.
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(message)s')
logger = logging.getLogger('AsteriskApp')

def get_db_connection():
    conn = psycopg2.connect(
        host="localhost",
        database="asterisk",
        user="asterisk",
        password="asterisk" 
    )
    conn.cursor_factory = RealDictCursor 
    return conn

def reload_asterisk(tech):
    """Recarrega o Asterisk (SIP ou PJSIP)"""
    if tech == 'SIP':
        os.system("asterisk -rx 'sip reload'")
    else:
        os.system("asterisk -rx 'pjsip reload'")

def append_to_file(filepath, content):
    """Escreve no final do arquivo"""
    try:
        with open(filepath, 'a') as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"Erro ao escrever arquivo: {e}")
        return False

def remove_block_from_file(filepath, section_name):
    """Remove um bloco [nome] do arquivo"""
    if not os.path.exists(filepath):
        return

    with open(filepath, 'r') as f:
        lines = f.readlines()

    with open(filepath, 'w') as f:
        skip = False
        for line in lines:
            if line.strip() == f"[{section_name}]":
                skip = True
            elif skip and line.strip().startswith("["):
                skip = False
            
            if not skip:
                f.write(line)

# Geradores de Texto
def generate_sip_block(ext, secret, context):
    return f"\n; RAMAL {ext}\n[{ext}]\ncallerid=\"{ext}\" <{ext}>\naccountcode={context}\nsecret={secret}\ncontext={context}\ntype=Friend\nhost=dynamic\ndtmfmode=rfc2833\nqualify=yes\n"

def generate_pjsip_block(ext, secret, context):
    return f"\n; RAMAL {ext}\n[{ext}]\ntype=endpoint\ncontext={context}\nauth=auth{ext}\naors={ext}\n\n[auth{ext}]\ntype=auth\nauth_type=userpass\npassword={secret}\nusername={ext}\n\n[{ext}]\ntype=aor\nmax_contacts=3\n"

# --- FUNÇÃO DE LOG (NOVO) ---
def registrar_log(usuario_obj, acao, detalhe=""):
    """
    Gera um log padronizado para o PM2.
    Formato: [DD/MM/YYYY HH:MM] - O usuário X executou ação Y.
    """
    try:
        # Tenta pegar o nome do objeto usuário, se falhar usa string direta
        if hasattr(usuario_obj, 'name'):
            nome_usuario = usuario_obj.name
        elif hasattr(usuario_obj, 'username'):
            nome_usuario = usuario_obj.username
        else:
            nome_usuario = str(usuario_obj)
        
        data_hora = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')
        
        mensagem = f"[{data_hora}] - O usuário {nome_usuario} {acao}"
        if detalhe:
            mensagem += f" {detalhe}"
            
        logger.info(mensagem)
    except Exception as e:
        print(f"Erro ao gerar log interno: {e}")
