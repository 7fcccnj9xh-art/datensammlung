#!/bin/bash
# ============================================================
# Knowledge Collector – Erstinstallation
# Ausführen auf dem UGREEN NAS via SSH:
#   bash setup.sh
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "======================================"
echo "  Knowledge Collector – Setup"
echo "  UGREEN NAS / UGOS Pro"
echo "======================================"

# --- .env prüfen ---
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo ""
    echo "[INFO] .env nicht gefunden. Kopiere .env.example..."
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo "[WICHTIG] Bitte .env bearbeiten bevor du fortfährst!"
    echo "  nano $PROJECT_DIR/.env"
    echo ""
    read -p "Weiter nach .env-Bearbeitung? [Enter]"
fi

# --- Daten-Verzeichnisse anlegen ---
echo "[1/5] Verzeichnisse anlegen..."
source "$PROJECT_DIR/.env"
DATA_PATH="${NAS_DATA_PATH:-./data}"
mkdir -p "$DATA_PATH"/{logs,exports,redis,obsidian}
echo "  Datenpfad: $DATA_PATH"

# --- SearXNG-Konfiguration ---
echo "[2/5] SearXNG konfigurieren..."
mkdir -p "$PROJECT_DIR/searxng"
if [ ! -f "$PROJECT_DIR/searxng/settings.yml" ]; then
    cat > "$PROJECT_DIR/searxng/settings.yml" << 'SEARXNG_EOF'
use_default_settings: true
server:
  secret_key: "$(openssl rand -hex 32)"
  limiter: false
  image_proxy: false
ui:
  static_use_hash: true
search:
  safe_search: 0
  default_lang: "de"
engines:
  - name: google
    engine: google
    language: de
    region: de-DE
  - name: duckduckgo
    engine: duckduckgo
  - name: bing
    engine: bing
SEARXNG_EOF
    echo "  SearXNG settings.yml erstellt"
fi

# --- Datenbank-Schema einrichten ---
echo "[3/5] Datenbank-Schema einrichten..."
echo "  MySQL wird für schema.sql benötigt."
echo "  Führe folgenden Befehl aus wenn MySQL läuft:"
echo ""
echo "  mysql -h \${DB_HOST} -u \${DB_USER} -p < database/schema.sql"
echo ""

# --- Docker-Images bauen ---
echo "[4/5] Docker-Images bauen..."
cd "$PROJECT_DIR"
docker compose build --no-cache
echo "  Images gebaut"

# --- Container starten ---
echo "[5/5] Container starten..."
docker compose up -d
echo "  Container gestartet"

echo ""
echo "======================================"
echo "  Installation abgeschlossen!"
echo "======================================"
echo ""
echo "  Frontend: http://$(hostname -I | awk '{print $1}'):${FRONTEND_PORT:-8421}"
echo "  Backend:  http://$(hostname -I | awk '{print $1}'):${APP_PORT:-8420}"
echo "  API Docs: http://$(hostname -I | awk '{print $1}'):${APP_PORT:-8420}/api/docs"
echo "  SearXNG:  http://$(hostname -I | awk '{print $1}'):${SEARXNG_PORT:-8422}"
echo ""
echo "  Logs:     docker compose logs -f backend"
echo "======================================"
