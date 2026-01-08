import os
from flask import Flask, render_template, g
from flask_login import LoginManager, current_user, login_required
from app.modules.ferramentas import get_db_connection
from app.modules import layout as LayoutModule

# Importação dos Blueprints
from app.modules import relatorios as RelatoriosBP
from app.modules import config_routes as ConfigBP
from app.modules import auth as AuthBP
from app.modules import filas as FilasBP
from app.modules import ramais as RamaisBP
from app.modules import rotas as RotasBP
from app.modules import cadastros as CadastrosBP
from app.modules import admin_monitor as AdminMonitorBP
from app.modules import troncos as TroncosBP
from app.modules import monitoramento as MonitoramentoBP # <--- ADICIONADO AQUI

# Funções do Login Manager
from app.models import get_user_by_id, User

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Por favor, faça login para acessar esta página.'

@login_manager.user_loader
def load_user(user_id):
    """Carrega o usuário dado seu ID."""
    return get_user_by_id(user_id)

# ----------------------------------------------------------------------

def create_app():
    app = Flask(__name__)
    
    # Configuração Secreta
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'sua_chave_secreta_padrao_muito_segura')
    
    # Inicializa Login Manager
    login_manager.init_app(app)

    # Context Processor para o layout
    @app.context_processor
    def inject_settings():
        """Injeta as configurações de layout em todos os templates."""
        return {'settings': LayoutModule.get_settings()}

    # Antes de cada requisição, define a conexão de banco de dados
    @app.before_request
    def before_request():
        g.db = get_db_connection()

    # Após cada requisição, fecha a conexão
    @app.teardown_request
    def teardown_request(exception):
        db = g.pop('db', None)
        if db is not None:
            db.close()

    # ---------------------------------------------------
    # ROTAS E BLUEPRINTS
    # ---------------------------------------------------

    # Rota Raiz
    @app.route('/')
    @login_required
    def index():
        return render_template('dashboard.html')

    # Registro de Blueprints
    app.register_blueprint(AuthBP.bp)
    app.register_blueprint(RelatoriosBP.bp)
    app.register_blueprint(LayoutModule.bp)
    app.register_blueprint(FilasBP.bp)
    app.register_blueprint(RamaisBP.bp)
    app.register_blueprint(RotasBP.bp)
    app.register_blueprint(CadastrosBP.bp)
    app.register_blueprint(ConfigBP.bp)
    app.register_blueprint(AdminMonitorBP.bp)
    app.register_blueprint(TroncosBP.bp)
    app.register_blueprint(MonitoramentoBP.bp)

    return app
