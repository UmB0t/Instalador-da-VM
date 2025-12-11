#!/bin/bash

# --- CONFIGURAÇÕES ---
DB_NAME="asterisk"
DB_USER="asterisk"
DB_PASS="asterisk"

if [ "$EUID" -ne 0 ]; then 
  echo "Por favor, execute como root (sudo)."
  exit
fi

echo "=================================================="
echo " INICIANDO AUTOMAÇÃO DO BANCO DE DADOS ASTERISK"
echo "=================================================="

echo "[1/4] Recriando Usuário e Banco de Dados..."
su - postgres -c "psql -c \"DROP DATABASE IF EXISTS $DB_NAME;\""
su - postgres -c "psql -c \"DROP USER IF EXISTS $DB_USER;\""
su - postgres -c "psql -c \"CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';\""
su - postgres -c "psql -c \"CREATE DATABASE $DB_NAME OWNER $DB_USER;\""

echo "[2/4] Criando Tabelas e Estruturas..."

SQL_COMMANDS=$(cat <<EOF
-- Conectar no banco criado
\c $DB_NAME

-- ==========================================
-- 1. TABELAS INDEPENDENTES (BASE)
-- ==========================================

-- Contextos
CREATE TABLE contexts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(80) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Setores
CREATE TABLE sectors (
    id SERIAL PRIMARY KEY,
    name VARCHAR(80) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Filas (Queues)
CREATE TABLE queues (
    id SERIAL PRIMARY KEY,
    name VARCHAR(128) NOT NULL UNIQUE,
    description VARCHAR(128),
    musiconhold VARCHAR(128) DEFAULT 'default',
    strategy VARCHAR(50) DEFAULT 'rrmemory',
    timeout INTEGER DEFAULT 15,
    retry INTEGER DEFAULT 5,
    wrapuptime INTEGER DEFAULT 0,
    maxlen INTEGER DEFAULT 0,
    joinempty VARCHAR(50) DEFAULT 'yes',
    leavewhenempty VARCHAR(50) DEFAULT 'no',
    time_condition_id INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ==========================================
-- 2. TABELAS DEPENDENTES
-- ==========================================

-- Extensions (Ramais)
CREATE TABLE extensions (
    id SERIAL PRIMARY KEY,
    extension VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(80),
    secret VARCHAR(80),
    transport VARCHAR(20) DEFAULT 'udp',
    technology VARCHAR(20) DEFAULT 'PJSIP',
    context_id INTEGER NOT NULL REFERENCES contexts(id),
    sectors_id INTEGER REFERENCES sectors(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_extensions_exten ON extensions(extension);

-- CDR (Relatórios de Chamadas)
CREATE TABLE cdr (
    id SERIAL PRIMARY KEY,
    uniqueid VARCHAR(150),
    accountcode VARCHAR(40),
    src VARCHAR(80),
    dst VARCHAR(80),
    dcontext VARCHAR(80),
    clid VARCHAR(80),
    channel VARCHAR(80),
    dstchannel VARCHAR(80),
    duration INTEGER,
    billsec INTEGER,
    disposition VARCHAR(40),
    queue_id INTEGER REFERENCES queues(id), -- FK para Queues
    calldate_start TIMESTAMP WITH TIME ZONE,
    calldate_answer TIMESTAMP WITH TIME ZONE,
    calldate_end TIMESTAMP WITH TIME ZONE,
    call_type VARCHAR(20),
    lastapp VARCHAR(80),
    lastdata VARCHAR(255),
    amaflags INTEGER,
    userfield VARCHAR(255),
    peeraccount VARCHAR(80),
    linkedid VARCHAR(150),
    sequence INTEGER
);

-- Índices do CDR
CREATE INDEX idx_cdr_calldate_start ON cdr(calldate_start);
CREATE INDEX idx_cdr_dst ON cdr(dst);
CREATE INDEX idx_cdr_src ON cdr(src);
CREATE INDEX idx_cdr_uniqueid ON cdr(uniqueid);

-- ==========================================
-- 3. INSERINDO DADOS PADRÃO (SEEDS)
-- ==========================================

-- Contexto Padrão
INSERT INTO contexts (name, description) VALUES ('INTERNAL', 'Contexto Interno Padrão');

-- Setor Padrão
INSERT INTO sectors (name, description) VALUES ('TI', 'Tecnologia da Informação');

-- Fila Padrão
INSERT INTO queues (name, description, strategy, timeout) VALUES ('fila_geral', 'Fila Geral de Atendimento', 'rrmemory', 20);

-- ==========================================
-- 4. PERMISSÕES FINAIS
-- ==========================================
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $DB_USER;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $DB_USER;

EOF
)

# Executa o SQL como usuário postgres
su - postgres -c "psql -d $DB_NAME -c \"$SQL_COMMANDS\""

echo "=================================================="
echo " CONCLUÍDO COM SUCESSO!"
echo "=================================================="
echo "Verificação rápida das tabelas criadas:"
su - postgres -c "psql -d $DB_NAME -c '\dt'"
echo "Verificação dos dados padrão:"
su - postgres -c "psql -d $DB_NAME -c 'SELECT * FROM contexts; SELECT * FROM sectors; SELECT * FROM queues;'"
