-- Migration 001: Initial Schema
-- Wird automatisch beim ersten Start ausgeführt
-- Status-Tracking: Tabelle schema_migrations

CREATE TABLE IF NOT EXISTS schema_migrations (
    version     VARCHAR(50)  PRIMARY KEY,
    applied_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    description VARCHAR(500)
) ENGINE=InnoDB;

-- Prüfen ob Migration bereits durchgeführt
-- (Dieser Block wird von migration_runner.py gesteuert)
INSERT IGNORE INTO schema_migrations (version, description)
VALUES ('001', 'Initial schema: topics, sources, research_results, weather_data, llm_configs, jobs');
