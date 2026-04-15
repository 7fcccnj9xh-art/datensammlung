# Knowledge Collector

Umfassendes Datensammlungs- und Knowledge-Management-System für den UGREEN DXP2800 NAS (UGOS Pro).

Vereint strukturierte Datensammlung (Wetterdaten, APIs), themenbasierte Web-Recherche mit LLM-Verarbeitung und ein lokales Web-Frontend zur Verwaltung aller Inhalte.

---

## Features

- **Topics & Scheduling** – Themen mit konfigurierbaren Intervallen (fix, Cron) automatisch recherchieren lassen
- **Web-Recherche** – Websites, RSS-Feeds und APIs scrapen; Inhalte via LLM zusammenfassen
- **LLM-Router** – Automatischer Fallback Ollama (lokal, kostenlos) → Claude → OpenAI
- **Wetterdaten** – DWD Open Data (kostenlos, kein API-Key) + optional OpenWeatherMap
- **Quellen-Management** – Trust-Scores, Fehlerrate, bevorzugte Quellen pro Topic
- **Job-Monitoring** – Alle Ausführungen protokolliert, WebSocket Live-Updates
- **Vue 3 Frontend** – Dashboard, Knowledge Browser, Wetter-Charts, Settings

---

## Systemvoraussetzungen

| Komponente | Version |
|-----------|---------|
| UGREEN NAS / UGOS Pro | beliebig |
| Docker Engine | ≥ 24 |
| MySQL (auf NAS) | ≥ 8.0 |
| Ollama (optional) | beliebig |

---

## Schnellstart

### 1. Konfiguration

```bash
cp .env.example .env
```

Mindestens folgende Werte in `.env` setzen:

```env
DB_HOST=192.168.0.101
DB_PASSWORD=dein_mysql_passwort
SECRET_KEY=$(openssl rand -hex 32)

# Standort für Wetterdaten
WEATHER_LAT=47.9990
WEATHER_LON=7.8421
WEATHER_LOCATION_NAME=Freiburg im Breisgau
```

### 2. Datenbank einrichten

```bash
mysql -h 192.168.0.101 -u root -p < database/schema.sql
```

### 3. Starten

```bash
docker compose up -d
```

### 4. Aufrufen

| Dienst | URL |
|--------|-----|
| Frontend | `http://192.168.0.101:8421` |
| API Docs | `http://192.168.0.101:8420/api/docs` |
| SearXNG | `http://192.168.0.101:8422` |

---

## Projektstruktur

```
knowledge-collector/
├── database/
│   ├── schema.sql              # Vollständiges DB-Schema (10 Tabellen)
│   └── migrations/             # Versionierte Migrationen
│
├── backend/
│   ├── main.py                 # FastAPI Einstiegspunkt
│   ├── config/
│   │   ├── settings.py         # Pydantic-Konfiguration aus .env
│   │   └── database.py         # Async MySQL-Verbindungspool
│   ├── models/                 # SQLAlchemy ORM-Models
│   ├── core/
│   │   ├── llm/                # LLM-Router + Provider-Clients
│   │   ├── collectors/         # Web/RSS/Wetter/API Collector
│   │   ├── processors/         # Text- und LLM-Verarbeitung
│   │   └── scheduler/          # APScheduler + Job-Management
│   └── api/routes/             # FastAPI-Endpunkte
│
├── frontend/
│   └── src/views/              # Vue 3 Ansichten
│
├── nginx/nginx.conf            # Reverse Proxy + API-Proxy
├── scripts/
│   ├── setup.sh                # Erstinstallation
│   └── backup.sh               # Tägliches DB-Backup
│
├── docker-compose.yml          # Produktion (NAS)
├── docker-compose.dev.yml      # Entwicklung (Hot-Reload)
└── .env.example                # Alle Konfigurationsvariablen
```

---

## LLM-Konfiguration

Der Router wählt automatisch nach Verfügbarkeit und Kosten:

| Stufe | Provider | Kosten | Wann |
|-------|---------|--------|------|
| 1 | **Ollama** (lokal) | kostenlos | Standard, wenn erreichbar |
| 2 | **Claude Haiku** | ~$0.80/MTok | Wenn Ollama nicht verfügbar |
| 3 | **Claude Sonnet** | ~$3/MTok | Für komplexe Aufgaben |
| 4 | **OpenAI GPT-4o-mini** | ~$0.15/MTok | Alternativer Cloud-Fallback |

Pro Topic kann ein anderer Provider erzwungen werden (`llm_provider` Feld).

---

## Wetterdaten

Standard: **DWD Open Data via BrightSky API** – kostenlos, kein API-Key nötig, Deutschland-fokussiert.

Optional: OpenWeatherMap (API-Key in `.env` → `OPENWEATHERMAP_API_KEY`).

Abfrage-Intervall konfigurierbar: `WEATHER_FETCH_INTERVAL_MIN=30`

---

## Entwicklung

```bash
# Hot-Reload starten
docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# Nur Backend lokal
cd backend && pip install -r requirements.txt
uvicorn main:app --reload --port 8420

# Nur Frontend lokal
cd frontend && npm install && npm run dev
```

---

## Ports

| Port | Dienst |
|------|--------|
| 8420 | Backend API |
| 8421 | Frontend |
| 8422 | SearXNG |
| 6379 | Redis (intern) |

---

## Umgebungsvariablen (wichtigste)

| Variable | Beschreibung | Standard |
|---------|-------------|---------|
| `DB_HOST` | MySQL-Host | `192.168.0.101` |
| `DB_PASSWORD` | MySQL-Passwort | – |
| `OLLAMA_HOST` | Ollama-Endpunkt | `http://host.docker.internal:11434` |
| `ANTHROPIC_API_KEY` | Claude API Key | – |
| `DEFAULT_LLM_PROVIDER` | `auto`/`ollama`/`claude`/`openai` | `auto` |
| `WEATHER_LAT` / `WEATHER_LON` | Standort-Koordinaten | Freiburg |
| `SECRET_KEY` | JWT Secret | **Pflichtfeld** |

Vollständige Liste: [.env.example](.env.example)
