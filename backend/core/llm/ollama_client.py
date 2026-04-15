"""
Ollama-Client: Lokales LLM über Ollama-API.
Kostenlos, Datenschutz-freundlich, kein Internet nötig.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from core.llm.llm_router import LLMRequest, LLMResponse

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client für lokalen Ollama-Server."""

    def __init__(self, host: str, default_model: str, timeout: int = 120) -> None:
        self.host          = host.rstrip("/")
        self.default_model = default_model
        self.timeout       = timeout
        self.available     = False
        self.available_models: list[str] = []

    async def check_availability(self) -> bool:
        """Ollama-Server auf Erreichbarkeit prüfen und Modell-Liste laden."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.host}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    self.available_models = [
                        m["name"] for m in data.get("models", [])
                    ]
                    self.available = True
                    logger.info(
                        f"Ollama erreichbar: {self.host} | "
                        f"Modelle: {', '.join(self.available_models[:5])}"
                    )
                    return True
        except Exception as e:
            logger.info(f"Ollama nicht erreichbar ({self.host}): {e}")
        self.available = False
        return False

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Text-Completion mit Ollama."""
        model = request.model or self.default_model

        # Messages aufbauen
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        payload = {
            "model":   model,
            "messages": messages,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.host}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        content = data.get("message", {}).get("content", "")
        usage   = data.get("usage", {})

        return LLMResponse(
            content=content,
            provider="ollama",
            model=model,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            cost_eur=0.0,    # Ollama ist kostenlos
        )

    async def list_models(self) -> list[str]:
        """Aktuelle Modell-Liste von Ollama abrufen."""
        await self.check_availability()
        return self.available_models
