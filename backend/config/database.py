"""
Datenbankverbindung und Session-Management.
Verwendet SQLAlchemy 2.0 async mit aiomysql.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from config.settings import get_settings

logger = logging.getLogger(__name__)

# ----------------------------------------------------------
# ORM-Basis
# ----------------------------------------------------------
class Base(DeclarativeBase):
    """SQLAlchemy ORM-Basis für alle Models."""
    pass


# ----------------------------------------------------------
# Engine + Session Factory (Singletons)
# ----------------------------------------------------------
_engine: AsyncEngine | None        = None
_session_factory: async_sessionmaker | None = None


def get_engine() -> AsyncEngine:
    """Gibt den globalen AsyncEngine zurück, erstellt ihn wenn nötig."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.db_echo,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_pool_max_overflow,
            pool_pre_ping=True,         # Verbindung vor Nutzung prüfen
            pool_recycle=3600,          # Verbindungen nach 1h recyclen (MySQL timeout)
            connect_args={
                "charset": "utf8mb4",
                "connect_timeout": 10,
            },
        )
        logger.info(
            "Datenbank-Engine erstellt",
            extra={"host": settings.db_host, "db": settings.db_name}
        )
    return _engine


def get_session_factory() -> async_sessionmaker:
    """Gibt die globale Session-Factory zurück."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,   # Objekte nach Commit nicht invalidieren
            autocommit=False,
            autoflush=False,
        )
    return _session_factory


# ----------------------------------------------------------
# Dependency für FastAPI (Dependency Injection)
# ----------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI-Dependency für DB-Sessions.
    Verwendung:
        @router.get("/")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ----------------------------------------------------------
# Context Manager für non-FastAPI Code (Scheduler, Tasks)
# ----------------------------------------------------------
@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context Manager für DB-Sessions außerhalb von FastAPI.
    Verwendung:
        async with get_db_session() as db:
            result = await db.execute(...)
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ----------------------------------------------------------
# Startup / Shutdown Lifecycle
# ----------------------------------------------------------
async def init_database() -> None:
    """
    Datenbankverbindung initialisieren und Verbindung testen.
    Wird beim App-Start aufgerufen.
    """
    settings = get_settings()
    engine = get_engine()

    try:
        # Verbindungstest
        async with engine.connect() as conn:
            from sqlalchemy import text
            result = await conn.execute(text("SELECT 1"))
            result.fetchone()
        logger.info(
            f"Datenbankverbindung OK: {settings.db_host}:{settings.db_port}/{settings.db_name}"
        )
    except Exception as e:
        logger.error(f"Datenbankverbindung FEHLGESCHLAGEN: {e}")
        raise


async def close_database() -> None:
    """Datenbankverbindung beim App-Stop sauber schließen."""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Datenbankverbindung geschlossen")


# ----------------------------------------------------------
# Hilfsfunktion: Schema initialisieren (für Tests)
# ----------------------------------------------------------
async def create_all_tables() -> None:
    """
    Erstellt alle Tabellen via ORM (nur für Tests/Dev).
    Produktion: Tabellen werden via schema.sql angelegt.
    """
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Alle ORM-Tabellen erstellt")
