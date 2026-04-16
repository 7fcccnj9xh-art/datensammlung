"""SearXNG-Suche: Liefert URLs für Ad-hoc-Recherchen."""

from __future__ import annotations

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class SearchCollector:
    """Sucht via SearXNG und gibt URLs zurück."""

    def __init__(self, searxng_url: str) -> None:
        self.searxng_url = searxng_url.rstrip("/")

    async def search(self, query: str, num_results: int = 5) -> list[dict]:
        """SearXNG-Suche, gibt Liste von {url, title, snippet} zurück."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.searxng_url}/search",
                    params={
                        "q":      query,
                        "format": "json",
                        "lang":   "de",
                    },
                )
                response.raise_for_status()
                data = response.json()
                results = []
                for r in data.get("results", [])[:num_results]:
                    results.append({
                        "url":     r.get("url", ""),
                        "title":   r.get("title", ""),
                        "snippet": r.get("content", ""),
                    })
                logger.info(f"SearXNG: {len(results)} Ergebnisse für '{query}'")
                return results
        except Exception as e:
            logger.warning(f"SearXNG-Suche fehlgeschlagen: {e}")
            return []
