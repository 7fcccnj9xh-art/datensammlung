"""
Zentrale Anwendungskonfiguration mit Pydantic BaseSettings.
Alle Werte werden aus Umgebungsvariablen oder .env geladen.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(str, Enum):
    OLLAMA = "ollama"
    CLAUDE = "claude"
    OPENAI = "openai"
    AUTO   = "auto"


class LogLevel(str, Enum):
    DEBUG   = "DEBUG"
    INFO    = "INFO"
    WARNING = "WARNING"
    ERROR   = "ERROR"


class Settings(BaseSettings):
    """
    Hauptkonfiguration der Anwendung.
    Werte werden in dieser Reihenfolge geladen:
    1. Umgebungsvariablen
    2. .env Datei
    3. Standardwerte
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",      # Unbekannte Variablen ignorieren
    )

    # ----------------------------------------------------------
    # Datenbank
    # ----------------------------------------------------------
    db_host: str              = Field("192.168.0.101",       description="MySQL Host (UGREEN NAS)")
    db_port: int              = Field(3306,                  description="MySQL Port")
    db_name: str              = Field("knowledge_collector", description="Datenbankname")
    db_user: str              = Field("root",                description="MySQL User")
    db_password: str          = Field("",                    description="MySQL Passwort")
    db_pool_size: int         = Field(10,                    description="Verbindungspool-Größe")
    db_pool_max_overflow: int = Field(20,                    description="Max. Overflow-Verbindungen")
    db_echo: bool             = Field(False,                 description="SQL-Queries loggen (nur Debug)")

    @property
    def database_url(self) -> str:
        """Async MySQL-URL für SQLAlchemy."""
        return (
            f"mysql+aiomysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
            f"?charset=utf8mb4"
        )

    @property
    def sync_database_url(self) -> str:
        """Sync MySQL-URL für Alembic-Migrationen."""
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
            f"?charset=utf8mb4"
        )

    # ----------------------------------------------------------
    # Redis
    # ----------------------------------------------------------
    redis_url: str = Field("redis://redis:6379/0", description="Redis-Verbindungs-URL")

    # ----------------------------------------------------------
    # LLM Provider
    # ----------------------------------------------------------
    ollama_host: str           = Field("http://host.docker.internal:11434", description="Ollama-Endpunkt")
    ollama_default_model: str  = Field("llama3.2",                          description="Standard-Ollama-Modell")
    ollama_timeout: int        = Field(120,                                  description="Timeout in Sekunden")

    anthropic_api_key: str     = Field("",                                   description="Anthropic API Key")
    claude_default_model: str  = Field("claude-haiku-4-5-20251001",          description="Standard-Claude-Modell")

    openai_api_key: str        = Field("",                                   description="OpenAI API Key")
    openai_default_model: str  = Field("gpt-4o-mini",                        description="Standard-GPT-Modell")

    default_llm_provider: LLMProvider = Field(LLMProvider.AUTO, description="Standard-LLM-Provider")
    llm_monthly_budget_eur: float     = Field(5.0,             description="Monatliches Kosten-Budget EUR")

    # LLM Cache-TTL in Sekunden (0 = deaktiviert)
    llm_cache_ttl: int = Field(3600, description="LLM-Antwort-Cache-Dauer in Sekunden")

    # ----------------------------------------------------------
    # Web-Scraping
    # ----------------------------------------------------------
    scraping_delay_min: float      = Field(1.5,  description="Min. Verzögerung zwischen Requests (s)")
    scraping_delay_max: float      = Field(4.0,  description="Max. Verzögerung zwischen Requests (s)")
    max_concurrent_scrapers: int   = Field(3,    description="Maximale parallele Scraper")
    respect_robots_txt: bool       = Field(True, description="robots.txt respektieren")
    use_playwright: bool           = Field(False, description="Playwright für JS-Seiten aktivieren")
    scraping_timeout: int          = Field(30,   description="HTTP-Timeout in Sekunden")
    user_agent: str                = Field(
        "KnowledgeCollector/1.0 (private research)",
        description="HTTP User-Agent"
    )

    # ----------------------------------------------------------
    # Suche
    # ----------------------------------------------------------
    searxng_url: str         = Field("http://searxng:8080", description="SearXNG-URL")
    search_fallback: str     = Field("duckduckgo",          description="Fallback-Suchmaschine")
    search_max_results: int  = Field(10,                    description="Max. Suchergebnisse")

    # ----------------------------------------------------------
    # Anwendung
    # ----------------------------------------------------------
    app_port: int          = Field(8420,            description="Backend-Port")
    frontend_port: int     = Field(8421,            description="Frontend-Port")
    secret_key: str        = Field("CHANGE_ME",     description="JWT Secret Key")
    log_level: LogLevel    = Field(LogLevel.INFO,   description="Log-Level")
    log_file: str          = Field("knowledge_collector.log", description="Log-Datei")
    tz: str                = Field("Europe/Berlin", description="Zeitzone")

    # Verzeichnisse (werden beim Start angelegt)
    logs_dir: Path         = Field(Path("/app/logs"),    description="Log-Verzeichnis")
    exports_dir: Path      = Field(Path("/app/exports"), description="Export-Verzeichnis")
    obsidian_vault_path: Optional[Path] = Field(None,    description="Obsidian Vault Pfad")

    # ----------------------------------------------------------
    # Benachrichtigungen
    # ----------------------------------------------------------
    telegram_bot_token: str  = Field("", description="Telegram Bot Token")
    telegram_chat_id: str    = Field("", description="Telegram Chat ID")
    smtp_host: str           = Field("", description="SMTP Host")
    smtp_port: int           = Field(587, description="SMTP Port")
    smtp_user: str           = Field("", description="SMTP User")
    smtp_password: str       = Field("", description="SMTP Passwort")
    smtp_from: str           = Field("knowledge@haasch.local", description="Absender-E-Mail")
    pushover_api_key: str    = Field("", description="Pushover API Key")
    pushover_user_key: str   = Field("", description="Pushover User Key")

    # ----------------------------------------------------------
    # NAS-spezifisch
    # ----------------------------------------------------------
    nas_data_path: str    = Field("./data",                          description="NAS Datenpfad")
    nas_backup_path: str  = Field("./data/backups",                  description="NAS Backup-Pfad")

    # ----------------------------------------------------------
    # Export
    # ----------------------------------------------------------
    obsidian_auto_export: bool = Field(False, description="Automatischer Obsidian-Export")

    # ----------------------------------------------------------
    # Validierungen
    # ----------------------------------------------------------
    @field_validator("db_password", "secret_key", mode="before")
    @classmethod
    def check_not_empty_in_production(cls, v: str) -> str:
        """Warnung (kein Fehler) wenn kritische Werte fehlen."""
        return v or ""

    @field_validator("scraping_delay_min", "scraping_delay_max")
    @classmethod
    def validate_delay(cls, v: float) -> float:
        """Mindest-Delay von 0.5s erzwingen (Fairness)."""
        return max(0.5, v)

    @model_validator(mode="after")
    def validate_delay_order(self) -> "Settings":
        """Min-Delay muss kleiner als Max-Delay sein."""
        if self.scraping_delay_min > self.scraping_delay_max:
            self.scraping_delay_max = self.scraping_delay_min + 1.0
        return self

    # ----------------------------------------------------------
    # Hilfsmethoden
    # ----------------------------------------------------------
    @property
    def has_telegram(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    @property
    def has_smtp(self) -> bool:
        return bool(self.smtp_host and self.smtp_user)

    @property
    def has_claude(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key)

    def get_active_providers(self) -> list[str]:
        """Liste aller konfigurierten (verfügbaren) LLM-Provider."""
        providers = ["ollama"]   # Ollama ist immer versucht
        if self.has_claude:
            providers.append("claude")
        if self.has_openai:
            providers.append("openai")
        return providers

    def safe_dict(self) -> dict:
        """Config als Dict – API-Keys werden maskiert."""
        data = self.model_dump()
        for key in ("db_password", "secret_key", "anthropic_api_key",
                    "openai_api_key",
                    "telegram_bot_token", "smtp_password",
                    "pushover_api_key", "pushover_user_key"):
            if data.get(key):
                data[key] = "***"
        return data


@lru_cache()
def get_settings() -> Settings:
    """
    Singleton-Getter für Settings.
    Verwendung: from config.settings import get_settings; s = get_settings()
    """
    return Settings()
