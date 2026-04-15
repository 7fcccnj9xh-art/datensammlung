"""
LLM-Processor: Verknüpft Collector-Ergebnisse mit dem LLM-Router.
Zusammenfassungen, Relevanz-Bewertung, Delta-Erkennung.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from core.llm.llm_router import LLMRequest, LLMResponse, get_llm_router
from core.llm.prompts.research import (
    RESEARCH_SYSTEM_PROMPT,
    build_delta_prompt,
    build_keyword_extraction_prompt,
    build_relevance_prompt,
    build_search_queries_prompt,
    build_summary_prompt,
)
from core.processors.text_processor import get_text_processor

logger = logging.getLogger(__name__)


class LLMProcessor:
    """
    Verarbeitet Texte mit LLM: Zusammenfassungen, Relevanz, Diffs.
    """

    def __init__(self) -> None:
        self.router = get_llm_router()
        self.text   = get_text_processor()

    async def summarize(
        self,
        content: str,
        topic_name: str,
        topic_id: Optional[int] = None,
        job_id: Optional[int] = None,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
    ) -> Optional[str]:
        """
        Text zusammenfassen.
        Gibt None zurück wenn Inhalt zu kurz oder LLM-Fehler.
        """
        if not self.text.is_meaningful(content):
            return None

        truncated = self.text.truncate(content, max_chars=6000)
        prompt    = build_summary_prompt(truncated, topic_name)

        response = await self.router.complete(LLMRequest(
            prompt        = prompt,
            system_prompt = RESEARCH_SYSTEM_PROMPT,
            max_tokens    = 800,
            temperature   = 0.2,
            provider      = llm_provider,
            model         = llm_model,
            prompt_type   = "summary",
            topic_id      = topic_id,
            job_id        = job_id,
        ))

        if response.success:
            return response.content
        logger.warning(f"Zusammenfassung fehlgeschlagen: {response.error}")
        return None

    async def compute_delta(
        self,
        old_summary: str,
        new_content: str,
        topic_name: str,
        topic_id: Optional[int] = None,
    ) -> Optional[str]:
        """Was ist neu gegenüber dem letzten Stand?"""
        if not old_summary or not new_content:
            return None

        prompt   = build_delta_prompt(old_summary, new_content, topic_name)
        response = await self.router.complete(LLMRequest(
            prompt        = prompt,
            system_prompt = RESEARCH_SYSTEM_PROMPT,
            max_tokens    = 500,
            temperature   = 0.1,
            prompt_type   = "delta",
            topic_id      = topic_id,
        ))

        if response.success:
            text = response.content.strip()
            if "keine wesentlichen neuigkeiten" in text.lower():
                return None
            return text
        return None

    async def rate_relevance(
        self,
        content: str,
        topic_name: str,
        keywords: list[str],
        topic_id: Optional[int] = None,
    ) -> float:
        """Relevanz 0.0–1.0 bewerten."""
        if not self.text.is_meaningful(content):
            return 0.0

        prompt   = build_relevance_prompt(content, topic_name, keywords)
        response = await self.router.complete(LLMRequest(
            prompt      = prompt,
            max_tokens  = 10,
            temperature = 0.0,
            prompt_type = "relevance",
            topic_id    = topic_id,
            use_cache   = True,
        ))

        if response.success:
            try:
                import re
                match = re.search(r'\d+(?:\.\d+)?', response.content)
                if match:
                    val = float(match.group())
                    return min(1.0, max(0.0, val))
            except ValueError:
                pass
        return 0.5  # Neutral bei Fehler

    async def extract_keywords(self, content: str) -> list[str]:
        """Schlüsselbegriffe aus Text extrahieren."""
        prompt   = build_keyword_extraction_prompt(content)
        response = await self.router.complete(LLMRequest(
            prompt      = prompt,
            max_tokens  = 100,
            temperature = 0.1,
            prompt_type = "keywords",
        ))

        if response.success:
            try:
                return json.loads(response.content.strip())
            except json.JSONDecodeError:
                pass
        return []

    async def generate_search_queries(
        self,
        topic_name: str,
        description: str,
        existing_keywords: list[str],
    ) -> list[str]:
        """Optimale Suchanfragen für ein Topic generieren."""
        prompt   = build_search_queries_prompt(topic_name, description, existing_keywords)
        response = await self.router.complete(LLMRequest(
            prompt      = prompt,
            max_tokens  = 200,
            temperature = 0.3,
            prompt_type = "search_queries",
        ))

        if response.success:
            try:
                queries = json.loads(response.content.strip())
                return [q for q in queries if isinstance(q, str)][:5]
            except json.JSONDecodeError:
                pass
        # Fallback: direkte Keywords als Queries
        return existing_keywords[:5]


# Singleton
_processor: Optional[LLMProcessor] = None


def get_llm_processor() -> LLMProcessor:
    global _processor
    if _processor is None:
        _processor = LLMProcessor()
    return _processor
