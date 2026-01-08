# Arquivo: /opt/application/app/models.py

from flask_login import UserMixin
from app.modules.ferramentas import get_db_connection
from werkzeug.security import generate_password_hash, check_password_hash

# 1. CLASSE USER (Obrigatória para Flask-Login)
class User(UserMixin):
    # Aceita os 4 argumentos que o auth.py agora envia
    def __init__(self, id, name, username, is_admin=False):
        self.id = id
        self.name = name
        self.username = username
        self.is_admin = is_admin
    
    # Métodos da classe...


# 2. FUNÇÃO OBRIGATÓRIA PARA O user_loader
def get_user_by_id(user_id):
    """Busca um usuário no banco de dados dado o user_id (que é o login/ID da sessão)."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # CORREÇÃO DEFINITIVA: A consulta SQL SÓ seleciona colunas existentes (login e name).
        # Removemos 'is_admin' do SQL para evitar o erro.
        cur.execute("SELECT login, name FROM users WHERE login = %s", (user_id,))
        row = cur.fetchone()
        
        if row:
            # Lógica: Se o login for 'adm', ele é considerado administrador.
            is_admin_flag = True if row['login'] == 'adm' else False
            
            return User(
                id=row['login'],          # ID da sessão (usado pelo Flask-Login)
                name=row['name'], 
                username=row['login'],    # O 'username' do objeto é o 'login' do banco
                is_admin=is_admin_flag    # Flag definido no Python
            )
        return None
    except Exception as e:
        # O print nos logs de erro agora deve ser limpo, a menos que haja outro problema de DB.
        print(f"Erro ao buscar usuário por ID: {e}")
        return None
    finally:
        conn.close()
