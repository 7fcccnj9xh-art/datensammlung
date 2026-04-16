"""
LLM-Router: Zentraler Einstiegspunkt für alle KI-Anfragen.

Fallback-Kette: Ollama (lokal, kostenlos) → Claude → OpenAI
Jeder Provider kann pro Topic oder global konfiguriert werden.
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Optional

import redis.asyncio as aioredis

from config.settings import LLMProvider, get_settings
from core.llm.llm_types import LLMRequest, LLMResponse
from core.llm.ollama_client import OllamaClient
from core.llm.claude_client import ClaudeClient
from core.llm.openai_client import OpenAIClient

logger = logging.getLogger(__name__)


class LLMRouter:
    """
    Zentraler LLM-Router mit automatischer Provider-Auswahl und Fallback.

    Verwendung:
        router = LLMRouter()
        await router.initialize()
        response = await router.complete(LLMRequest(prompt="Fasse zusammen: ..."))
    """

    def __init__(self) -> None:
        self.settings       = get_settings()
        self._ollama: Optional[OllamaClient]    = None
        self._claude: Optional[ClaudeClient]    = None
        self._openai: Optional[OpenAIClient]    = None
        self._redis: Optional[aioredis.Redis]   = None
        self._initialized   = False

    async def initialize(self) -> None:
        """Provider-Clients und Redis-Cache initialisieren."""
        # Ollama: immer versuchen
        self._ollama = OllamaClient(
            host=self.settings.ollama_host,
            default_model=self.settings.ollama_default_model,
            timeout=self.settings.ollama_timeout,
        )
        await self._ollama.check_availability()

        # Claude: nur wenn API-Key vorhanden
        if self.settings.has_claude:
            self._claude = ClaudeClient(
                api_key=self.settings.anthropic_api_key,
                default_model=self.settings.claude_default_model,
            )

        # OpenAI: nur wenn API-Key vorhanden
        if self.settings.has_openai:
            self._openai = OpenAIClient(
                api_key=self.settings.openai_api_key,
                default_model=self.settings.openai_default_model,
            )

        # Redis-Cache
        if self.settings.llm_cache_ttl > 0:
            try:
                self._redis = aioredis.from_url(
                    self.settings.redis_url,
                    decode_responses=True,
                    socket_timeout=2,
                )
                await self._redis.ping()
                logger.info("LLM-Cache: Redis verbunden")
            except Exception as e:
                logger.warning(f"LLM-Cache: Redis nicht erreichbar ({e}), Cache deaktiviert")
                self._redis = None

        self._initialized = True
        available = self._get_available_providers()
        logger.info(f"LLM-Router initialisiert. Verfügbare Provider: {available}")

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """
        Haupt-Methode: LLM-Anfrage mit automatischem Fallback.

        Reihenfolge:
        1. Cache prüfen
        2. Gewünschten Provider versuchen
        3. Bei Fehler: nächsten Provider in Fallback-Kette
        4. Ergebnis cachen
        5. Verbrauch in DB loggen
        """
        if not self._initialized:
            await self.initialize()

        # Cache prüfen
        if request.use_cache and self._redis:
            cached = await self._get_from_cache(request)
            if cached:
                logger.debug(f"LLM-Cache-Hit für {request.prompt_type}")
                return cached

        # Provider-Reihenfolge bestimmen
        providers = self._get_provider_order(request.provider)

        last_error: Optional[str] = None
        for provider_name in providers:
            try:
                start_ms = int(time.monotonic() * 1000)
                response = await self._call_provider(provider_name, request)
                response.duration_ms = int(time.monotonic() * 1000) - start_ms

                if response.success:
                    # Ergebnis cachen
                    if request.use_cache and self._redis:
                        await self._save_to_cache(request, response)

                    # Verbrauch loggen
                    await self._log_usage(request, response)

                    return response

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Provider {provider_name} fehlgeschlagen: {e}, versuche nächsten...")
                continue

        # Alle Provider fehlgeschlagen
        logger.error(f"Alle LLM-Provider fehlgeschlagen. Letzter Fehler: {last_error}")
        return LLMResponse(
            content="",
            provider="none",
            model="none",
            error=f"Alle Provider fehlgeschlagen: {last_error}",
        )

    async def is_available(self, provider: str) -> bool:
        """Prüft ob ein bestimmter Provider erreichbar ist."""
        if provider == "ollama":
            return self._ollama is not None and self._ollama.available
        elif provider == "claude":
            return self._claude is not None
        elif provider == "openai":
            return self._openai is not None
        return False

    def get_status(self) -> dict:
        """Status aller Provider für das Dashboard."""
        return {
            "ollama": {
                "available":     self._ollama is not None and self._ollama.available,
                "host":          self.settings.ollama_host,
                "default_model": self.settings.ollama_default_model,
                "models":        getattr(self._ollama, "available_models", []),
            },
            "claude": {
                "available":     self._claude is not None,
                "configured":    self.settings.has_claude,
                "default_model": self.settings.claude_default_model,
            },
            "openai": {
                "available":     self._openai is not None,
                "configured":    self.settings.has_openai,
                "default_model": self.settings.openai_default_model,
            },
            "default_provider": self.settings.default_llm_provider,
            "cache_active":      self._redis is not None,
        }

    # ----------------------------------------------------------
    # Private Methoden
    # ----------------------------------------------------------

    def _get_provider_order(self, requested: Optional[str]) -> list[str]:
        """
        Ermittelt die Provider-Reihenfolge.
        Bei 'auto': Ollama → Claude → OpenAI
        """
        if requested and requested != "auto":
            # Explizit angefordert: erst dieser, dann Fallback
            fallback = [p for p in ["ollama", "claude", "openai"] if p != requested]
            return [requested] + fallback

        default = self.settings.default_llm_provider.value
        if default == "auto":
            return ["ollama", "claude", "openai"]
        else:
            fallback = [p for p in ["ollama", "claude", "openai"] if p != default]
            return [default] + fallback

    def _get_available_providers(self) -> list[str]:
        """Gibt Liste der aktuell verfügbaren Provider zurück."""
        available = []
        if self._ollama and self._ollama.available:
            available.append("ollama")
        if self._claude:
            available.append("claude")
        if self._openai:
            available.append("openai")
        return available

    async def _call_provider(self, provider: str, request: LLMRequest) -> LLMResponse:
        """Ruft einen spezifischen Provider auf."""
        if provider == "ollama":
            if not self._ollama or not self._ollama.available:
                raise RuntimeError("Ollama nicht erreichbar")
            return await self._ollama.complete(request)

        elif provider == "claude":
            if not self._claude:
                raise RuntimeError("Claude nicht konfiguriert (kein API-Key)")
            return await self._claude.complete(request)

        elif provider == "openai":
            if not self._openai:
                raise RuntimeError("OpenAI nicht konfiguriert (kein API-Key)")
            return await self._openai.complete(request)

        else:
            raise ValueError(f"Unbekannter Provider: {provider}")

    def _cache_key(self, request: LLMRequest) -> str:
        """Eindeutiger Cache-Key aus Prompt + Parametern."""
        key_data = f"{request.provider}|{request.model}|{request.temperature}|{request.prompt}"
        if request.system_prompt:
            key_data += f"|sys:{request.system_prompt}"
        hash_val = hashlib.sha256(key_data.encode()).hexdigest()[:16]
        return f"llm_cache:{hash_val}"

    async def _get_from_cache(self, request: LLMRequest) -> Optional[LLMResponse]:
        """LLM-Antwort aus Redis-Cache laden."""
        try:
            import json
            key  = self._cache_key(request)
            data = await self._redis.get(key)
            if data:
                d = json.loads(data)
                return LLMResponse(from_cache=True, **d)
        except Exception as e:
            logger.debug(f"Cache-Lesefehler: {e}")
        return None

    async def _save_to_cache(self, request: LLMRequest, response: LLMResponse) -> None:
        """LLM-Antwort in Redis cachen."""
        try:
            import json
            key = self._cache_key(request)
            data = {
                "content":       response.content,
                "provider":      response.provider,
                "model":         response.model,
                "input_tokens":  response.input_tokens,
                "output_tokens": response.output_tokens,
                "cost_eur":      response.cost_eur,
                "duration_ms":   response.duration_ms,
            }
            await self._redis.setex(key, self.settings.llm_cache_ttl, json.dumps(data))
        except Exception as e:
            logger.debug(f"Cache-Schreibfehler: {e}")

    async def _log_usage(self, request: LLMRequest, response: LLMResponse) -> None:
        """LLM-Verbrauch in Datenbank protokollieren."""
        try:
            from config.database import get_db_session
            from models.llm import LLMUsage
            from sqlalchemy import select

            async with get_db_session() as db:
                from models.llm import LLMConfig
                result = await db.execute(
                    select(LLMConfig).where(LLMConfig.provider == response.provider).limit(1)
                )
                config = result.scalar_one_or_none()
                if config:
                    usage = LLMUsage(
                        llm_config_id=config.id,
                        job_id=request.job_id,
                        topic_id=request.topic_id,
                        input_tokens=response.input_tokens,
                        output_tokens=response.output_tokens,
                        cost_eur=response.cost_eur,
                        prompt_type=request.prompt_type,
                        duration_ms=response.duration_ms,
                        from_cache=response.from_cache,
                    )
                    db.add(usage)
                    # Budget-Update
                    if response.cost_eur > 0:
                        config.monthly_spent_eur += response.cost_eur
        except Exception as e:
            logger.debug(f"Usage-Logging fehlgeschlagen: {e}")

    async def close(self) -> None:
        """Resources freigeben."""
        if self._redis:
            await self._redis.close()


# Globale Router-Instanz (Singleton via App-State)
_router_instance: Optional[LLMRouter] = None


def get_llm_router() -> LLMRouter:
    """Gibt die globale Router-Instanz zurück."""
    global _router_instance
    if _router_instance is None:
        _router_instance = LLMRouter()
    return _router_instance
