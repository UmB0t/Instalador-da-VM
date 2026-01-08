from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.modules.ferramentas import get_db_connection, registrar_log
import os

# Define o Blueprint
bp = Blueprint('rotas', __name__)

# --- CAMINHO CONFIGURADO ---
ARQUIVO_ROTAS = '/etc/asterisk/macros/rotas.conf'

# --- ROTAS WEB (FLASK) ---

@bp.route('/rotas', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        # Criação
        dados = request.form.to_dict()
        sucesso, msg = criar_rota(dados)
        if sucesso:
            flash(msg, 'success')
            # LOG DE CRIAÇÃO
            detalhes = f"Discagem: {dados['dialing']} -> Destino: {dados['destination']} (Tipo: {dados['type']})"
            registrar_log(current_user, f"criou a rota {dados['dialing']}.", detalhes)
        else:
            flash(msg, 'danger')
        return redirect(url_for('rotas.index'))

    # Listagem
    lista_rotas = listar_rotas()
    lista_ramais = listar_ramais_simples()
    lista_filas = listar_filas_opcoes()
    
    return render_template('rotas.html', 
                           rotas=lista_rotas, 
                           ramais=lista_ramais, 
                           filas=lista_filas, 
                           edit_obj=None)

@bp.route('/rotas/editar/<id>')
@login_required
def editar(id):
    rota = buscar_rota_por_id(id)
    if not rota:
        flash('Rota não encontrada.', 'danger')
        return redirect(url_for('rotas.index'))
    
    lista_rotas = listar_rotas()
    lista_ramais = listar_ramais_simples()
    lista_filas = listar_filas_opcoes()
    
    return render_template('rotas.html', 
                           rotas=lista_rotas, 
                           ramais=lista_ramais, 
                           filas=lista_filas,
                           edit_obj=rota)

@bp.route('/rotas/salvar', methods=['POST'])
@login_required
def salvar_edicao():
    dados = request.form.to_dict()
    id_rota = dados.get('id_rota')
    
    # Busca dados antigos para log de comparação
    antigo = buscar_rota_por_id(id_rota)

    sucesso, msg = atualizar_rota(id_rota, dados)
    if sucesso:
        flash(msg, 'success')
        
        # LOG DE DIFF (Detalhado)
        alteracoes = []
        if antigo:
            if antigo['dialing'] != dados['dialing']:
                alteracoes.append(f"Padrão: '{antigo['dialing']}' -> '{dados['dialing']}'")
            if antigo['destination'] != dados['destination']:
                alteracoes.append(f"Destino: '{antigo['destination']}' -> '{dados['destination']}'")
            if antigo['type'] != dados['type']:
                alteracoes.append(f"Tipo: '{antigo['type']}' -> '{dados['type']}'")
        
        msg_log = " | ".join(alteracoes) if alteracoes else "Sem alterações visíveis"
        registrar_log(current_user, f"editou a rota ID {id_rota}.", msg_log)

    else:
        flash(msg, 'danger')
    return redirect(url_for('rotas.index'))

@bp.route('/rotas/excluir/<id>')
@login_required
def excluir(id):
    # Busca antes de excluir para saber o que foi apagado
    rota = buscar_rota_por_id(id)
    nome_rota = rota['dialing'] if rota else f"ID {id}"
    destino_rota = rota['destination'] if rota else "?"

    sucesso, msg = excluir_rota(id)
    if sucesso:
        flash(msg, 'success')
        # LOG DE EXCLUSÃO
        registrar_log(current_user, f"excluiu a rota {nome_rota}.", f"Apontava para: {destino_rota}")
    else:
        flash(msg, 'danger')
    return redirect(url_for('rotas.index'))


# --- FUNÇÕES DE BANCO DE DADOS ---

def listar_rotas():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, dialing, type, destination FROM routes ORDER BY dialing ASC")
    rows = cur.fetchall()
    conn.close()
    return rows

def buscar_rota_por_id(rota_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, dialing, type, destination FROM routes WHERE id = %s", (rota_id,))
    row = cur.fetchone() # Retorna Dict (RealDictCursor) ou Tuple dependendo da config
    conn.close()
    
    # Normalização para garantir dicionário
    if row and isinstance(row, tuple):
        return {'id': row[0], 'dialing': row[1], 'type': row[2], 'destination': row[3]}
    return row

def listar_filas_opcoes():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT name FROM queues ORDER BY name ASC")
    rows = cur.fetchall()
    conn.close()
    return rows

def listar_ramais_simples():
    # Função auxiliar para preencher o Select
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT extension, name FROM extensions ORDER BY extension ASC")
    rows = cur.fetchall()
    conn.close()
    return rows

# --- CRUD ---

def criar_rota(dados):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM routes WHERE dialing = %s", (dados['dialing'],))
        if cur.fetchone(): return False, "Já existe uma rota para este número de discagem."

        sql = "INSERT INTO routes (dialing, type, destination) VALUES (%s, %s, %s)"
        cur.execute(sql, (dados['dialing'], dados['type'], dados['destination']))
        conn.commit()
        
        sincronizar_arquivo_rotas()
        return True, "Rota criada com sucesso!"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def atualizar_rota(rota_id, dados):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        sql = "UPDATE routes SET dialing=%s, type=%s, destination=%s WHERE id=%s"
        cur.execute(sql, (dados['dialing'], dados['type'], dados['destination'], rota_id))
        conn.commit()
        
        sincronizar_arquivo_rotas()
        return True, "Rota atualizada!"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def excluir_rota(rota_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM routes WHERE id = %s", (rota_id,))
        conn.commit()
        
        sincronizar_arquivo_rotas()
        return True, "Rota excluída."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

# --- SINCRONIZAÇÃO COM ASTERISK ---

def sincronizar_arquivo_rotas():
    print("SINCRONIZANDO ROTAS INTERNAS...")
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT dialing, type, destination FROM routes ORDER BY dialing ASC")
    rotas = cur.fetchall()
    conn.close()

    conteudo = "; ARQUIVO DE ROTAS INTERNAS - GERADO PELA WEB\n\n"
    conteudo += "[INTERNAL]\n\n"
    
    for r in rotas:
        # Tratamento para garantir acesso aos dados (Tuple ou Dict)
        if isinstance(r, tuple):
            discagem = r[0]
            tipo = r[1]
            destino = r[2]
        else:
            discagem = r['dialing']
            tipo = r['type']
            destino = r['destination']

        padrao = f"_{discagem}" 

        bloco = ""
        
        if tipo == 'ramal':
            bloco = f"""
exten => {padrao},1,NoOp( -- ROTA PARA RAMAL {destino} -- )
exten => {padrao},n,Goto(DIAL,{destino},1)
exten => {padrao},n,Hangup()
"""
        elif tipo == 'ramal_generico':
            bloco = f"""
exten => {padrao},1,NoOp( -- ROTA GENERICA {discagem} -- )
exten => {padrao},n,Goto(DIAL,${{EXTEN}},1)
exten => {padrao},n,Hangup()
"""
        elif tipo == 'fila':
            bloco = f"""
exten => {padrao},1,NoOp( -- ROTA PARA FILA {destino} -- )
exten => {padrao},n,Goto(Fila-{destino},${{EXTEN}},1)
exten => {padrao},n,Hangup()
"""
        
        conteudo += bloco

    try:
        os.makedirs(os.path.dirname(ARQUIVO_ROTAS), exist_ok=True)
        with open(ARQUIVO_ROTAS, 'w') as f:
            f.write(conteudo)
        print(f"Arquivo {ARQUIVO_ROTAS} escrito com sucesso.")
        os.system("asterisk -rx 'dialplan reload'")
    except Exception as e:
        print(f"ERRO ao escrever rotas: {e}")
