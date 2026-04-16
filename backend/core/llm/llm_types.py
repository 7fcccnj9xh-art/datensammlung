"""
Gemeinsame Datenklassen für den LLM-Router.
Ausgelagert um zirkuläre Imports zu vermeiden.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class LLMRequest:
    """Einheitliche Anfrage-Struktur für alle Provider."""
    prompt: str
    system_prompt: Optional[str]      = None
    max_tokens: int                   = 2000
    temperature: float                = 0.3
    provider: Optional[str]           = None
    model: Optional[str]              = None
    prompt_type: str                  = "generic"
    topic_id: Optional[int]           = None
    job_id: Optional[int]             = None
    use_cache: bool                   = True
    extra: dict[str, Any]             = field(default_factory=dict)


@dataclass
class LLMResponse:
    """Einheitliche Antwort-Struktur von allen Providern."""
    content: str
    provider: str
    model: str
    input_tokens: int       = 0
    output_tokens: int      = 0
    cost_eur: float         = 0.0
    duration_ms: int        = 0
    from_cache: bool        = False
    error: Optional[str]    = None

    @property
    def success(self) -> bool:
        return self.error is None and bool(self.content)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens
