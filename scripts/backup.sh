#!/bin/bash
# ============================================================
# Knowledge Collector – Tägliches Backup
# Cron-Empfehlung: 0 2 * * * /path/to/backup.sh
# ============================================================
set -e

source "$(dirname "$0")/../.env"

DATE=$(date +%Y%m%d_%H%M)
BACKUP_DIR="${NAS_BACKUP_PATH:-./data/backups}/$DATE"
mkdir -p "$BACKUP_DIR"

echo "[$(date)] Backup startet → $BACKUP_DIR"

# MySQL Dump
mysqldump \
  -h "${DB_HOST:-192.168.0.101}" \
  -P "${DB_PORT:-3306}" \
  -u "${DB_USER:-root}" \
  -p"${DB_PASSWORD}" \
  --single-transaction \
  --routines \
  "${DB_NAME:-knowledge_collector}" \
  | gzip > "$BACKUP_DIR/db_${DB_NAME}.sql.gz"

echo "[$(date)] DB gesichert: $(du -sh "$BACKUP_DIR/db_${DB_NAME}.sql.gz" | cut -f1)"

# Alte Backups löschen (> 30 Tage)
find "${NAS_BACKUP_PATH:-./data/backups}" -maxdepth 1 -mtime +30 -type d -exec rm -rf {} + 2>/dev/null || true

echo "[$(date)] Backup abgeschlossen"
