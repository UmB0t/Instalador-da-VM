import functools
from flask_login import login_required
from flask import Blueprint, render_template, request, url_for

# Define o Blueprint
bp = Blueprint('config', __name__)

@bp.route('/config')
@login_required
def index():
    """
    Página de índice central para todas as opções de configuração.
    """
    # Usaremos esta lista para renderizar os cards de opções no template.
    config_options = [
        {
            'title': 'Usuários e Permissões',
            'description': 'Gerenciar contas de acesso, redefinir senhas e definir níveis de permissão.',
            'icon': 'fas fa-users',
            'url': url_for('auth.usuarios_index') # Rota existente de Usuários
        },
        {
            'title': 'Filas de Atendimento',
            'description': 'Configuração de grupos de atendimento, agentes e estratégias de toque.',
            'icon': 'fas fa-phone-alt',
            'url': url_for('filas.index') # Rota existente de Filas
        },
        {
            'title': 'Ramais',
            'description': 'Gerenciamento de ramais SIP e suas configurações (contexto, senha, etc.).',
            'icon': 'fas fa-phone-square-alt',
            'url': url_for('ramais.index') # Rota existente de Ramais
        },
        {
            'title': 'Rotas Internas',
            'description': 'Mapeamento de prefixos e regras de roteamento dentro do PBX.',
            'icon': 'fas fa-route',
            'url': url_for('rotas.index') # Rota existente de Rotas
        },
        {
            'title': 'Setores e Contextos',
            'description': 'Cadastro e organização de setores e contextos de discagem do PBX.',
            'icon': 'fas fa-sitemap',
            'url': url_for('cadastros.setores_index') # Rota existente de Setores
        },
        {
            'title': 'Layout e Aparência',
            'description': 'Personalizar cores, logos e o Favicon do sistema.',
            'icon': 'fas fa-palette',
            'url': url_for('layout.index') # Rota existente de Layout
        }
    ]
    return render_template('config_index.html', config_options=config_options)
