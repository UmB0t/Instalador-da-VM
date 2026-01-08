# Arquivo: /opt/application/app/modules/sync_asterisk.py
import sys
import os
import subprocess
import psycopg2

# --- CONFIGURAÇÕES DO BANCO DE DADOS ---
# Ajuste aqui para bater com o seu get_db_connection
DB_HOST = "localhost"
DB_NAME = "asterisk_db"  # Nome do seu banco de dados
DB_USER = "postgres"     # Seu usuário do Postgres
DB_PASS = "postgres"     # Sua senha do Postgres

# --- CAMINHOS ---
ARQUIVO_PJSIP = '/etc/asterisk/pjsip_ramais.conf'
ARQUIVO_SIP = '/etc/asterisk/sip_ramais.conf'
ARQUIVO_HINT = '/etc/asterisk/macros/hint.conf'

def get_db_connection():
    """Conexão direta sem depender do Flask"""
    try:
        conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS)
        return conn
    except Exception as e:
        print(f"ERRO DE CONEXÃO DB: {e}")
        return None

def run_cmd(comando):
    """Executa comando no terminal"""
    try:
        # Timeout alto (30s) pois este script roda no background
        subprocess.run(comando, shell=True, timeout=30, check=False)
    except Exception as e:
        print(f"Erro ao executar '{comando}': {e}")

def main():
    print("--- INICIANDO SYNC ASTERISK (BACKGROUND) ---")
    
    conn = get_db_connection()
    if not conn:
        print("Abortando: Sem conexão com banco.")
        return

    try:
        cur = conn.cursor()
        sql = """
            SELECT r.extension, r.name, r.secret, c.name as context, r.transport, r.technology
            FROM extensions r
            LEFT JOIN contexts c ON r.context_id = c.id
            ORDER BY r.extension ASC
        """
        cur.execute(sql)
        todos_ramais = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Erro ao ler dados: {e}")
        return

    conteudo_pjsip = ""
    conteudo_sip = ""
    conteudo_hints = "[default]\n"
    
    for r in todos_ramais:
        # Acesso por índice (0=ext, 1=name, 2=secret, 3=context, 4=transport, 5=tech)
        ramal = r[0]
        nome = r[1]
        senha = r[2]
        contexto = r[3] if r[3] else "default"
        transporte = r[4] if r[4] else "transport-UDP"
        tecnologia = r[5].lower() if r[5] else 'pjsip'
        tech_upper = tecnologia.upper()
        
        # GERAÇÃO DO HINT
        conteudo_hints += f"exten => {ramal},hint,{tech_upper}/{ramal}\n"

        if 'pjsip' in tecnologia:
            bloco = f"""
[{ramal}]
callerid="{nome}"<{ramal}>
type=endpoint
context={contexto}
accountcode=ATENDIMENTO
dtmf_mode=rfc4733
disallow=all
allow=ulaw,alaw,g729
auth=auth{ramal}
aors={ramal}
call_group=1
pickup_group=1
transport={transporte}
aggregate_mwi=yes
allow_subscribe=yes
mailboxes={ramal}@{contexto}
mwi_from_user={ramal}
webrtc=no

[auth{ramal}]
type=auth
auth_type=userpass
password={senha}
username={ramal}

[{ramal}]
type=aor
max_contacts=3
qualify_frequency=30
"""
            conteudo_pjsip += bloco + "\n"

        elif 'sip' in tecnologia:
            bloco = f"""
[{ramal}]
type=friend
secret={senha}
context={contexto}
host=dynamic
callerid="{nome}" <{ramal}>
disallow=all
allow=ulaw,alaw,g729
qualify=yes
nat=force_rport,comedia
callgroup=1
pickupgroup=1
"""
            conteudo_sip += bloco + "\n"

    # ESCRITA DOS ARQUIVOS
    try:
        with open(ARQUIVO_PJSIP, 'w') as f:
            f.write("; ARQUIVO PJSIP GERADO AUTOMATICAMENTE - WEB\n" + conteudo_pjsip)
            
        with open(ARQUIVO_SIP, 'w') as f:
            f.write("; ARQUIVO SIP GERADO AUTOMATICAMENTE - WEB\n" + conteudo_sip)
            
        dir_hints = os.path.dirname(ARQUIVO_HINT)
        if not os.path.exists(dir_hints):
            os.makedirs(dir_hints, exist_ok=True)
            
        with open(ARQUIVO_HINT, 'w') as f:
            f.write("; ARQUIVO HINTS GERADO AUTOMATICAMENTE - WEB\n" + conteudo_hints)
            
        print("Arquivos gerados com sucesso.")
    except Exception as e:
        print(f"ERRO DE ARQUIVO: {e}")

    # RECARREGAR ASTERISK
    print("Recarregando Asterisk...")
    run_cmd("asterisk -rx 'pjsip reload'")
    run_cmd("asterisk -rx 'sip reload'")
    run_cmd("asterisk -rx 'dialplan reload'")
    print("--- SINCRONIZAÇÃO CONCLUÍDA ---")

if __name__ == "__main__":
    main()
