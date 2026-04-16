"""
Claude-Client: Anthropic API Integration.
Nutzt Prompt Caching für wiederholte System-Prompts (spart Tokens).
"""

from __future__ import annotations

import logging
from typing import Optional

import anthropic

from core.llm.llm_types import LLMRequest, LLMResponse

logger = logging.getLogger(__name__)

# Kosten pro 1M Tokens in EUR (ca. USD ≈ EUR für einfache Rechnung)
CLAUDE_COSTS: dict[str, dict[str, float]] = {
    "claude-haiku-4-5-20251001": {"input": 0.80,  "output": 4.00},
    "claude-sonnet-4-6":         {"input": 3.00,  "output": 15.00},
    "claude-opus-4-6":           {"input": 15.00, "output": 75.00},
}


def _calc_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Berechnet Kosten in EUR für einen API-Aufruf."""
    costs = CLAUDE_COSTS.get(model, {"input": 3.00, "output": 15.00})
    return (
        input_tokens  / 1_000_000 * costs["input"] +
        output_tokens / 1_000_000 * costs["output"]
    )


class ClaudeClient:
    """Client für Anthropic Claude API mit Prompt-Caching."""

    def __init__(self, api_key: str, default_model: str) -> None:
        self.client        = anthropic.AsyncAnthropic(api_key=api_key)
        self.default_model = default_model

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Text-Completion mit Claude API."""
        model = request.model or self.default_model

        # System-Prompt mit Caching-Prefix (spart 90% bei wiederholten Anfragen)
        system_content: list | str = []
        if request.system_prompt:
            system_content = [
                {
                    "type": "text",
                    "text": request.system_prompt,
                    "cache_control": {"type": "ephemeral"},  # Prompt Caching
                }
            ]

        response = await self.client.messages.create(
            model=model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            system=system_content if system_content else anthropic.NOT_GIVEN,
            messages=[{"role": "user", "content": request.prompt}],
        )

        content       = response.content[0].text if response.content else ""
        input_tokens  = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        cost          = _calc_cost(model, input_tokens, output_tokens)

        return LLMResponse(
            content=content,
            provider="claude",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_eur=cost,
        )
