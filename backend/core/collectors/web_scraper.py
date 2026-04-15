"""
Web-Scraper: Statische und dynamische Webseiten scrapen.
Primär BeautifulSoup, optional Playwright für JS-heavy Seiten.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from readability import Document

from core.collectors.base_collector import BaseCollector, CollectorResult

logger = logging.getLogger(__name__)

# HTML-Tags die Hauptinhalt enthalten (vs. Navigation/Ads)
CONTENT_TAGS = ["article", "main", "section", "[role='main']", ".content", "#content"]

# Tags die immer entfernt werden
NOISE_TAGS = [
    "script", "style", "nav", "header", "footer", "aside",
    "advertisement", ".ads", ".cookie-banner", ".newsletter",
    "noscript", "iframe",
]


class WebScraper(BaseCollector):
    """
    Web-Scraper mit intelligenter Content-Extraktion.
    Nutzt readability-lxml für saubere Hauptinhalt-Extraktion.
    """

    async def _fetch(self, url: str, **kwargs) -> CollectorResult:
        """URL abrufen und Content extrahieren."""
        try:
            response = await self.http_client.get(url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                return CollectorResult(
                    url=url, success=False,
                    error=f"Kein HTML-Content: {content_type}",
                    http_status=response.status_code,
                )

            result = self._parse_html(url, response.text)
            result.http_status = response.status_code
            return result

        except httpx.HTTPStatusError as e:
            return CollectorResult(
                url=url, success=False,
                error=f"HTTP {e.response.status_code}",
                http_status=e.response.status_code,
            )

    def _parse_html(self, url: str, html: str) -> CollectorResult:
        """HTML parsen und Hauptinhalt extrahieren."""
        # readability für Hauptinhalt-Extraktion
        try:
            doc     = Document(html)
            title   = doc.title()
            content = doc.summary(html_partial=True)
        except Exception:
            title   = ""
            content = html

        # BeautifulSoup für Metadaten und Bereinigung
        soup = BeautifulSoup(content, "lxml")

        # Störelemente entfernen
        for tag_name in NOISE_TAGS:
            for tag in soup.select(tag_name):
                tag.decompose()

        # Reinen Text extrahieren
        clean_text = soup.get_text(separator="\n", strip=True)
        clean_text = self._clean_text(clean_text)

        # Metadaten aus Original-HTML
        soup_full = BeautifulSoup(html, "lxml")
        meta = self._extract_metadata(url, soup_full, title)

        return CollectorResult(
            url=url,
            content=clean_text,
            title=meta.get("title") or title,
            author=meta.get("author"),
            published=meta.get("published"),
            language=meta.get("language"),
            meta_data=meta,
            source_type="website",
            success=bool(clean_text.strip()),
        )

    def _extract_metadata(self, url: str, soup: BeautifulSoup, fallback_title: str) -> dict:
        """Metadaten aus HTML-Kopf extrahieren."""
        meta = {"url": url}

        # Titel
        title_tag = (
            soup.find("meta", property="og:title") or
            soup.find("meta", {"name": "title"}) or
            soup.find("title")
        )
        if title_tag:
            meta["title"] = (
                title_tag.get("content") or
                getattr(title_tag, "string", None) or
                fallback_title
            )

        # Autor
        author_tag = (
            soup.find("meta", {"name": "author"}) or
            soup.find("meta", property="article:author")
        )
        if author_tag:
            meta["author"] = author_tag.get("content", "")

        # Veröffentlichungsdatum
        date_tag = (
            soup.find("meta", property="article:published_time") or
            soup.find("meta", {"name": "date"}) or
            soup.find("time", {"itemprop": "datePublished"})
        )
        if date_tag:
            date_str = date_tag.get("content") or date_tag.get("datetime") or ""
            meta["published_str"] = date_str
            try:
                from dateutil import parser as dateutil_parser
                meta["published"] = dateutil_parser.parse(date_str)
            except Exception:
                pass

        # Sprache
        html_tag = soup.find("html")
        if html_tag and html_tag.get("lang"):
            meta["language"] = html_tag.get("lang", "")[:5]

        # Description
        desc_tag = (
            soup.find("meta", property="og:description") or
            soup.find("meta", {"name": "description"})
        )
        if desc_tag:
            meta["description"] = desc_tag.get("content", "")

        # Canonical URL
        canonical = soup.find("link", {"rel": "canonical"})
        if canonical:
            meta["canonical_url"] = canonical.get("href", url)

        return meta

    def _clean_text(self, text: str) -> str:
        """Text bereinigen: Leerzeilen, Whitespace, etc."""
        # Mehrfache Leerzeilen reduzieren
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Whitespace am Zeilenanfang/-ende
        lines = [line.strip() for line in text.splitlines()]
        # Leere Zeilen zusammenfassen
        result = []
        prev_empty = False
        for line in lines:
            if not line:
                if not prev_empty:
                    result.append("")
                prev_empty = True
            else:
                result.append(line)
                prev_empty = False
        return "\n".join(result).strip()

    async def scrape_links(self, url: str, filter_domain: bool = True) -> list[str]:
        """Alle Links einer Seite extrahieren."""
        result = await self.collect(url)
        if not result.success:
            return []

        response = await self.http_client.get(url)
        soup     = BeautifulSoup(response.text, "lxml")
        base     = urlparse(url)
        links    = []

        for a_tag in soup.find_all("a", href=True):
            href = urljoin(url, a_tag["href"])
            parsed = urlparse(href)
            if parsed.scheme not in ("http", "https"):
                continue
            if filter_domain and parsed.netloc != base.netloc:
                continue
            links.append(href)

        return list(set(links))
