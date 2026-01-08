from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.modules.ferramentas import get_db_connection, registrar_log

bp = Blueprint('cadastros', __name__)

# ==============================================================================
#                                   CONTEXTOS
# ==============================================================================

@bp.route('/contextos', methods=['GET', 'POST'])
@login_required
def contextos_index():
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        nome = request.form.get('nome_contexto')
        desc = request.form.get('descricao_contexto')
        try:
            cur.execute("INSERT INTO contexts (name, description) VALUES (%s, %s)", (nome, desc))
            conn.commit()
            
            registrar_log(current_user, f"criou o contexto '{nome}'.", f"Desc: {desc}")
            
            flash('Contexto criado com sucesso!', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Erro ao criar contexto: {e}', 'danger')
        finally:
            conn.close()
        return redirect(url_for('cadastros.contextos_index'))

    cur.execute("SELECT id, name, description FROM contexts ORDER BY name ASC")
    lista = cur.fetchall()
    conn.close()
    
    contextos_dict = []
    for item in lista:
        if isinstance(item, tuple):
            contextos_dict.append({'id': item[0], 'name': item[1], 'description': item[2]})
        else:
            contextos_dict.append(item)

    return render_template('contextos.html', contextos=contextos_dict, edit_obj=None)

@bp.route('/contextos/editar/<id_ctx>', methods=['GET'])
@login_required
def contextos_editar(id_ctx):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, description FROM contexts WHERE id = %s", (id_ctx,))
    dado = cur.fetchone()
    
    cur.execute("SELECT id, name, description FROM contexts ORDER BY name ASC")
    lista = cur.fetchall()
    conn.close()

    obj_edit = None
    if dado:
        if isinstance(dado, tuple):
            obj_edit = {'id': dado[0], 'name': dado[1], 'description': dado[2]}
        else:
            obj_edit = dado

    contextos_dict = []
    for item in lista:
        if isinstance(item, tuple):
            contextos_dict.append({'id': item[0], 'name': item[1], 'description': item[2]})
        else:
            contextos_dict.append(item)

    return render_template('contextos.html', contextos=contextos_dict, edit_obj=obj_edit)

@bp.route('/contextos/salvar', methods=['POST'])
@login_required
def contextos_salvar():
    id_ctx = request.form.get('id_contexto')
    nome = request.form.get('nome_contexto')
    desc = request.form.get('descricao_contexto')
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Busca dados ANTIGOS para log
        cur.execute("SELECT name, description FROM contexts WHERE id = %s", (id_ctx,))
        antigo = cur.fetchone() # Retorna dict (RealDictCursor) ou tupla
        
        cur.execute("UPDATE contexts SET name=%s, description=%s WHERE id=%s", (nome, desc, id_ctx))
        conn.commit()
        
        # LOG DE DIFF
        alteracoes = []
        # Normaliza acesso (caso seja tupla ou dict)
        ant_nome = antigo['name'] if isinstance(antigo, dict) else antigo[0]
        ant_desc = antigo['description'] if isinstance(antigo, dict) else antigo[1]
        
        if ant_nome != nome:
            alteracoes.append(f"Nome: '{ant_nome}' -> '{nome}'")
        if ant_desc != desc:
            alteracoes.append(f"Desc: '{ant_desc}' -> '{desc}'")
            
        if alteracoes:
            detalhe = " | ".join(alteracoes)
            registrar_log(current_user, f"editou o contexto '{ant_nome}'.", detalhe)
        
        flash('Contexto atualizado!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Erro ao atualizar: {e}', 'danger')
    finally:
        conn.close()
        
    return redirect(url_for('cadastros.contextos_index'))

@bp.route('/contextos/excluir/<id_ctx>')
@login_required
def contextos_excluir(id_ctx):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Busca nome antes de excluir
        cur.execute("SELECT name FROM contexts WHERE id=%s", (id_ctx,))
        res = cur.fetchone()
        nome_ctx = res['name'] if isinstance(res, dict) else res[0]
        
        cur.execute("DELETE FROM contexts WHERE id=%s", (id_ctx,))
        conn.commit()
        
        registrar_log(current_user, f"excluiu o contexto '{nome_ctx}'.")
        
        flash('Contexto excluído.', 'success')
    except Exception as e:
        conn.rollback()
        flash('Erro: Não é possível excluir contexto em uso.', 'danger')
    finally:
        conn.close()
    return redirect(url_for('cadastros.contextos_index'))


# ==============================================================================
#                                     SETORES
# ==============================================================================

@bp.route('/setores', methods=['GET', 'POST'])
@login_required
def setores_index():
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        nome = request.form.get('nome_setor')
        desc = request.form.get('descricao_setor')
        try:
            cur.execute("INSERT INTO sectors (name, description) VALUES (%s, %s)", (nome, desc))
            conn.commit()
            
            registrar_log(current_user, f"criou o setor '{nome}'.", f"Desc: {desc}")
            
            flash('Setor criado!', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Erro: {e}', 'danger')
        finally:
            conn.close()
        return redirect(url_for('cadastros.setores_index'))

    cur.execute("SELECT id, name, description FROM sectors ORDER BY name ASC")
    lista = cur.fetchall()
    conn.close()

    setores_dict = []
    for item in lista:
        if isinstance(item, tuple):
            setores_dict.append({'id': item[0], 'name': item[1], 'description': item[2]})
        else:
            setores_dict.append(item)

    return render_template('setores.html', setores=setores_dict, edit_obj=None)

@bp.route('/setores/editar/<id_setor>', methods=['GET'])
@login_required
def setores_editar(id_setor):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, description FROM sectors WHERE id = %s", (id_setor,))
    dado = cur.fetchone()
    
    cur.execute("SELECT id, name, description FROM sectors ORDER BY name ASC")
    lista = cur.fetchall()
    conn.close()

    obj_edit = None
    if dado:
        if isinstance(dado, tuple):
            obj_edit = {'id': dado[0], 'name': dado[1], 'description': dado[2]}
        else:
            obj_edit = dado

    setores_dict = []
    for item in lista:
        if isinstance(item, tuple):
            setores_dict.append({'id': item[0], 'name': item[1], 'description': item[2]})
        else:
            setores_dict.append(item)

    return render_template('setores.html', setores=setores_dict, edit_obj=obj_edit)

@bp.route('/setores/salvar', methods=['POST'])
@login_required
def setores_salvar():
    id_setor = request.form.get('id_setor')
    nome = request.form.get('nome_setor')
    desc = request.form.get('descricao_setor')
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Busca dados ANTIGOS para log
        cur.execute("SELECT name, description FROM sectors WHERE id = %s", (id_setor,))
        antigo = cur.fetchone()
        
        cur.execute("UPDATE sectors SET name=%s, description=%s WHERE id=%s", (nome, desc, id_setor))
        conn.commit()
        
        # LOG DE DIFF
        alteracoes = []
        ant_nome = antigo['name'] if isinstance(antigo, dict) else antigo[0]
        ant_desc = antigo['description'] if isinstance(antigo, dict) else antigo[1]
        
        if ant_nome != nome:
            alteracoes.append(f"Nome: '{ant_nome}' -> '{nome}'")
        if ant_desc != desc:
            alteracoes.append(f"Desc: '{ant_desc}' -> '{desc}'")
            
        if alteracoes:
            detalhe = " | ".join(alteracoes)
            registrar_log(current_user, f"editou o setor '{ant_nome}'.", detalhe)
        
        flash('Setor atualizado!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Erro: {e}', 'danger')
    finally:
        conn.close()
        
    return redirect(url_for('cadastros.setores_index'))

@bp.route('/setores/excluir/<id_setor>')
@login_required
def setores_excluir(id_setor):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Busca nome para log
        cur.execute("SELECT name FROM sectors WHERE id=%s", (id_setor,))
        res = cur.fetchone()
        nome_setor = res['name'] if isinstance(res, dict) else res[0]
        
        cur.execute("DELETE FROM sectors WHERE id=%s", (id_setor,))
        conn.commit()
        
        registrar_log(current_user, f"excluiu o setor '{nome_setor}'.")
        
        flash('Setor excluído.', 'success')
    except Exception as e:
        conn.rollback()
        flash('Erro: Setor em uso.', 'danger')
    finally:
        conn.close()
    return redirect(url_for('cadastros.setores_index'))

# ==============================================================================
#                       FUNÇÕES AUXILIARES
# ==============================================================================

def listar_setores():
    """Função auxiliar usada pelo módulo de usuários/auth"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM sectors ORDER BY name ASC")
    rows = cur.fetchall()
    conn.close()
    
    lista = []
    for r in rows:
        if isinstance(r, tuple):
            lista.append({'id': r[0], 'name': r[1]})
        else:
            lista.append({'id': r['id'], 'name': r['name']})
    return lista

def listar_contextos():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM contexts ORDER BY name ASC")
    rows = cur.fetchall()
    conn.close()
    
    lista = []
    for r in rows:
        if isinstance(r, tuple):
            lista.append({'id': r[0], 'name': r[1]})
        else:
            lista.append({'id': r['id'], 'name': r['name']})
    return lista
