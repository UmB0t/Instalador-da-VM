from flask import Blueprint, render_template, request, url_for, flash, send_file, redirect, Response, stream_with_context
from flask_login import login_required
from app.modules.ferramentas import get_db_connection
import datetime
import os
import glob
import math
import subprocess # Necessário para o FFmpeg

bp = Blueprint('relatorios', __name__, url_prefix='/relatorios')

# --- CONFIGURAÇÃO DE GRAVAÇÕES ---
DIR_GRAVACOES = '/var/spool/asterisk/monitor'

def segundos_para_tempo(segundos):
    try:
        seg = int(segundos)
    except (ValueError, TypeError):
        seg = 0
    m, s = divmod(seg, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def montar_filtro_sql(data_inicio, data_fim, origem, destino, fila, tipo, status):
    filtro = []
    params = []

    # Filtro de Data
    if data_inicio and data_fim:
        try:
            d_ini = data_inicio
            d_fim = data_fim
            # Garante formato YYYY-MM-DD
            if '/' in data_inicio:
                d_ini = datetime.datetime.strptime(data_inicio, '%d/%m/%Y').strftime('%Y-%m-%d')
            if '/' in data_fim:
                d_fim = datetime.datetime.strptime(data_fim, '%d/%m/%Y').strftime('%Y-%m-%d')

            filtro.append("c.calldate_start::TIMESTAMP >= %s::TIMESTAMP AND c.calldate_start::TIMESTAMP <= %s::TIMESTAMP")
            params.append(f"{d_ini} 00:00:00")
            params.append(f"{d_fim} 23:59:59")
        except ValueError:
            pass
    
    # Filtro de Origem
    if origem:
        filtro.append("c.src ILIKE %s")
        params.append(f"%{origem}%")

    # Filtro de Destino
    if destino:
        filtro.append("c.dst ILIKE %s")
        params.append(f"%{destino}%")

    # Filtro de Fila (queue_id)
    if fila and fila.isdigit():
        filtro.append("c.queue_id = %s")
        params.append(fila)

    # Filtro de Tipo (Baseado na coluna call_type)
    if tipo:
        filtro.append("c.call_type = %s") 
        params.append(tipo)

    # Filtro de Status (Baseado na coluna disposition)
    if status:
        filtro.append("c.disposition = %s")
        params.append(status)

    where_clause = " WHERE " + " AND ".join(filtro) if filtro else ""
    return where_clause, params

def contar_total_registros(where_clause, params):
    conn = get_db_connection()
    cur = conn.cursor()
    sql = f"SELECT COUNT(*) FROM cdr c {where_clause}"
    cur.execute(sql, tuple(params))
    total = cur.fetchone()
    conn.close()
    
    if isinstance(total, tuple): return total[0]
    return total['count'] 

def buscar_relatorio_paginado(where_clause, params, limit, offset):
    conn = get_db_connection()
    cur = conn.cursor()
    
    sql = f"""
        SELECT 
          c.uniqueid, c.src AS origem, c.dst AS destino,
          c.duration AS duracao_total, c.billsec AS duracao_falada,
          c.disposition AS status,
          TO_CHAR(c.calldate_start, 'DD/MM/YYYY HH24:MI:SS') AS data_inicio,
          TO_CHAR(c.calldate_answer, 'DD/MM/YYYY HH24:MI:SS') AS data_atendimento,
          TO_CHAR(c.calldate_end, 'DD/MM/YYYY HH24:MI:SS') AS data_fim,
          c.call_type AS tipo, 
          q.name AS fila
        FROM cdr c
        LEFT JOIN queues q ON q.id = c.queue_id
        {where_clause}
        ORDER BY c.calldate_start DESC
        LIMIT %s OFFSET %s
    """
    
    params_paginacao = params + [limit, offset]
    cur.execute(sql, tuple(params_paginacao))
    rows = cur.fetchall()
    
    resultado = []
    if rows:
        is_tuple = isinstance(rows[0], tuple)
        colunas = [desc[0] for desc in cur.description] if is_tuple else []

        for row in rows:
            r = dict(zip(colunas, row)) if is_tuple else row
            
            st = r.get('status')
            if st == 'ANSWERED': st_fmt = 'Atendida'
            elif st == 'NO ANSWER': st_fmt = 'Não Atendida'
            elif st == 'BUSY': st_fmt = 'Ocupado'
            elif st == 'FAILED': st_fmt = 'Falhou'
            else: st_fmt = st
            
            resultado.append({
                'uniqueid': r.get('uniqueid') or '',
                'origem': r.get('origem') or '-',
                'destino': r.get('destino') or '-',
                'duracao_total': segundos_para_tempo(r.get('duracao_total')),
                'duracao_falada': segundos_para_tempo(r.get('duracao_falada')),
                'status': st_fmt,
                'fila': r.get('fila') or '-',
                'inicio': r.get('data_inicio') or '-',
                'atendimento': r.get('data_atendimento') or '-',
                'fim': r.get('data_fim') or '-',
                'tipo': r.get('tipo') or 'Outros'
            })
            
    conn.close()
    return resultado

def listar_filas():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM queues ORDER BY name")
    rows = cur.fetchall()
    conn.close()
    filas = []
    for r in rows:
        if isinstance(r, tuple): filas.append({'id': r[0], 'name': r[1]})
        else: filas.append({'id': r['id'], 'name': r['name']})
    return filas

# --- ROTAS ---

@bp.route('/', methods=['GET'])
@login_required
def index():
    # 1. Parâmetros de Filtro
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    
    if not data_inicio:
        today = datetime.date.today()
        first_day = today.replace(day=1)
        data_inicio = first_day.strftime('%Y-%m-%d')
        
    if not data_fim:
        today = datetime.date.today()
        data_fim = today.strftime('%Y-%m-%d')
    
    origem = request.args.get('origem', '')
    destino = request.args.get('destino', '')
    fila_id = request.args.get('fila', '')
    
    # NOVOS FILTROS
    filtro_tipo = request.args.get('filtro_tipo', '')
    filtro_status = request.args.get('filtro_status', '')

    # 2. Parâmetros de Paginação
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    if per_page not in [10, 25, 50, 100]: per_page = 10
    
    offset = (page - 1) * per_page

    relatorio = []
    total_registros = 0
    total_pages = 0
    
    try:
        where_clause, params = montar_filtro_sql(data_inicio, data_fim, origem, destino, fila_id, filtro_tipo, filtro_status)
        total_registros = contar_total_registros(where_clause, params)
        relatorio = buscar_relatorio_paginado(where_clause, params, per_page, offset)
        
        if total_registros > 0:
            total_pages = math.ceil(total_registros / per_page)
        
        if (origem or destino or filtro_tipo or filtro_status) and not relatorio:
            flash("Nenhum registro encontrado para o filtro.", "warning")
            
    except Exception as e:
        flash(f"Erro ao gerar relatório: {str(e)}", "danger")
        print(f"Erro SQL: {e}")

    filas_opcoes = listar_filas()

    return render_template('relatorios.html', 
                          relatorio=relatorio, 
                          data_inicio=data_inicio, 
                          data_fim=data_fim,
                          filas=filas_opcoes,
                          page=page,
                          per_page=per_page,
                          total_pages=total_pages,
                          total_registros=total_registros,
                          filtro_tipo=filtro_tipo,
                          filtro_status=filtro_status)

# ROTA PARA DOWNLOAD (Arquivo original)
@bp.route('/gravacao/<uniqueid>')
@login_required
def baixar_gravacao(uniqueid):
    if not uniqueid or uniqueid == '-':
        flash("Chamada sem ID de gravação.", "warning")
        return redirect(url_for('relatorios.index'))

    padrao = os.path.join(DIR_GRAVACOES, f"*{uniqueid}*.*")
    arquivos = glob.glob(padrao)

    if arquivos:
        arquivo_encontrado = arquivos[0]
        try:
            return send_file(arquivo_encontrado, as_attachment=True)
        except Exception as e:
            flash(f"Erro ao baixar arquivo: {e}", "danger")
    else:
        flash("Arquivo de áudio não encontrado no servidor.", "secondary")
    
    return redirect(request.referrer or url_for('relatorios.index'))

# --- NOVA ROTA PARA STREAMING (Com Conversão FFmpeg) ---
@bp.route('/stream/<uniqueid>')
@login_required
def stream_gravacao(uniqueid):
    if not uniqueid or uniqueid == '-':
        return "ID inválido", 404

    padrao = os.path.join(DIR_GRAVACOES, f"*{uniqueid}*.*")
    arquivos = glob.glob(padrao)

    if not arquivos:
        return "Arquivo não encontrado", 404

    arquivo_origem = arquivos[0]

    # Função Geradora: Executa o FFmpeg e transmite os dados
    def generate():
        # Comando para converter para MP3 (-f mp3) na saída padrão (-)
        # -ab 64k: bitrate leve para voz
        # -v error: apenas erros graves no log
        comando = ['ffmpeg', '-i', arquivo_origem, '-f', 'mp3', '-ab', '64k', '-v', 'error', '-']
        
        processo = subprocess.Popen(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        try:
            while True:
                # Lê blocos de 4KB do FFmpeg
                data = processo.stdout.read(4096)
                if not data:
                    break
                yield data
        finally:
            # Garante que o processo morra se a conexão fechar
            if processo.poll() is None:
                processo.kill()

    # Retorna o stream como audio/mpeg (MP3)
    return Response(stream_with_context(generate()), mimetype="audio/mpeg")
