# Arquivo: /opt/application/app/routes/relatorios.py
from flask import Blueprint, render_template, request
from flask_login import login_required
from datetime import date
from app.models import Cdr, Fila # Importa dos novos modelos
from app.extensions import db

# Cria o Blueprint (um pedaço da aplicação)
bp = Blueprint('relatorios', __name__)

@bp.route('/relatorios')
@login_required
def index():
    # 1. Filtros de Data
    data_inicio = request.args.get('data_inicio', date.today().strftime('%Y-%m-%d'))
    data_fim = request.args.get('data_fim', date.today().strftime('%Y-%m-%d'))
    
    # 2. Outros Filtros
    origem = request.args.get('origem')
    destino = request.args.get('destino')
    fila_id = request.args.get('fila')
    status_filtro = request.args.get('status')

    # 3. Construção da Query
    query = Cdr.query.filter(
        Cdr.calldate >= f"{data_inicio} 00:00:00",
        Cdr.calldate <= f"{data_fim} 23:59:59"
    )

    if origem:
        query = query.filter(Cdr.src.ilike(f"%{origem}%"))
    
    if destino:
        query = query.filter(Cdr.dst.ilike(f"%{destino}%"))
        
    if fila_id:
        fila_obj = Fila.query.get(fila_id)
        if fila_obj:
            query = query.filter(Cdr.dcontext == fila_obj.name) 

    if status_filtro:
        if status_filtro == 'atendida':
            query = query.filter(Cdr.disposition == 'ANSWERED')
        elif status_filtro == 'perdida':
            query = query.filter(Cdr.disposition != 'ANSWERED')

    # 4. Executa
    chamadas = query.order_by(Cdr.calldate.desc()).all()
    filas = Fila.query.all()

    return render_template('relatorios.html', 
                           chamadas=chamadas, 
                           filas=filas,
                           data_inicio=data_inicio,
                           data_fim=data_fim)
