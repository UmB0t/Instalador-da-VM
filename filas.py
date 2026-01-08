from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.modules.ferramentas import get_db_connection, registrar_log
import os

# Define o Blueprint
bp = Blueprint('filas', __name__)

# --- ARQUIVOS DE DESTINO ---
ARQUIVO_MACROS = '/etc/asterisk/macros/queues.conf'
ARQUIVO_CONFIG = '/etc/asterisk/queues.conf'

# --- ROTAS ---

@bp.route('/filas', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        # Criação de nova fila
        dados = request.form.to_dict()
        sucesso, msg = criar_fila(dados)
        if sucesso:
            flash(msg, 'success')
        else:
            flash(msg, 'danger')
        return redirect(url_for('filas.index'))
    
    # Listagem (GET)
    lista = listar_filas()
    return render_template('filas.html', filas=lista, edit_obj=None)

@bp.route('/filas/editar/<id>')
@login_required
def editar(id):
    # Busca a fila específica
    fila = buscar_fila_por_id(id)
    if not fila:
        flash('Fila não encontrada.', 'danger')
        return redirect(url_for('filas.index'))
    
    # Busca todas para montar a lista lateral
    lista = listar_filas()
    return render_template('filas.html', filas=lista, edit_obj=fila)

@bp.route('/filas/salvar', methods=['POST'])
@login_required
def salvar_edicao():
    dados = request.form.to_dict()
    id_fila = dados.get('id_fila')
    
    sucesso, msg = atualizar_fila(id_fila, dados)
    if sucesso:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
    return redirect(url_for('filas.index'))

# ROTA: ALTERNAR STATUS
@bp.route('/filas/status/<id>')
@login_required
def alternar_status(id):
    sucesso, msg = alternar_status_fila(id)
    if sucesso:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
    return redirect(url_for('filas.index'))

# --- FUNÇÕES DE BANCO DE DADOS ---

def listar_filas():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, description, strategy, timeout, retry, wrapuptime, status
        FROM queues 
        ORDER BY name ASC
    """)
    rows = cur.fetchall()
    conn.close()
    return rows

def buscar_fila_por_id(fila_id):
    conn = get_db_connection()
    cur = conn.cursor()
    sql = """
        SELECT id, name, description, musiconhold, strategy, timeout, retry, 
               wrapuptime, maxlen, joinempty, leavewhenempty, time_condition_id, status
        FROM queues WHERE id = %s
    """
    cur.execute(sql, (fila_id,))
    row = cur.fetchone()
    conn.close()
    return row 

# --- CRUD ---

def criar_fila(dados):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM queues WHERE name = %s", (dados['name'],))
        if cur.fetchone(): return False, "Já existe uma fila com este nome."

        desc = dados.get('description', '')
        music = dados.get('musiconhold', 'default')
        join = dados.get('joinempty', 'yes')
        leave = dados.get('leavewhenempty', 'no')
        
        sql = """
            INSERT INTO queues (name, description, strategy, timeout, retry, wrapuptime, maxlen, joinempty, leavewhenempty, musiconhold, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
        """
        cur.execute(sql, (
            dados['name'], desc, dados['strategy'], dados['timeout'], 
            dados['retry'], dados['wrapuptime'], dados['maxlen'], 
            join, leave, music
        ))
        conn.commit()
        
        # LOG DE CRIAÇÃO
        registrar_log(current_user, f"criou a fila '{dados['name']}'.")
        
        sincronizar_arquivos_asterisk()
        return True, "Fila criada com sucesso!"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def atualizar_fila(fila_id, dados):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Busca dados ANTIGOS para log de diff
        cur.execute("SELECT * FROM queues WHERE id = %s", (fila_id,))
        antigo = cur.fetchone()

        # Prepara valores para salvar (trata defaults)
        desc = dados.get('description', '')
        music = dados.get('musiconhold', 'default')
        join = dados.get('joinempty', 'yes')
        leave = dados.get('leavewhenempty', 'no')

        sql = """
            UPDATE queues SET 
                description=%s, strategy=%s, timeout=%s, retry=%s, wrapuptime=%s, 
                maxlen=%s, joinempty=%s, leavewhenempty=%s, musiconhold=%s
            WHERE id=%s
        """
        cur.execute(sql, (
            desc, dados['strategy'], dados['timeout'], 
            dados['retry'], dados['wrapuptime'], dados['maxlen'], 
            join, leave, music,
            fila_id
        ))
        conn.commit()
        
        # LOG DE DIFF COMPLETO
        alteracoes = []
        if antigo:
            nome_fila = antigo['name']
            
            # Mapeia Nome do Campo DB -> Valor Novo (vindo do form)
            comparar = [
                ('description', desc, 'Descrição'),
                ('strategy', dados['strategy'], 'Estratégia'),
                ('timeout', dados['timeout'], 'Timeout'),
                ('retry', dados['retry'], 'Retry'),
                ('wrapuptime', dados['wrapuptime'], 'WrapUp'),
                ('maxlen', dados['maxlen'], 'MaxLen'),
                ('musiconhold', music, 'Música'),
                ('joinempty', join, 'Entrar Vazia'),
                ('leavewhenempty', leave, 'Sair Vazia')
            ]

            for campo_db, valor_novo, label in comparar:
                # Converte ambos para string para garantir comparação correta (DB retorna int, Form retorna str)
                val_antigo = str(antigo[campo_db]) if antigo[campo_db] is not None else ''
                val_novo = str(valor_novo)
                
                if val_antigo != val_novo:
                    alteracoes.append(f"{label}: '{val_antigo}' -> '{val_novo}'")
            
            if alteracoes:
                detalhe = " | ".join(alteracoes)
                registrar_log(current_user, f"editou a fila '{nome_fila}'.", detalhe)
            else:
                # Se salvou sem mudar nada, registra apenas que houve uma atualização
                registrar_log(current_user, f"atualizou a fila '{nome_fila}' (sem alterações visíveis).")

        sincronizar_arquivos_asterisk()
        return True, "Fila atualizada!"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def alternar_status_fila(fila_id):
    """Alterna entre Ativo (True) e Inativo (False)"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT name, status FROM queues WHERE id = %s", (fila_id,))
        atual = cur.fetchone()
        
        if not atual:
            return False, "Fila não encontrada."
            
        novo_status = not atual['status']
        nome_fila = atual['name']
        
        cur.execute("UPDATE queues SET status = %s WHERE id = %s", (novo_status, fila_id))
        conn.commit()
        
        # LOG DE STATUS
        acao = "Habilitou" if novo_status else "Desabilitou"
        registrar_log(current_user, f"{acao} a fila '{nome_fila}'.")
        
        sincronizar_arquivos_asterisk()
        
        status_txt = "Ativada" if novo_status else "Desativada"
        return True, f"Fila {status_txt} com sucesso."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

# --- SINCRONIZAÇÃO TOTAL ---

def sincronizar_arquivos_asterisk():
    print("SINCRONIZANDO FILAS (DIALPLAN + CONFIG)...")
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Filtra apenas status = TRUE
    sql = """
        SELECT name, strategy, timeout, wrapuptime, musiconhold, joinempty, leavewhenempty, retry, maxlen 
        FROM queues 
        WHERE status = true
        ORDER BY name ASC
    """
    cur.execute(sql)
    filas = cur.fetchall()
    conn.close()

    conteudo_macros = "; ARQUIVO DE FILAS (LOGICA) - GERADO PELA WEB\n\n"
    conteudo_conf = """[general]
persistentmembers = yes
autofill = yes
monitor-type = MixMonitor

"""

    for f in filas:
        nome_fila = f['name']
        strategy = f['strategy'].upper() if f['strategy'] else 'RRMEMORY'
        timeout = f['timeout'] if f['timeout'] else 15
        wrapuptime = f['wrapuptime'] if f['wrapuptime'] else 0
        music = f['musiconhold'] if f['musiconhold'] else 'default'
        joinempty = f['joinempty'] if f['joinempty'] else 'yes'
        
        # 1. MACROS
        contexto = f"Fila-{nome_fila}"
        bloco_macro = f"""
[{contexto}]
exten => _X.,1,Answer()
exten => _X.,n,NoOp(--- INICIO ATENDIMENTO FILA {nome_fila} ---)
exten => _X.,n,NoCDR()
exten => _X.,n,Set(__QUEUE_NAME={nome_fila})
exten => _X.,n,Set(__QUEUE_ID=${{GET_QUEUE_ID(${{QUEUE_NAME}})}})
exten => _X.,n,Gosub(QUEUE_INSERT,s,1)

exten => _X.,n,GotoIfTime(00:00-23:59,mon,*,*?in)
exten => _X.,n,GotoIfTime(00:00-23:59,tue,*,*?in)
exten => _X.,n,GotoIfTime(00:00-23:59,wed,*,*?in)
exten => _X.,n,GotoIfTime(00:00-23:59,thu,*,*?in)
exten => _X.,n,GotoIfTime(00:00-23:59,fri,*,*?in)
exten => _X.,n,GotoIfTime(00:00-23:59,sat,*,*?in)
exten => _X.,n,GotoIfTime(00:00-23:59,sun,*,*?in:out)

exten => _X.,n(in),MixMonitor(${{UNIQUEID}}.WAV,ab)
exten => _X.,n,Queue(${{QUEUE_NAME}},Ttc,,,300,,,QUEUE_UPDATE_ANSWER,,${{QUEUEPOSITION}})
exten => _X.,n,Hangup()

exten => _X.,n(out),Busy(3)
exten => _X.,n,Hangup()

exten => h,1,NoOp(--- FINALIZANDO E ATUALIZANDO CDR ---)
exten => h,n,GotoIf($[${{ISNULL(${{CDR_ID}})}}]?fim)
exten => h,n,Gosub(QUEUE_HANGUP_UPDATE,s,1)
exten => h,n(fim),Hangup()
"""
        conteudo_macros += bloco_macro + "\n"

        # 2. QUEUES.CONF
        bloco_conf = f"""
[{nome_fila}]
timeout={timeout}
setinterfacevar=YES
strategy={strategy}
musiconhold={music}
joinempty={joinempty}
autopause=NO
ringinuse=NO
setqueuevar=YES
periodic-announce=
periodic-announce-frequency=
wrapuptime={wrapuptime}
"""
        conteudo_conf += bloco_conf + "\n"

    try:
        os.makedirs(os.path.dirname(ARQUIVO_MACROS), exist_ok=True)
        with open(ARQUIVO_MACROS, 'w') as f:
            f.write(conteudo_macros)

        with open(ARQUIVO_CONFIG, 'w') as f:
            f.write(conteudo_conf)

        os.system("asterisk -rx 'dialplan reload'")
        os.system("asterisk -rx 'queue reload all'")
        
    except Exception as e:
        print(f"ERRO CRÍTICO ao escrever arquivos de fila: {e}")
