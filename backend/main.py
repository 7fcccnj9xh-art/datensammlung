"""
Knowledge Collector – FastAPI Hauptanwendung
Einstiegspunkt für den Backend-Server.
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from config.settings import get_settings
from config.database import init_database, close_database
from core.llm.llm_router import get_llm_router
from core.scheduler.scheduler import get_scheduler
from api.routes import topics, research, sources, structured_data, jobs, llm, weather
from api.middleware.logging import RequestLoggingMiddleware

# ----------------------------------------------------------
# Logging konfigurieren
# ----------------------------------------------------------
settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.value),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(settings.logs_dir / settings.log_file, mode="a"),
    ],
)

logger = logging.getLogger("knowledge_collector")


# ----------------------------------------------------------
# App-Lifecycle
# ----------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup und Shutdown der Anwendung."""
    # STARTUP
    logger.info("=" * 60)
    logger.info("Knowledge Collector startet...")
    logger.info(f"  DB:       {settings.db_host}:{settings.db_port}/{settings.db_name}")
    logger.info(f"  LLM:      {settings.default_llm_provider}")
    logger.info(f"  Wetter:   {settings.weather_location_name} ({settings.weather_lat}, {settings.weather_lon})")
    logger.info("=" * 60)

    # Verzeichnisse anlegen
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    settings.exports_dir.mkdir(parents=True, exist_ok=True)

    # Datenbankverbindung
    await init_database()

    # LLM-Router initialisieren
    router = get_llm_router()
    await router.initialize()
    app.state.llm_router = router

    # Scheduler starten
    scheduler = get_scheduler()
    await scheduler.start()
    app.state.scheduler = scheduler

    logger.info("Startup abgeschlossen – API bereit")

    yield  # App läuft

    # SHUTDOWN
    logger.info("Knowledge Collector fährt herunter...")
    await scheduler.stop()
    await router.close()
    await close_database()
    logger.info("Shutdown abgeschlossen")


# ----------------------------------------------------------
# FastAPI App
# ----------------------------------------------------------
app = FastAPI(
    title="Knowledge Collector API",
    description="Datensammlungs- und Knowledge-Management-System",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ----------------------------------------------------------
# Middleware
# ----------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8421",
                   "http://192.168.0.101:8421"],  # Frontend-URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(RequestLoggingMiddleware)

# ----------------------------------------------------------
# Routes einbinden
# ----------------------------------------------------------
API_PREFIX = "/api"

app.include_router(topics.router,         prefix=f"{API_PREFIX}/topics",          tags=["Topics"])
app.include_router(research.router,       prefix=f"{API_PREFIX}/research",         tags=["Research"])
app.include_router(sources.router,        prefix=f"{API_PREFIX}/sources",          tags=["Sources"])
app.include_router(structured_data.router, prefix=f"{API_PREFIX}/data",            tags=["Structured Data"])
app.include_router(jobs.router,           prefix=f"{API_PREFIX}/jobs",             tags=["Jobs"])
app.include_router(llm.router,            prefix=f"{API_PREFIX}/llm",              tags=["LLM"])
app.include_router(weather.router,        prefix=f"{API_PREFIX}/weather",          tags=["Weather"])


# ----------------------------------------------------------
# Health + Info Endpunkte
# ----------------------------------------------------------
@app.get("/health", tags=["System"])
async def health_check():
    """Systemstatus für Docker Health-Check."""
    return {"status": "ok", "service": "knowledge-collector"}


@app.get("/api/status", tags=["System"])
async def system_status():
    """Vollständiger Systemstatus für Dashboard."""
    scheduler = get_scheduler()
    llm_router = get_llm_router()

    return {
        "status":       "running",
        "llm":          llm_router.get_status(),
        "scheduler": {
            "running": scheduler._running,
            "jobs":    scheduler.get_scheduled_jobs(),
        },
        "config": {
            "location":        settings.weather_location_name,
            "default_provider": settings.default_llm_provider,
            "log_level":       settings.log_level,
        },
    }


@app.get("/api/config", tags=["System"])
async def get_config():
    """Aktuelle Konfiguration (ohne Secrets) ausgeben."""
    return settings.safe_dict()


# ----------------------------------------------------------
# Globale Exception-Handler
# ----------------------------------------------------------
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(status_code=404, content={"detail": "Nicht gefunden"})


@app.exception_handler(500)
async def server_error_handler(request, exc):
    logger.error(f"Unbehandelte Exception: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Interner Serverfehler"})


# ----------------------------------------------------------
# Direktstart (Entwicklung)
# ----------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.app_port,
        reload=True,
        log_level=settings.log_level.value.lower(),
    )
