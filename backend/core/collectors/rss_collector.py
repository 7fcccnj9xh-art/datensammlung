"""RSS/Atom Feed Collector mit Deduplizierung."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import feedparser
import httpx

from core.collectors.base_collector import BaseCollector, CollectorResult

logger = logging.getLogger(__name__)


class RSSCollector(BaseCollector):
    """
    RSS/Atom Feed-Collector.
    Lädt Feed, extrahiert Artikel, dedupliziert via URL-Hash.
    """

    async def _fetch(self, url: str, **kwargs) -> CollectorResult:
        """Feed abrufen und parsen."""
        try:
            response = await self.http_client.get(url)
            response.raise_for_status()

            feed = feedparser.parse(response.text)
            if feed.bozo and not feed.entries:
                return CollectorResult(url=url, success=False, error="Ungültiger Feed")

            # Feed-Metadaten
            feed_title = feed.feed.get("title", urlparse_domain(url))
            entries    = []
            for entry in feed.entries[:50]:  # Max 50 Einträge
                entry_data = self._parse_entry(entry, url)
                if entry_data:
                    entries.append(entry_data)

            return CollectorResult(
                url=url,
                content="",   # Wird aus entries zusammengesetzt
                title=feed_title,
                success=True,
                meta_data={
                    "feed_type":   "rss",
                    "feed_title":  feed_title,
                    "entries":     entries,
                    "entry_count": len(entries),
                },
                source_type="rss",
            )

        except Exception as e:
            return CollectorResult(url=url, success=False, error=str(e))

    def _parse_entry(self, entry, feed_url: str) -> Optional[dict]:
        """Einzelnen Feed-Eintrag in einheitliches Format konvertieren."""
        link = entry.get("link", "")
        if not link:
            return None

        # Datum parsen
        published = None
        for date_field in ("published_parsed", "updated_parsed", "created_parsed"):
            if entry.get(date_field):
                try:
                    import time as time_module
                    published = datetime(*entry[date_field][:6])
                    break
                except Exception:
                    pass

        # Content extrahieren
        content = ""
        if entry.get("content"):
            content = entry["content"][0].get("value", "")
        elif entry.get("summary"):
            content = entry["summary"]
        elif entry.get("description"):
            content = entry["description"]

        # HTML-Tags entfernen
        if content:
            from bs4 import BeautifulSoup
            soup    = BeautifulSoup(content, "lxml")
            content = soup.get_text(separator=" ", strip=True)

        return {
            "url":       link,
            "title":     entry.get("title", ""),
            "content":   content,
            "published": published.isoformat() if published else None,
            "author":    entry.get("author", ""),
            "tags":      [t.get("term", "") for t in entry.get("tags", [])],
        }

    async def fetch_entries(self, feed_url: str) -> list[dict]:
        """Feed-Einträge als Liste von Dictionaries zurückgeben."""
        result = await self.collect(feed_url)
        if result.success and result.meta_data.get("entries"):
            return result.meta_data["entries"]
        return []


def urlparse_domain(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(url).netloc
