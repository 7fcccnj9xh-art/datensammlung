-- ============================================================
-- Knowledge Collector – Vollständiges Datenbankschema
-- UGREEN NAS / MySQL 8.x
-- Erstellt: 2026-04-15
-- ============================================================

CREATE DATABASE IF NOT EXISTS knowledge_collector
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE knowledge_collector;

-- ============================================================
-- 1. THEMEN-VERWALTUNG
-- ============================================================
CREATE TABLE topics (
    id              INT UNSIGNED     AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(200)     NOT NULL,
    slug            VARCHAR(200)     NOT NULL UNIQUE,
    description     TEXT,
    category        VARCHAR(100),
    -- Scheduling-Typ: continuous=regelmäßig, sporadic=gelegentlich, once=einmalig
    schedule_type   ENUM('continuous','sporadic','once') NOT NULL DEFAULT 'sporadic',
    status          ENUM('active','paused','archived') NOT NULL DEFAULT 'active',
    -- Bevorzugter LLM-Provider für dieses Topic (NULL = globaler Default)
    llm_provider    ENUM('ollama','claude','openai','auto') DEFAULT NULL,
    llm_model       VARCHAR(100)     DEFAULT NULL,
    -- Suchkonfiguration als JSON
    -- Beispiel: {"keywords": ["raspberry pi"], "exclude": ["forum"], "sources": [1,2]}
    search_config   JSON,
    -- LLM-System-Prompt für dieses Topic
    system_prompt   TEXT,
    -- Tags als JSON-Array
    tags            JSON,
    -- Priorität 1 (höchste) bis 10 (niedrigste)
    priority        TINYINT UNSIGNED NOT NULL DEFAULT 5,
    created_at      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_researched DATETIME         DEFAULT NULL,

    INDEX idx_status   (status),
    INDEX idx_category (category),
    INDEX idx_schedule (schedule_type, status)
) ENGINE=InnoDB;

-- ============================================================
-- 2. INTERVALL-KONFIGURATION
-- ============================================================
CREATE TABLE research_intervals (
    id              INT UNSIGNED     AUTO_INCREMENT PRIMARY KEY,
    topic_id        INT UNSIGNED     NOT NULL,
    -- fixed=alle X Sekunden, cron=Cron-Expression, smart=KI-gesteuert
    interval_type   ENUM('fixed','cron','smart') NOT NULL DEFAULT 'fixed',
    -- Bei fixed: Intervall in Sekunden (z.B. 3600 = 1h, 86400 = 1d)
    interval_seconds INT UNSIGNED   DEFAULT NULL,
    -- Bei cron: Standard-Cron-Expression (5 Felder)
    cron_expression VARCHAR(100)     DEFAULT NULL,
    -- Nächste geplante Ausführung
    next_run        DATETIME         DEFAULT NULL,
    -- Letzte Ausführung
    last_run        DATETIME         DEFAULT NULL,
    last_run_status ENUM('success','failed','skipped') DEFAULT NULL,
    -- Aktiv/inaktiv unabhängig vom Topic-Status
    is_active       BOOLEAN          NOT NULL DEFAULT TRUE,
    -- Maximale Laufzeit in Sekunden (0 = kein Limit)
    timeout_seconds INT UNSIGNED     NOT NULL DEFAULT 300,
    created_at      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE,
    INDEX idx_next_run (next_run, is_active),
    INDEX idx_topic    (topic_id)
) ENGINE=InnoDB;

-- ============================================================
-- 3. QUELLEN
-- ============================================================
CREATE TABLE sources (
    id              INT UNSIGNED     AUTO_INCREMENT PRIMARY KEY,
    url             VARCHAR(2000)    NOT NULL,
    -- Normalisierte Basis-Domain für Rate-Limiting
    domain          VARCHAR(255)     NOT NULL,
    title           VARCHAR(500),
    description     TEXT,
    -- website, api, rss, pdf, youtube, github, custom
    source_type     ENUM('website','api','rss','pdf','youtube','github','custom')
                    NOT NULL DEFAULT 'website',
    -- Vertrauenswürdigkeit 0.0 (unbekannt) bis 1.0 (sehr vertrauenswürdig)
    trust_score     DECIMAL(3,2)     NOT NULL DEFAULT 0.50,
    -- Für API-Quellen: Auth-Informationen als JSON (Keys NICHT speichern, nur Schema)
    auth_config     JSON,
    -- HTTP-Header für diese Quelle als JSON
    custom_headers  JSON,
    -- Quell-spezifische Extraktions-Regeln als JSON
    -- {"content_selector": "article.main", "exclude": [".ads", "nav"]}
    extraction_config JSON,
    is_active       BOOLEAN          NOT NULL DEFAULT TRUE,
    first_seen      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_fetched    DATETIME         DEFAULT NULL,
    fetch_count     INT UNSIGNED     NOT NULL DEFAULT 0,
    error_count     INT UNSIGNED     NOT NULL DEFAULT 0,
    created_at      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_domain      (domain),
    INDEX idx_type        (source_type),
    INDEX idx_trust       (trust_score),
    INDEX idx_last_fetch  (last_fetched)
) ENGINE=InnoDB;

-- Verknüpfung Topic ↔ Quelle (bevorzugte Quellen pro Topic)
CREATE TABLE topic_sources (
    topic_id        INT UNSIGNED     NOT NULL,
    source_id       INT UNSIGNED     NOT NULL,
    -- Priorität innerhalb dieses Topics
    priority        TINYINT UNSIGNED NOT NULL DEFAULT 5,
    created_at      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (topic_id, source_id),
    FOREIGN KEY (topic_id)  REFERENCES topics(id)  ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ============================================================
-- 4. RECHERCHE-ERGEBNISSE
-- ============================================================
CREATE TABLE research_results (
    id              BIGINT UNSIGNED  AUTO_INCREMENT PRIMARY KEY,
    topic_id        INT UNSIGNED     NOT NULL,
    source_id       INT UNSIGNED     DEFAULT NULL,
    job_id          BIGINT UNSIGNED  DEFAULT NULL,
    -- Rohdaten: extrahierter HTML/Text
    raw_content     MEDIUMTEXT,
    -- Bereinigter Volltext
    clean_content   MEDIUMTEXT,
    -- LLM-generierte Zusammenfassung
    summary         TEXT,
    -- Welche neuen Informationen wurden gefunden (bei Update-Recherchen)
    delta_summary   TEXT,
    -- Metadaten aus der Quelle als JSON
    -- {"title": "...", "author": "...", "published": "...", "language": "de"}
    meta_data       JSON,
    -- Embedding-Vektor als JSON-Array (für spätere Semantiksuche)
    -- In Produktion: VECTOR-Typ oder separate Tabelle
    embedding       JSON,
    -- Versionsnummer (erhöht bei Updates)
    version         INT UNSIGNED     NOT NULL DEFAULT 1,
    -- Hash des clean_content für Duplikatserkennung
    content_hash    CHAR(64)         DEFAULT NULL,
    -- Sprache des Inhalts
    language        CHAR(5)          DEFAULT 'de',
    -- Relevanz-Score (0-1), gesetzt vom LLM
    relevance_score DECIMAL(3,2)     DEFAULT NULL,
    created_at      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (topic_id)  REFERENCES topics(id)  ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE SET NULL,
    INDEX idx_topic      (topic_id, created_at),
    INDEX idx_hash       (content_hash),
    INDEX idx_relevance  (relevance_score),
    INDEX idx_created    (created_at)
) ENGINE=InnoDB;

-- ============================================================
-- 5. STRUKTURIERTE DATEN (generisch)
-- ============================================================
CREATE TABLE structured_data (
    id              BIGINT UNSIGNED  AUTO_INCREMENT PRIMARY KEY,
    -- Datentyp-Bezeichner: 'energy', 'price', 'sensor', 'custom_xyz'
    data_type       VARCHAR(100)     NOT NULL,
    source_id       INT UNSIGNED     DEFAULT NULL,
    -- Flexibles JSON-Schema pro Datentyp
    data            JSON             NOT NULL,
    -- Zeitstempel der Daten (nicht des Imports!)
    data_timestamp  DATETIME         NOT NULL,
    -- Lokation/Kontext als JSON: {"lat": 47.99, "lon": 7.85, "name": "Freiburg"}
    location        JSON,
    created_at      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE SET NULL,
    INDEX idx_type_time  (data_type, data_timestamp),
    INDEX idx_data_time  (data_timestamp)
) ENGINE=InnoDB;

-- ============================================================
-- 6. LLM-KONFIGURATIONEN
-- ============================================================
CREATE TABLE llm_configs (
    id              INT UNSIGNED     AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(100)     NOT NULL UNIQUE,
    -- Provider: ollama, claude, openai, custom
    provider        ENUM('ollama','claude','openai','custom') NOT NULL,
    -- Modell-Name (z.B. 'llama3.2', 'claude-haiku-4-5-20251001', 'gpt-4o-mini')
    model_name      VARCHAR(100)     NOT NULL,
    -- API-Endpoint (bei Ollama oder custom)
    api_endpoint    VARCHAR(500)     DEFAULT NULL,
    -- Maximale Tokens für Antworten
    max_tokens      INT UNSIGNED     NOT NULL DEFAULT 2000,
    -- Temperatur
    temperature     DECIMAL(3,2)     NOT NULL DEFAULT 0.30,
    -- Monatliches Kosten-Budget in EUR (0 = kein Limit)
    monthly_budget_eur DECIMAL(8,2)  NOT NULL DEFAULT 0.00,
    -- Verbrauchte Kosten diesen Monat
    monthly_spent_eur  DECIMAL(8,2)  NOT NULL DEFAULT 0.00,
    -- Reset-Datum für Budget
    budget_reset_date DATE           DEFAULT NULL,
    -- Ist dies der System-Default?
    is_default      BOOLEAN          NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN          NOT NULL DEFAULT TRUE,
    -- Zusätzliche Provider-spezifische Config als JSON
    extra_config    JSON,
    created_at      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_provider (provider, is_active)
) ENGINE=InnoDB;

-- Kosten-Tracking pro LLM-Aufruf
CREATE TABLE llm_usage (
    id              BIGINT UNSIGNED  AUTO_INCREMENT PRIMARY KEY,
    llm_config_id   INT UNSIGNED     NOT NULL,
    job_id          BIGINT UNSIGNED  DEFAULT NULL,
    topic_id        INT UNSIGNED     DEFAULT NULL,
    -- Tokens
    input_tokens    INT UNSIGNED     NOT NULL DEFAULT 0,
    output_tokens   INT UNSIGNED     NOT NULL DEFAULT 0,
    -- Kosten in EUR
    cost_eur        DECIMAL(10,6)    NOT NULL DEFAULT 0.000000,
    -- Verwendeter Prompt-Typ
    prompt_type     VARCHAR(100)     DEFAULT NULL,
    -- Dauer in Millisekunden
    duration_ms     INT UNSIGNED     DEFAULT NULL,
    -- War Ergebnis aus Cache?
    from_cache      BOOLEAN          NOT NULL DEFAULT FALSE,
    created_at      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (llm_config_id) REFERENCES llm_configs(id) ON DELETE CASCADE,
    INDEX idx_config_time  (llm_config_id, created_at),
    INDEX idx_job          (job_id),
    INDEX idx_topic        (topic_id)
) ENGINE=InnoDB;

-- ============================================================
-- 7. JOB-AUSFÜHRUNGSPROTOKOLL
-- ============================================================
CREATE TABLE jobs (
    id              BIGINT UNSIGNED  AUTO_INCREMENT PRIMARY KEY,
    -- Interner Job-Bezeichner (eindeutig pro Lauf)
    job_key         VARCHAR(200)     NOT NULL,
    -- research, api_sync, on_demand, backup
    job_type        ENUM('research','api_sync','on_demand','backup','export')
                    NOT NULL,
    topic_id        INT UNSIGNED     DEFAULT NULL,
    -- Ausgelöst durch: scheduler, api, user, cron
    triggered_by    ENUM('scheduler','api','user','cron') NOT NULL DEFAULT 'scheduler',
    status          ENUM('queued','running','completed','failed','cancelled','timeout')
                    NOT NULL DEFAULT 'queued',
    -- Fortschritt 0-100
    progress_pct    TINYINT UNSIGNED NOT NULL DEFAULT 0,
    -- Kurze Status-Nachricht für UI
    status_message  VARCHAR(500)     DEFAULT NULL,
    -- Fehler-Detail
    error_detail    TEXT             DEFAULT NULL,
    -- Performance-Metriken als JSON
    -- {"urls_fetched": 5, "tokens_used": 1200, "new_content": true}
    metrics         JSON,
    -- Job-Parameter (wie übergeben)
    parameters      JSON,
    started_at      DATETIME         DEFAULT NULL,
    completed_at    DATETIME         DEFAULT NULL,
    -- Laufzeit in Sekunden
    duration_seconds INT UNSIGNED    DEFAULT NULL,
    created_at      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_type_status  (job_type, status),
    INDEX idx_topic        (topic_id),
    INDEX idx_created      (created_at),
    INDEX idx_status       (status, created_at)
) ENGINE=InnoDB;

-- ============================================================
-- 8. BENACHRICHTIGUNGEN
-- ============================================================
CREATE TABLE notifications (
    id              BIGINT UNSIGNED  AUTO_INCREMENT PRIMARY KEY,
    -- alert, info, warning, error
    level           ENUM('info','warning','alert','error') NOT NULL DEFAULT 'info',
    title           VARCHAR(300)     NOT NULL,
    message         TEXT,
    -- Quelle: topic, job, system, llm_budget
    source_type     VARCHAR(50)      DEFAULT NULL,
    source_id       VARCHAR(50)      DEFAULT NULL,
    -- Gelesen?
    is_read         BOOLEAN          NOT NULL DEFAULT FALSE,
    -- Über welchen Kanal gesendet?
    sent_via        JSON,
    created_at      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_read_level  (is_read, level, created_at),
    INDEX idx_created     (created_at)
) ENGINE=InnoDB;

-- ============================================================
-- 9. ANNOTATIONS / NOTIZEN
-- ============================================================
CREATE TABLE annotations (
    id              BIGINT UNSIGNED  AUTO_INCREMENT PRIMARY KEY,
    -- Kann zu verschiedenen Entitäten gehören
    entity_type     ENUM('topic','result','source') NOT NULL,
    entity_id       BIGINT UNSIGNED  NOT NULL,
    note            TEXT             NOT NULL,
    created_at      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_entity (entity_type, entity_id)
) ENGINE=InnoDB;

-- ============================================================
-- SEED-DATEN: Initiale LLM-Konfigurationen
-- ============================================================
INSERT INTO llm_configs (name, provider, model_name, api_endpoint, max_tokens, temperature, is_default, is_active) VALUES
('Ollama Llama3.2 (lokal)',   'ollama',  'llama3.2',                   'http://host.docker.internal:11434', 2000, 0.30, TRUE,  TRUE),
('Claude Haiku (günstig)',     'claude',  'claude-haiku-4-5-20251001',  NULL,                                2000, 0.30, FALSE, FALSE),
('Claude Sonnet (Standard)',   'claude',  'claude-sonnet-4-6',          NULL,                                4000, 0.30, FALSE, FALSE),
('OpenAI GPT-4o-mini',        'openai',  'gpt-4o-mini',                NULL,                                2000, 0.30, FALSE, FALSE);

-- ============================================================
-- SEED-DATEN: Beispiel-Topics
-- ============================================================
INSERT INTO topics (name, slug, description, category, schedule_type, status, priority, tags, search_config) VALUES
(
    'KI-Modelle neue Releases',
    'ki-modelle-releases',
    'Neue Sprachmodelle, Benchmarks und Release-Ankündigungen',
    'Technologie',
    'continuous',
    'active',
    2,
    '["KI", "LLM", "Technologie"]',
    '{"keywords": ["new AI model release", "LLM benchmark", "claude update", "GPT release", "ollama new model"], "exclude": ["crypto", "blockchain"]}'
),
(
    'Lokale Strompreise',
    'strompreise',
    'Aktuelle Strom- und Gaspreise sowie Energiemarkt-News',
    'Energie',
    'continuous',
    'active',
    3,
    '["Energie", "Kosten", "Smart Home"]',
    '{"keywords": ["Strompreis aktuell", "Energiepreise Deutschland", "Börsen Strompreis"], "language": "de"}'
),
(
    'Raspberry Pi Neuigkeiten',
    'raspberry-pi',
    'Neue Raspberry Pi Hardware, Software und Community-Projekte',
    'Hardware',
    'sporadic',
    'active',
    4,
    '["Hardware", "Raspberry Pi", "DIY"]',
    '{"keywords": ["Raspberry Pi new", "RPi release", "raspberry pi 5"], "sources_prefer": ["raspberrypi.com", "raspberrypi.org"]}'
);

-- Research-Intervalle für die Beispiel-Topics
INSERT INTO research_intervals (topic_id, interval_type, interval_seconds, cron_expression, is_active) VALUES
(1, 'cron',  NULL,  '0 8,16 * * *', TRUE),  -- 2x täglich um 8 und 16 Uhr
(2, 'cron',  NULL,  '0 7 * * *',    TRUE),  -- täglich 7 Uhr morgens
(3, 'fixed', 604800, NULL,          TRUE);  -- einmal pro Woche

-- Beispiel-Quellen
INSERT INTO sources (url, domain, title, source_type, trust_score) VALUES
('https://www.heise.de/rss/heise.rdf',        'heise.de',            'Heise Online',          'rss',     0.90),
('https://feeds.arstechnica.com/arstechnica/technology', 'arstechnica.com', 'Ars Technica',   'rss',     0.88),
('https://www.tagesschau.de/xml/rss2',         'tagesschau.de',       'Tagesschau',            'rss',     0.95),
('https://www.raspberrypi.com/news',           'raspberrypi.com',     'Raspberry Pi Blog',     'website', 0.98),
('https://ollama.com',                         'ollama.com',          'Ollama',                'website', 0.92);
