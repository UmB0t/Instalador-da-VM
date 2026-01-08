import os
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.modules.ferramentas import get_db_connection, registrar_log
from werkzeug.utils import secure_filename

# Define o Blueprint
bp = Blueprint('layout', __name__)

UPLOAD_FOLDER = '/opt/application/app/static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg', 'ico'} 

# Configuração padrão (todos os caminhos de arquivo são None por segurança)
DEFAULT_SETTINGS = {
    'site_name': 'AsteriskWEB',
    'logo': None,
    'login_image': None,
    'favicon': None, 
    'primary_color': '#C2185B',
    'sidebar_bg': '#ffffff',
    'sidebar_text': '#333333'
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- ROTAS WEB (FLASK) ---

@bp.route('/layout', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        # Certifique-se de que o diretório de uploads existe
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)
        
        dados = request.form.to_dict()
        
        # 1. Captura estado ANTERIOR para comparação (antes de salvar)
        settings_antigas = get_settings()
        
        arquivo_logo = request.files.get('logo_file')
        arquivo_login = request.files.get('login_image_file')
        arquivo_favicon = request.files.get('favicon_file') 

        sucesso, msg = update_settings(dados, arquivo_logo, arquivo_login, arquivo_favicon) 
        
        if sucesso:
            # 2. Gera LOG de diferenças (Diff)
            alteracoes = []
            
            # Comparação de Textos/Cores
            # Verifica se mudou e se não é None (para evitar erro de comparação)
            nome_antigo = settings_antigas.get('site_name') or ''
            nome_novo = dados.get('site_name') or ''
            if nome_antigo != nome_novo:
                alteracoes.append(f"Nome Site: '{nome_antigo}' -> '{nome_novo}'")
            
            cor_pri_antiga = settings_antigas.get('primary_color')
            cor_pri_nova = dados.get('primary_color')
            if cor_pri_antiga != cor_pri_nova:
                alteracoes.append(f"Cor Primária: {cor_pri_antiga} -> {cor_pri_nova}")
                
            bg_antigo = settings_antigas.get('sidebar_bg')
            bg_novo = dados.get('sidebar_bg')
            if bg_antigo != bg_novo:
                alteracoes.append(f"Cor Menu: {bg_antigo} -> {bg_novo}")
                
            txt_antigo = settings_antigas.get('sidebar_text')
            txt_novo = dados.get('sidebar_text')
            if txt_antigo != txt_novo:
                alteracoes.append(f"Cor Texto Menu: {txt_antigo} -> {txt_novo}")

            # Comparação de Arquivos (Se enviou arquivo novo)
            if arquivo_logo and arquivo_logo.filename: alteracoes.append("Logo alterada")
            if arquivo_login and arquivo_login.filename: alteracoes.append("Imagem Login alterada")
            if arquivo_favicon and arquivo_favicon.filename: alteracoes.append("Favicon alterado")
            
            # Monta mensagem final
            detalhe_log = " | ".join(alteracoes) if alteracoes else "Nenhuma alteração visível"
            
            registrar_log(current_user, "atualizou o layout do sistema.", detalhe_log)
            
            flash(msg, 'success')
        else:
            flash(msg, 'danger')
        
        return redirect(url_for('layout.index')) 

    settings = get_settings()
    return render_template('layout.html', settings=settings)

# --- FUNÇÕES DE BANCO ---

def get_settings():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT site_name, logo_path, primary_color, sidebar_bg, sidebar_text, login_image_path, favicon_path 
            FROM settings 
            WHERE id = 1
        """)
        row = cur.fetchone()
        if row:
            # Garante que o valor NULL ou string vazia no banco seja Python None
            return {
                'site_name': row['site_name'],
                'logo': row['logo_path'] if row['logo_path'] else None,
                'primary_color': row['primary_color'],
                'sidebar_bg': row['sidebar_bg'],
                'sidebar_text': row['sidebar_text'],
                'login_image': row['login_image_path'] if row['login_image_path'] else None,
                'favicon': row['favicon_path'] if row['favicon_path'] else None
            }
        return DEFAULT_SETTINGS
    except Exception as e:
        print(f"Erro ao ler layout: {e}") 
        return DEFAULT_SETTINGS
    finally:
        conn.close()

def update_settings(dados, arquivo_logo, arquivo_login, arquivo_favicon):
    conn = get_db_connection()
    cur = conn.cursor()
    
    updates = {}
    
    try:
        # 1. ATUALIZA TEXTOS E CORES (SEMPRE FEITO NO INÍCIO)
        cur.execute("""
            UPDATE settings 
            SET site_name=%s, primary_color=%s, sidebar_bg=%s, sidebar_text=%s 
            WHERE id=1
        """, (dados['site_name'], dados['primary_color'], dados['sidebar_bg'], dados['sidebar_text']))
        
        if cur.rowcount == 0:
            cur.execute("""
                INSERT INTO settings (id, site_name, primary_color, sidebar_bg, sidebar_text)
                VALUES (1, %s, %s, %s, %s)
            """, (dados['site_name'], dados['primary_color'], dados['sidebar_bg'], dados['sidebar_text']))

        # ----------------------------------------------------
        # 2. PROCESSA LOGO do Dashboard (TENTA SALVAR PRIMEIRO)
        # ----------------------------------------------------
        if arquivo_logo and arquivo_logo.filename and allowed_file(arquivo_logo.filename):
            filename = secure_filename("dashboard_" + arquivo_logo.filename)
            caminho_salvo = os.path.join(UPLOAD_FOLDER, filename)
            
            arquivo_logo.save(caminho_salvo) 
            updates['logo_path'] = f"uploads/{filename}"

        # ----------------------------------------------------
        # 3. Processa IMAGEM DO LOGIN (TENTA SALVAR PRIMEIRO)
        # ----------------------------------------------------
        if arquivo_login and arquivo_login.filename and allowed_file(arquivo_login.filename):
            filename = secure_filename("login_hero_" + arquivo_login.filename)
            caminho_salvo = os.path.join(UPLOAD_FOLDER, filename)
            
            arquivo_login.save(caminho_salvo) 
            updates['login_image_path'] = f"uploads/{filename}"

        # ----------------------------------------------------
        # 4. PROCESSA FAVICON (TENTA SALVAR PRIMEIRO)
        # ----------------------------------------------------
        if arquivo_favicon and arquivo_favicon.filename and allowed_file(arquivo_favicon.filename):
            ext = arquivo_favicon.filename.rsplit('.', 1)[1].lower()
            # Gera nome de arquivo único para quebrar cache e evitar conflitos
            filename = secure_filename(f"favicon_{os.urandom(4).hex()}.{ext}")
            caminho_salvo = os.path.join(UPLOAD_FOLDER, filename)
            
            arquivo_favicon.save(caminho_salvo) 
            updates['favicon_path'] = f"uploads/{filename}"
        
        # -----------------------------------------------------------------
        # 5. COMMIT DE MÍDIA (SÓ ATUALIZA O BANCO SE NÃO HOUVE ERRO DE ESCRITA)
        # -----------------------------------------------------------------
        for key, value in updates.items():
            cur.execute(f"UPDATE settings SET {key}=%s WHERE id=1", (value,))

        conn.commit()
        return True, "Layout atualizado com sucesso! (Mídia e textos)"
        
    except Exception as e:
        conn.rollback()
        return False, f"Falha ao salvar a mídia ou atualizar o banco. Erro: {str(e)}"
    finally:
        conn.close()
