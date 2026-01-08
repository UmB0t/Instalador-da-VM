from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from app.modules.ferramentas import get_db_connection, registrar_log
from werkzeug.security import check_password_hash, generate_password_hash
from app.models import User
from app.modules.cadastros import listar_setores 

bp = Blueprint('auth', __name__)

# ==================================
# --- ROTAS WEB (FLASK) ---
# ==================================

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user_dict = verificar_credenciais(username, password)
        
        if user_dict:
            user = User(
                user_dict['id'], 
                user_dict['name'],
                user_dict['username'],
                user_dict['is_admin']
            )
            login_user(user)
            
            # LOG: Sucesso com IP
            ip_cliente = request.remote_addr
            registrar_log(user, "fez login no sistema.", f"IP: {ip_cliente}")
            
            return redirect(url_for('index'))
        else:
            # LOG EXTRA: Tentativa de falha (Segurança)
            # Passamos um objeto falso ou string pois não tem user logado
            registrar_log(f"Visitante ({request.remote_addr})", f"falhou ao tentar logar como '{username}'.")
            flash('Login ou senha inválidos', 'danger')

    return render_template('login.html')

@bp.route('/logout')
@login_required
def logout():
    registrar_log(current_user, "fez logout do sistema.")
    logout_user()
    return redirect(url_for('auth.login'))

# --- ROTAS DE GERENCIAMENTO DE USUÁRIOS ---

@bp.route('/usuarios', methods=['GET', 'POST'])
@login_required
def usuarios_index():
    if request.method == 'POST':
        login = request.form.get('login')
        nome = request.form.get('nome')
        senha = request.form.get('senha')
        sectors_id = request.form.get('sectors_id')
        
        sucesso, msg = criar_usuario_sistema(login, nome, senha, sectors_id)
        if sucesso:
            registrar_log(current_user, f"criou o usuário '{login}'.", f"Nome: {nome}")
            flash(msg, 'success')
        else:
            flash(msg, 'danger')
        return redirect(url_for('auth.usuarios_index'))

    lista_usuarios = listar_usuarios()
    lista_setores = listar_setores()
    
    return render_template('usuarios.html', 
                           usuarios=lista_usuarios, 
                           sectors=lista_setores,
                           edit_user=None)

@bp.route('/editar_usuario/<login>')
@login_required
def usuarios_editar(login):
    # Retorna tupla (login, name, sectors_id)
    edit_user = buscar_usuario_completo(login)
    if not edit_user:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('auth.usuarios_index'))
    
    lista_usuarios = listar_usuarios()
    lista_setores = listar_setores()

    return render_template('usuarios.html',
                           usuarios=lista_usuarios,
                           sectors=lista_setores,
                           edit_user=edit_user)

@bp.route('/salvar_edicao_usuario', methods=['POST'])
@login_required
def usuarios_salvar_edicao():
    login_original = request.form.get('login_original')
    novo_login = request.form.get('login')
    nome = request.form.get('nome')
    sectors_id = request.form.get('sectors_id')
    
    # 1. Busca dados ANTIGOS para comparação
    dados_antigos = buscar_usuario_completo(login_original) # Tupla: (login, name, sectors_id)
    
    sucesso, msg = atualizar_usuario_sistema(login_original, novo_login, nome, sectors_id)
    
    if sucesso and dados_antigos:
        # 2. Monta o Log de Diferenças (Diff)
        alteracoes = []
        antigo_login, antigo_nome, antigo_setor = dados_antigos
        
        # Converte setor para string para comparar (banco pode retornar int)
        antigo_setor = str(antigo_setor) if antigo_setor is not None else ""
        sectors_id = str(sectors_id) if sectors_id else ""

        if antigo_login != novo_login:
            alteracoes.append(f"Login: '{antigo_login}' -> '{novo_login}'")
        if antigo_nome != nome:
            alteracoes.append(f"Nome: '{antigo_nome}' -> '{nome}'")
        if antigo_setor != sectors_id:
            # Poderíamos buscar o nome do setor, mas o ID já ajuda
            alteracoes.append(f"Setor ID: '{antigo_setor or 'Nenhum'}' -> '{sectors_id or 'Nenhum'}'")
            
        if alteracoes:
            detalhe_log = " | ".join(alteracoes)
            registrar_log(current_user, f"editou o usuário '{login_original}'.", detalhe_log)
        
        flash(msg, 'success')
    elif not sucesso:
        flash(msg, 'danger')
        
    return redirect(url_for('auth.usuarios_index'))

@bp.route('/alternar_status_usuario/<login>', methods=['POST'])
@login_required
def usuarios_alternar_status(login):
    login_atual = current_user.get_id()
    
    # Busca status ATUAL antes de inverter
    status_atual = buscar_status_usuario(login) # True/False
    
    sucesso, msg = alternar_status_usuario(login, login_atual)
    
    if sucesso:
        # Se estava True (Ativo) virou Inativo, e vice-versa
        acao = "Desabilitou" if status_atual else "Habilitou"
        registrar_log(current_user, f"{acao} o usuário '{login}'.")
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
    return redirect(url_for('auth.usuarios_index'))

# ==================================
# --- LOGIN E SESSÃO ---
# ==================================

def verificar_credenciais(login, senha_fornecida):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT login, name, password, active FROM users WHERE login = %s", (login,))
        user_data = cur.fetchone()
        
        if user_data:
            db_login = user_data['login']
            db_name = user_data['name']
            db_password_hash = user_data['password']
            db_active = user_data['active']
            
            is_admin_flag = True if db_login == 'adm' else False
            
            if not db_active: return None
            
            if check_password_hash(db_password_hash, senha_fornecida):
                return {
                    'id': db_login, 
                    'name': db_name,
                    'username': db_login,
                    'is_admin': is_admin_flag
                }
        return None
    except Exception as e: 
        print(f"ERRO DE DB EM AUTENTICAÇÃO: {e}") 
        return None
    finally: conn.close()

def buscar_usuario_por_id(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT login, name FROM users WHERE login = %s", (user_id,))
        user_data = cur.fetchone()
        if user_data: return {'id': user_data['login'], 'name': user_data['name']}
        return None
    except: return None
    finally: conn.close()

# ==================================
# --- GERENCIAMENTO DE USUÁRIOS (DB) ---
# ==================================

def listar_usuarios():
    conn = get_db_connection()
    cur = conn.cursor()
    sql = """
        SELECT u.login, u.name, u.active, s.name as sector_name
        FROM users u
        LEFT JOIN sectors s ON u.sectors_id = s.id
        ORDER BY u.name ASC
    """
    cur.execute(sql)
    rows = cur.fetchall()
    conn.close()
    return rows

def buscar_usuario_completo(login):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT login, name, sectors_id FROM users WHERE login = %s", (login,))
        data = cur.fetchone()
        if data:
            return (data['login'], data['name'], data['sectors_id'])
        return None
    except: return None
    finally: conn.close()

def buscar_status_usuario(login):
    """Auxiliar para saber se está ativo ou inativo antes de trocar"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT active FROM users WHERE login = %s", (login,))
        data = cur.fetchone()
        return data['active'] if data else None
    except: return None
    finally: conn.close()

def criar_usuario_sistema(login, nome, senha, sectors_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT login FROM users WHERE login = %s", (login,))
        if cur.fetchone(): return False, "Este login já existe."
        if sectors_id == "": sectors_id = None
        senha_hash = generate_password_hash(senha)
        cur.execute("INSERT INTO users (login, name, password, active, sectors_id) VALUES (%s, %s, %s, true, %s)", (login, nome, senha_hash, sectors_id))
        conn.commit()
        return True, "Usuário criado com sucesso!"
    except Exception as e: conn.rollback(); return False, str(e)
    finally: conn.close()

def atualizar_usuario_sistema(login_original, novo_login, nome, sectors_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if login_original != novo_login:
            cur.execute("SELECT login FROM users WHERE login = %s", (novo_login,))
            if cur.fetchone(): return False, "O novo login já está em uso."

        if sectors_id == "": sectors_id = None
        
        cur.execute(
            "UPDATE users SET login = %s, name = %s, sectors_id = %s WHERE login = %s",
            (novo_login, nome, sectors_id, login_original)
        )
        conn.commit()
        return True, "Usuário atualizado com sucesso!"
    except Exception as e: conn.rollback(); return False, str(e)
    finally: conn.close()

def alternar_status_usuario(login, login_atual):
    if login == login_atual: return False, "Você não pode desabilitar seu próprio usuário."
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE users SET active = NOT active WHERE login = %s", (login,))
        conn.commit()
        return True, "Status alterado."
    except Exception as e: conn.rollback(); return False, str(e)
    finally: conn.close()

def alterar_senha_usuario(login, nova_senha):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        senha_hash = generate_password_hash(nova_senha)
        cur.execute("UPDATE users SET password = %s WHERE login = %s", (senha_hash, login))
        conn.commit()
        return True, "Senha alterada com sucesso!"
    except Exception as e: conn.rollback(); return False, str(e)
    finally: conn.close()
