from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.modules.ferramentas import get_db_connection, registrar_log
import os

bp = Blueprint('ramais', __name__)

ARQUIVO_PJSIP = '/etc/asterisk/pjsip_ramais.conf'
ARQUIVO_SIP = '/etc/asterisk/sip_ramais.conf'
ARQUIVO_HINT = '/etc/asterisk/macros/hint.conf'

# --- ROTAS GET ---

@bp.route('/ramais')
@login_required
def index():
    lista = listar_todos()
    ctxs, secs = listar_opcoes_auxiliares()
    return render_template('ramais.html', 
                           ramais=lista, 
                           contexts=ctxs,
                           sectors=secs)

@bp.route('/ramais/novo', methods=['GET'])
@login_required
def novo_form():
    ctxs, secs = listar_opcoes_auxiliares()
    return render_template('criar_ramal.html', 
                           contexts=ctxs,
                           sectors=secs)

@bp.route('/ramais/range', methods=['GET'])
@login_required
def range_form():
    ctxs, secs = listar_opcoes_auxiliares()
    return render_template('criar_range.html', 
                           contexts=ctxs,
                           sectors=secs)

@bp.route('/ramais/editar/<id>', methods=['GET'])
@login_required
def editar_form(id):
    ramal = buscar_por_extension(id)
    if not ramal:
        flash('Ramal não encontrado!', 'danger')
        return redirect(url_for('ramais.index'))
    
    ctxs, secs = listar_opcoes_auxiliares()
    return render_template('editar_ramal.html', 
                           ramal=ramal, 
                           contexts=ctxs,
                           sectors=secs)

# --- ROTAS POST ---

@bp.route('/ramais/criar', methods=['POST'])
@login_required
def criar():
    dados = request.form.to_dict()
    sucesso, msg = criar_novo_ramal(dados)
    if sucesso: 
        flash(msg, 'success')
        # LOG
        registrar_log(current_user, f"criou o ramal {dados['extension']} ({dados['name']}).")
    else: 
        flash(msg, 'danger')
    return redirect(url_for('ramais.index'))

@bp.route('/ramais/criar_range', methods=['POST'])
@login_required
def criar_range_rota():
    dados = request.form.to_dict()
    sucesso, msg = criar_lote(dados)
    if sucesso: 
        flash(msg, 'success')
        # LOG
        registrar_log(current_user, f"criou um range de ramais.", f"De: {dados['inicio']} Até: {dados['fim']}")
    else: 
        flash(msg, 'danger')
    return redirect(url_for('ramais.index'))

@bp.route('/ramais/editar', methods=['POST'])
@login_required
def editar():
    dados = request.form.to_dict()
    # Busca dados antigos para log
    antigo = buscar_por_extension(dados['extension'])
    
    sucesso, msg = atualizar_ramal(dados)
    if sucesso: 
        flash(msg, 'success')
        
        # LOG DE DIFF
        alteracoes = []
        if antigo:
            if antigo['name'] != dados['name']:
                alteracoes.append(f"Nome: '{antigo['name']}' -> '{dados['name']}'")
            if antigo['technology'] != dados['technology']:
                alteracoes.append(f"Tech: '{antigo['technology']}' -> '{dados['technology']}'")
            if antigo['secret'] != dados['secret']:
                alteracoes.append("Senha alterada")
            # Comparação de IDs (tratando None)
            ant_ctx = str(antigo['context_id'] or '')
            new_ctx = str(dados.get('context_id') or dados.get('ctx_id') or '')
            if ant_ctx != new_ctx:
                alteracoes.append(f"Contexto ID: '{ant_ctx}' -> '{new_ctx}'")
                
            ant_sec = str(antigo['sectors_id'] or '')
            new_sec = str(dados.get('sectors_id') or dados.get('sec_id') or '')
            if ant_sec != new_sec:
                alteracoes.append(f"Setor ID: '{ant_sec}' -> '{new_sec}'")

            detalhe = " | ".join(alteracoes) if alteracoes else "Sem alterações visíveis"
            registrar_log(current_user, f"editou o ramal {dados['extension']}.", detalhe)
            
    else: 
        flash(msg, 'danger')
    return redirect(url_for('ramais.index'))

@bp.route('/ramais/excluir/<id>')
@login_required
def excluir(id):
    # Pega nome antes de excluir
    ramal = buscar_por_extension(id)
    nome_ramal = ramal['name'] if ramal else 'Desconhecido'
    
    sucesso, msg = excluir_ramal(id)
    if sucesso: 
        flash(msg, 'success')
        # LOG
        registrar_log(current_user, f"excluiu o ramal {id} ({nome_ramal}).")
    else: 
        flash(msg, 'error')
    return redirect(url_for('ramais.index'))

@bp.route('/ramais/editar_massa', methods=['POST'])
@login_required
def editar_massa_rota():
    ids = request.form.getlist('ids[]')
    dados = request.form.to_dict()
    if not ids:
        flash('Selecione pelo menos um ramal.', 'warning')
        return redirect(url_for('ramais.index'))
    
    sucesso, msg = editar_em_massa(ids, dados)
    if sucesso: 
        flash(msg, 'success')
        
        # --- LOG MELHORADO (CORREÇÃO SOLICITADA) ---
        log_detalhes = []
        
        # Verifica Tecnologia
        if dados.get('technology'):
            log_detalhes.append(f"Tecnologia definida para '{dados['technology']}'")
            
        # Verifica Transporte
        if dados.get('transport'):
            log_detalhes.append(f"Transporte definido para '{dados['transport']}'")
            
        # Verifica Contexto (tenta pegar por nomes variados de chave)
        ctx = dados.get('ctx_id') or dados.get('context_id')
        if ctx:
            log_detalhes.append(f"Contexto ID definido para '{ctx}'")
            
        # Verifica Setor
        sec = dados.get('sec_id') or dados.get('sectors_id')
        if sec:
            log_detalhes.append(f"Setor ID definido para '{sec}'")
            
        # Monta a string final
        msg_final = " | ".join(log_detalhes) if log_detalhes else "Nenhum campo de valor enviado."
        
        registrar_log(current_user, f"editou {len(ids)} ramais em massa.", msg_final)
    else: 
        flash(msg, 'danger')
    return redirect(url_for('ramais.index'))

@bp.route('/ramais/excluir_massa', methods=['POST'])
@login_required
def excluir_massa():
    ids = request.form.getlist('ids[]')
    if not ids:
        flash('Selecione ramais para excluir.', 'warning')
        return redirect(url_for('ramais.index'))
    
    sucesso, msg = excluir_em_massa(ids)
    if sucesso: 
        flash(msg, 'success')
        # LOG
        lista_ids = ", ".join(ids) if len(ids) < 10 else f"{len(ids)} ramais"
        registrar_log(current_user, f"excluiu ramais em massa.", f"IDs: {lista_ids}")
    else: 
        flash(msg, 'danger')
    return redirect(url_for('ramais.index'))

# --- FUNÇÕES DE BANCO ---

def listar_opcoes_auxiliares():
    """Retorna LISTA DE DICIONÁRIOS [{'id':1, 'name':'X'}]"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT id, name FROM contexts ORDER BY name")
    rows_ctx = cur.fetchall()
    
    cur.execute("SELECT id, name FROM sectors ORDER BY name")
    rows_sec = cur.fetchall()
    conn.close()
    
    # Padroniza tudo como DICIONÁRIO
    ctxs = []
    for r in rows_ctx:
        if isinstance(r, tuple):
            ctxs.append({'id': r[0], 'name': r[1]})
        else:
            ctxs.append({'id': r['id'], 'name': r['name']})
        
    secs = []
    for r in rows_sec:
        if isinstance(r, tuple):
            secs.append({'id': r[0], 'name': r[1]})
        else:
            secs.append({'id': r['id'], 'name': r['name']})

    return ctxs, secs

def listar_todos():
    conn = get_db_connection()
    cur = conn.cursor()
    sql = """
        SELECT r.extension, r.name, r.technology, c.name as context, s.name as sector, 
               r.secret, r.transport, r.context_id, r.sectors_id
        FROM extensions r
        LEFT JOIN contexts c ON r.context_id = c.id
        LEFT JOIN sectors s ON r.sectors_id = s.id
        ORDER BY r.extension ASC
    """
    cur.execute(sql)
    rows = cur.fetchall()
    conn.close()
    
    lista = []
    for r in rows:
        if isinstance(r, tuple):
            lista.append({
                'extension': r[0], 'name': r[1], 'technology': r[2], 'context': r[3], 'sector': r[4],
                'secret': r[5], 'transport': r[6], 'context_id': r[7], 'sectors_id': r[8]
            })
        else:
            lista.append({
                'extension': r['extension'], 'name': r['name'], 'technology': r['technology'], 
                'context': r['context'], 'sector': r['sector'],
                'secret': r['secret'], 'transport': r['transport'],
                'context_id': r.get('context_id'), 'sectors_id': r.get('sectors_id')
            })
    return lista

def buscar_por_extension(ramal_ext):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT extension, name, secret, context_id, sectors_id, technology, transport FROM extensions WHERE extension = %s", (ramal_ext,))
    row = cur.fetchone()
    conn.close()
    if row:
        if isinstance(row, tuple):
            return {'extension': row[0], 'name': row[1], 'secret': row[2], 'context_id': row[3], 'sectors_id': row[4], 'technology': row[5], 'transport': row[6]}
        return dict(row)
    return None

# --- LÓGICA DE NEGÓCIO ---

def criar_novo_ramal(dados):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT extension FROM extensions WHERE extension = %s", (dados['extension'],))
        if cur.fetchone(): return False, "Ramal já existe."
        
        sql = "INSERT INTO extensions (extension, name, technology, secret, context_id, sectors_id, transport) VALUES (%s, %s, %s, %s, %s, %s, %s)"
        
        # Pega do form (compatível com id ou _id)
        ctx = dados.get('context_id') or dados.get('ctx_id')
        sec = dados.get('sectors_id') or dados.get('sec_id')
        
        if not ctx: ctx = None
        if not sec: sec = None
        
        cur.execute(sql, (dados['extension'], dados['name'], dados.get('technology','pjsip'), dados['secret'], ctx, sec, dados.get('transport','transport-udp')))
        conn.commit()
        sync_asterisk()
        return True, "Criado com sucesso!"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally: conn.close()

def criar_lote(dados):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        inicio, fim = int(dados['inicio']), int(dados['fim'])
        criados = 0
        
        ctx = dados.get('context_id') or dados.get('ctx_id')
        sec = dados.get('sectors_id') or dados.get('sec_id')
        if not ctx: ctx = None
        if not sec: sec = None

        padrao = dados['senha_padrao']

        for num in range(inicio, fim + 1):
            ramal_str = str(num)
            ramal_name = f"Ramal {ramal_str}" 
            senha_final = padrao.replace('${ramal}', ramal_str).replace('{ramal}', ramal_str)

            cur.execute("SELECT extension FROM extensions WHERE extension=%s", (ramal_str,))
            if not cur.fetchone():
                cur.execute("""INSERT INTO extensions (extension, name, technology, secret, context_id, sectors_id, transport) 
                               VALUES (%s, %s, %s, %s, %s, %s, %s)""", 
                               (ramal_str, ramal_name, dados['technology'], senha_final, ctx, sec, dados['transport']))
                criados += 1
        
        conn.commit()
        sync_asterisk()
        return True, f"{criados} ramais criados com sucesso."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally: conn.close()

def atualizar_ramal(dados):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        sql = "UPDATE extensions SET name=%s, technology=%s, secret=%s, context_id=%s, sectors_id=%s, transport=%s WHERE extension=%s"
        
        ctx = dados.get('context_id') or dados.get('ctx_id')
        sec = dados.get('sectors_id') or dados.get('sec_id')
        
        if not ctx: ctx = None
        if not sec: sec = None
        
        cur.execute(sql, (dados['name'], dados['technology'], dados['secret'], ctx, sec, dados['transport'], dados['extension']))
        conn.commit()
        sync_asterisk()
        return True, "Atualizado!"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally: conn.close()

def editar_em_massa(ids, dados):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        campos, vals = [], []
        if dados.get('technology'): campos.append("technology=%s"); vals.append(dados['technology'])
        if dados.get('transport'): campos.append("transport=%s"); vals.append(dados['transport'])
        
        ctx = dados.get('ctx_id') or dados.get('context_id')
        sec = dados.get('sec_id') or dados.get('sectors_id')

        if ctx: campos.append("context_id=%s"); vals.append(ctx)
        if sec: campos.append("sectors_id=%s"); vals.append(sec)
        
        if not campos: return False, "Nenhum campo selecionado."
        
        sql = f"UPDATE extensions SET {', '.join(campos)} WHERE extension = ANY(%s)"
        vals.append(ids)
        cur.execute(sql, tuple(vals))
        conn.commit()
        sync_asterisk()
        return True, "Atualização em massa concluída."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally: conn.close()

def excluir_em_massa(ids):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM extensions WHERE extension = ANY(%s)", (ids,))
        conn.commit()
        sync_asterisk()
        return True, f"{cur.rowcount} ramais excluídos."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally: conn.close()

def excluir_ramal(id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM extensions WHERE extension=%s", (id,))
        conn.commit()
        sync_asterisk()
        return True, "Excluído."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally: conn.close()

def sync_asterisk():
    print("SYNC ASTERISK...")
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT r.extension, r.name, r.secret, c.name, r.transport, r.technology FROM extensions r LEFT JOIN contexts c ON r.context_id = c.id ORDER BY r.extension")
        rows = cur.fetchall()
        conn.close()

        pjsip = "; GERADO VIA SISTEMA\n\n"
        sip = "; GERADO VIA SISTEMA\n\n"
        hints = "[default]\n"

        for r in rows:
            if isinstance(r, tuple): ext, nm, pw, ctx, tr, te = r[0], r[1], r[2], r[3] or 'default', r[4], r[5].lower()
            else: ext, nm, pw, ctx, tr, te = r['extension'], r['name'], r['secret'], r['name'] or 'default', r['transport'], r['technology'].lower()
            
            tr_pjsip = tr or 'transport-udp'
            hints += f"exten => {ext},hint,{te.upper()}/{ext}\n"
            
            if 'pjsip' in te:
                pjsip += f"[{ext}]\ncallerid=\"{nm}\" <{ext}>\ntype=endpoint\ncontext={ctx}\naccountcode=Interno\ndtmf_mode=rfc4733\ndisallow=all\nallow=ulaw,alaw,g729\nauth=auth{ext}\naors={ext}\ncall_group=1\npickup_group=1\ntransport={tr_pjsip}\naggregate_mwi=yes\nallow_subscribe=yes\nmailboxes={ext}@{ctx}\nmwi_from_user={ext}\nwebrtc=no\n\n[auth{ext}]\ntype=auth\nauth_type=userpass\npassword={pw}\nusername={ext}\n\n[{ext}]\ntype=aor\nmax_contacts=99\nqualify_frequency=30\n\n"
            else:
                sip_tr = tr_pjsip.replace('transport-', '').upper()
                sip += f"[{ext}]\ncallerid=\"{nm}\" <{ext}>\naccountcode=INTERNO\nsecret={pw}\ncontext={ctx}\ncall-limit=1\ncc_agent_policy=generic\ncc_monitor_policy=generic\ndefaultuser={ext}\ncanreinvite=no\nhost=dynamic\ndtmfmode=rfc2833\nnat=force_rport,comedia\nqualify=yes\ntype=friend\ncallgroup=1\npickupgroup=1\ntransport={sip_tr}\n\n"

        with open(ARQUIVO_PJSIP, 'w') as f: f.write(pjsip)
        with open(ARQUIVO_SIP, 'w') as f: f.write(sip)
        
        d_hint = os.path.dirname(ARQUIVO_HINT)
        if not os.path.exists(d_hint): os.makedirs(d_hint, exist_ok=True)
        with open(ARQUIVO_HINT, 'w') as f: f.write(hints)

        os.system("asterisk -rx 'pjsip reload'")
        os.system("asterisk -rx 'sip reload'")
        os.system("asterisk -rx 'dialplan reload'")
    except Exception as e:
        print(f"Erro Sync: {e}")
