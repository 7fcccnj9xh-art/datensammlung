-- Migration 002: Wetter-Baustein entfernen
-- Wetterdaten werden im separaten Projekt /Users/whaa/Documents/GitHub/Wetterdaten verwaltet.

-- Alte Job-Einträge für weather_fetch löschen, damit die ENUM-Änderung nicht fehlschlägt
DELETE FROM jobs WHERE job_type = 'weather_fetch';

-- weather_data Tabelle droppen
DROP TABLE IF EXISTS weather_data;

-- jobs.job_type ENUM anpassen (weather_fetch entfernen)
ALTER TABLE jobs
    MODIFY COLUMN job_type ENUM('research','api_sync','on_demand','backup','export') NOT NULL;

INSERT IGNORE INTO schema_migrations (version, description)
VALUES ('002', 'Drop weather_data table and remove weather_fetch from jobs.job_type');
