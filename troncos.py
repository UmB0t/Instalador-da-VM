from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.modules.ferramentas import get_db_connection, registrar_log
import os

bp = Blueprint('troncos', __name__)

# Arquivos de Destino
FILE_SIP = '/etc/asterisk/sip_trunk.conf'
FILE_PJSIP = '/etc/asterisk/pjsip_trunk.conf'
FILE_IAX = '/etc/asterisk/iax_trunk.conf'

# --- ROTAS ---

@bp.route('/troncos')
@login_required
def index():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM trunks ORDER BY name ASC")
    rows = cur.fetchall()
    conn.close()
    
    lista = []
    if rows:
        if isinstance(rows[0], tuple):
            colunas = [desc[0] for desc in cur.description]
            for row in rows:
                lista.append(dict(zip(colunas, row)))
        else:
            lista = rows

    return render_template('troncos.html', troncos=lista, edit_obj=None)

@bp.route('/troncos/salvar', methods=['POST'])
@login_required
def salvar():
    dados = request.form
    id_trunk = dados.get('id_trunk')
    # Tratamento de checkbox
    register = True if dados.get('register') else False
    
    reg_user = dados.get('register_username') or None
    reg_secret = dados.get('register_secret') or None

    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        if id_trunk and id_trunk.isdigit(): 
            # --- UPDATE ---
            # 1. Busca dados antigos para log
            cur.execute("SELECT * FROM trunks WHERE id=%s", (int(id_trunk),))
            row_antigo = cur.fetchone()
            antigo = {}
            if row_antigo:
                if isinstance(row_antigo, tuple):
                    cols = [desc[0] for desc in cur.description]
                    antigo = dict(zip(cols, row_antigo))
                else:
                    antigo = row_antigo

            # 2. Executa Update
            sql = """UPDATE trunks SET name=%s, username=%s, secret=%s, host=%s, port=%s, 
                     technology=%s, register=%s, context=%s, transport=%s,
                     register_username=%s, register_secret=%s
                     WHERE id=%s"""
            cur.execute(sql, (dados['name'], dados['username'], dados['secret'], dados['host'], 
                              dados['port'], dados['technology'], register, dados['context'], 
                              dados['transport'], reg_user, reg_secret, int(id_trunk)))
            msg = "Tronco atualizado!"
            
            # 3. Log de Diferenças
            alteracoes = []
            if antigo:
                if antigo.get('name') != dados['name']:
                    alteracoes.append(f"Nome: '{antigo.get('name')}' -> '{dados['name']}'")
                if antigo.get('host') != dados['host']:
                    alteracoes.append(f"Host: '{antigo.get('host')}' -> '{dados['host']}'")
                if antigo.get('username') != dados['username']:
                    alteracoes.append(f"User: '{antigo.get('username')}' -> '{dados['username']}'")
                if str(antigo.get('port')) != str(dados['port']):
                    alteracoes.append(f"Porta: '{antigo.get('port')}' -> '{dados['port']}'")
                if antigo.get('technology') != dados['technology']:
                    alteracoes.append(f"Tech: '{antigo.get('technology')}' -> '{dados['technology']}'")
                
                # Verifica senha (sem mostrar)
                if antigo.get('secret') != dados['secret']:
                    alteracoes.append("Senha alterada")

            detalhes_log = " | ".join(alteracoes) if alteracoes else "Sem alterações visíveis"
            registrar_log(current_user, f"editou o tronco {dados['name']}.", detalhes_log)

        else:
            # --- INSERT ---
            sql = """INSERT INTO trunks (name, username, secret, host, port, technology, register, context, transport, register_username, register_secret)
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
            cur.execute(sql, (dados['name'], dados['username'], dados['secret'], dados['host'], 
                              dados['port'], dados['technology'], register, dados['context'], 
                              dados['transport'], reg_user, reg_secret))
            msg = "Tronco criado com sucesso!"
            
            # Log de Criação
            registrar_log(current_user, f"criou o tronco {dados['name']}.", f"Tech: {dados['technology']} | Host: {dados['host']}")
            
        conn.commit()
        sincronizar_arquivos()
        flash(msg, 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f"Erro no banco: {e}", 'danger')
    finally:
        conn.close()
        
    return redirect(url_for('troncos.index'))

@bp.route('/troncos/editar/<int:id>')
@login_required
def editar(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM trunks WHERE id=%s", (id,))
    row = cur.fetchone()
    
    cur.execute("SELECT * FROM trunks ORDER BY name ASC")
    rows_all = cur.fetchall()
    conn.close()
    
    edit_obj = None
    if row:
        if isinstance(row, tuple):
            colunas = [desc[0] for desc in cur.description]
            edit_obj = dict(zip(colunas, row))
        else:
            edit_obj = row
        
    lista = []
    if rows_all:
        if isinstance(rows_all[0], tuple):
            colunas = [desc[0] for desc in cur.description]
            for r in rows_all:
                lista.append(dict(zip(colunas, r)))
        else:
            lista = rows_all

    return render_template('troncos.html', troncos=lista, edit_obj=edit_obj)

@bp.route('/troncos/excluir/<int:id>')
@login_required
def excluir(id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Busca nome antes de apagar
        cur.execute("SELECT name FROM trunks WHERE id=%s", (id,))
        row = cur.fetchone()
        nome_tronco = row[0] if row else "Desconhecido" # assume tuple access or dict based on connector
        if not isinstance(row, tuple) and row: nome_tronco = row['name']

        cur.execute("DELETE FROM trunks WHERE id=%s", (id,))
        conn.commit()
        
        sincronizar_arquivos()
        flash("Tronco removido.", 'success')
        
        # LOG
        registrar_log(current_user, f"excluiu o tronco {nome_tronco}.")

    except Exception as e:
        conn.rollback()
        flash(f"Erro ao excluir: {e}", 'danger')
    finally:
        conn.close()
    return redirect(url_for('troncos.index'))

# --- SINCRONIZAÇÃO INTELIGENTE ---

def sincronizar_arquivos():
    print("SYNC TRONCOS (Dynamic Support)...")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM trunks")
    rows = cur.fetchall()
    conn.close()
    
    troncos = []
    if rows:
        if isinstance(rows[0], tuple):
            colunas = [desc[0] for desc in cur.description]
            for r in rows:
                troncos.append(dict(zip(colunas, r)))
        else:
            troncos = rows

    sip_content = "; GERADO VIA SISTEMA\n"
    pjsip_content = "; GERADO VIA SISTEMA\n"
    iax_content = "; GERADO VIA SISTEMA\n"

    for t in troncos:
        tech = t['technology'].lower()
        nm = t['name']
        user = t['username']
        secret = t['secret']
        host = t['host'] # Pode ser 'dynamic'
        port = t['port']
        ctx = t['context']
        reg = t['register']
        
        reg_user = t.get('register_username') or user
        reg_secret = t.get('register_secret') or secret
        
        # --- LÓGICA SIP ---
        if tech == 'sip':
            sip_content += f"\n[{nm}]\ntype=friend\ndefaultuser={user}\nsecret={secret}\nhost={host}\nport={port}\ninsecure=port,invite\nqualify=yes\nnat=force_rport,comedia\ndisallow=all\nallow=alaw,ulaw\ndtmfmode=rfc2833\ncontext={ctx}\nreinvite=no\ncanreinvite=no\n"
            if reg and host.lower() != 'dynamic':
                sip_content += f"register => {reg_user}:{reg_secret}@{host}:{port}/{reg_user}\n"

        # --- LÓGICA IAX2 ---
        elif tech == 'iax2':
            iax_content += f"\n[{nm}]\ntype=friend\naccountcode=00{nm}\nusername={user}\nsecret={secret}\ncontext={ctx}\nhost={host}\nport={port}\nauth=md5\ndisallow=all\nallow=ulaw,alaw\ntransfer=yes\nrequirecalltoken=no\nqualify=yes\njitterbuffer=yes\ntrunk=yes\n"
            if reg and host.lower() != 'dynamic':
                iax_content += f"register = {reg_user}:{reg_secret}@{host}:{port}\n"

        # --- LÓGICA PJSIP ---
        elif tech == 'pjsip':
            transp = t['transport'] or 'transport-UDP'
            is_dynamic = (host.lower() == 'dynamic')

            # 1. Auth Principal
            pjsip_content += f"\n[{nm}-auth]\ntype=auth\nauth_type=userpass\npassword={secret}\nusername={user}\n"
            
            # 2. AOR (Address of Record)
            if is_dynamic:
                pjsip_content += f"\n[{nm}-aor]\ntype=aor\nmax_contacts=5\n"
            else:
                pjsip_content += f"\n[{nm}-aor]\ntype=aor\ncontact=sip:{host}:{port}\n"
            
            # 3. Endpoint
            pjsip_content += f"\n[{nm}]\ntype=endpoint\ntransport={transp}\ncontext={ctx}\ndisallow=all\nallow=gsm,alaw,g729,ulaw\noutbound_auth={nm}-auth\naors={nm}-aor\ndirect_media=no\n"
            
            # 4. Identify (SÓ GERA SE NÃO FOR DYNAMIC)
            if not is_dynamic:
                pjsip_content += f"\n[{nm}-identify]\ntype=identify\nendpoint={nm}\nmatch={host}\n"
            
            # 5. Registration (SÓ GERA SE NÃO FOR DYNAMIC)
            if reg and not is_dynamic:
                pjsip_content += f"\n[{nm}-reg-auth]\ntype=auth\nauth_type=userpass\npassword={reg_secret}\nusername={reg_user}\n"
                pjsip_content += f"\n[{nm}-reg]\ntype=registration\noutbound_auth={nm}-reg-auth\nserver_uri=sip:{host}:{port}\nclient_uri=sip:{reg_user}@{host}:{port}\n"

    try:
        with open(FILE_SIP, 'w') as f: f.write(sip_content)
        with open(FILE_PJSIP, 'w') as f: f.write(pjsip_content)
        with open(FILE_IAX, 'w') as f: f.write(iax_content)
        
        os.system("asterisk -rx 'sip reload'")
        os.system("asterisk -rx 'pjsip reload'")
        os.system("asterisk -rx 'iax2 reload'")
        os.system("asterisk -rx 'dialplan reload'")
    except Exception as e:
        print(f"Erro ao salvar arquivos: {e}")
