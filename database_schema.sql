-- ==========================================
-- ESTRUTURA DO BANCO DE DADOS - ASTERISK WEB
-- ==========================================

-- GRUPO 1: INFRAESTRUTURA BÁSICA

CREATE TABLE contexts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(80) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE sectors (
    id SERIAL PRIMARY KEY,
    name VARCHAR(80) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

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
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status BOOLEAN DEFAULT TRUE
);

-- GRUPO 2: TELEFONIA (CORE)

CREATE TABLE trunks (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    username VARCHAR(80),
    secret VARCHAR(80),
    host VARCHAR(100) NOT NULL,
    port INTEGER DEFAULT 5060,
    technology VARCHAR(10) NOT NULL,
    register BOOLEAN DEFAULT FALSE,
    context VARCHAR(50) DEFAULT 'ENTRADA_GERAL',
    transport VARCHAR(50) DEFAULT 'transport-UDP',
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    register_username VARCHAR(80),
    register_secret VARCHAR(80)
);

CREATE TABLE extensions (
    extension VARCHAR(20) PRIMARY KEY, 
    name VARCHAR(80),
    secret VARCHAR(80),
    transport VARCHAR(20) DEFAULT 'udp',
    technology VARCHAR(20) DEFAULT 'PJSIP',
    context_id INTEGER NOT NULL REFERENCES contexts(id),
    sectors_id INTEGER REFERENCES sectors(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE routes (
    id SERIAL PRIMARY KEY,
    dialing VARCHAR(100) NOT NULL,
    type VARCHAR(50) NOT NULL,
    destination VARCHAR(100) NOT NULL
);

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
    queue_id INTEGER REFERENCES queues(id),
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
CREATE INDEX idx_cdr_calldate_start ON cdr(calldate_start);

-- GRUPO 3: APLICAÇÃO WEB

CREATE TABLE settings (
    id SERIAL PRIMARY KEY,
    site_name VARCHAR(100) DEFAULT 'AsteriskWEB',
    logo_path VARCHAR(255),
    primary_color VARCHAR(20) DEFAULT '#C2185B',
    sidebar_bg VARCHAR(20) DEFAULT '#ffffff',
    sidebar_text VARCHAR(20) DEFAULT '#333333',
    login_image_path VARCHAR(255),
    favicon_path VARCHAR(255)
);

-- GRUPO 4: USUÁRIOS E PERMISSÕES

CREATE TABLE users (
    login VARCHAR(80) PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    password VARCHAR(255) NOT NULL,
    sector VARCHAR(80),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    active BOOLEAN DEFAULT TRUE,
    sectors_id INTEGER REFERENCES sectors(id) ON DELETE SET NULL
);

CREATE TABLE user_extensions (
    user_id VARCHAR(80) REFERENCES users(login) ON DELETE CASCADE,
    extension_id VARCHAR(20) REFERENCES extensions(extension) ON DELETE CASCADE,
    PRIMARY KEY (user_id, extension_id)
);

CREATE TABLE user_sectors (
    user_id VARCHAR(80) REFERENCES users(login) ON DELETE CASCADE,
    sector_id INTEGER REFERENCES sectors(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, sector_id)
);

CREATE TABLE user_contexts (
    user_id VARCHAR(80) REFERENCES users(login) ON DELETE CASCADE,
    context_id INTEGER REFERENCES contexts(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, context_id)
);

CREATE TABLE user_queues (
    user_id VARCHAR(80) REFERENCES users(login) ON DELETE CASCADE,
    queue_id INTEGER REFERENCES queues(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, queue_id)
);

-- INSERINDO DADOS PADRÃO (SEEDS)

INSERT INTO contexts (name, description) VALUES ('INTERNO', 'Contexto Interno Padrão');
INSERT INTO sectors (name, description) VALUES ('INTERNO', 'Setor Interno Padrão');
INSERT INTO queues (name, description, strategy) VALUES ('fila_suporte', 'Suporte Técnico', 'rrmemory');
INSERT INTO queues (name, description, strategy) VALUES ('Template', 'Fila Template', 'rrmemory');

INSERT INTO settings (site_name, primary_color) VALUES ('AsteriskWEB', '#C2185B');

INSERT INTO extensions (extension, name, secret, context_id, technology) 
VALUES ('1100', 'Ramal 1100', '1234', 1, 'PJSIP');
INSERT INTO extensions (extension, name, secret, context_id, technology) 
VALUES ('1101', 'Ramal 1101', '1234', 1, 'PJSIP');

INSERT INTO users (login, name, password, sector, sectors_id) 
VALUES ('adm', 'Administrador Padrão', '@Sam62dan', 'INTERNO', 1);

INSERT INTO user_extensions (user_id, extension_id) VALUES ('adm', '1100');
INSERT INTO user_sectors (user_id, sector_id) VALUES ('adm', 1);
INSERT INTO user_queues (user_id, queue_id) VALUES ('adm', 1);

INSERT INTO trunks (name, host, technology, context) VALUES ('Trunk_Vivo', '192.168.1.100', 'pjsip', 'ENTRADA_GERAL');

INSERT INTO routes (dialing, type, destination) VALUES ('_0[1-9]XXXXXXXX', 'SIP', 'Trunk_Vivo');

-- PERMISSÕES FINAIS
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO asterisk;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO asterisk;
