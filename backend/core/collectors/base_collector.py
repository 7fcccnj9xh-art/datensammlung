"""
Basis-Collector: Abstrakte Basisklasse für alle Collector-Typen.
Stellt einheitliche Interface, Retry-Logic und Rate-Limiting bereit.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class CollectorResult:
    """Standardisiertes Ergebnis eines Collector-Aufrufs."""
    url:         str
    content:     str                     = ""
    title:       Optional[str]           = None
    author:      Optional[str]           = None
    published:   Optional[datetime]      = None
    language:    Optional[str]           = None
    meta_data:   dict[str, Any]          = field(default_factory=dict)
    source_type: str                     = "website"
    success:     bool                    = True
    error:       Optional[str]           = None
    fetched_at:  datetime                = field(default_factory=datetime.utcnow)
    http_status: Optional[int]           = None

    @property
    def domain(self) -> str:
        return urlparse(self.url).netloc

    @property
    def content_length(self) -> int:
        return len(self.content)


# Rate-Limiting: Letzte Request-Zeit pro Domain
_domain_last_request: dict[str, float] = {}
_domain_lock = asyncio.Lock()


class BaseCollector(ABC):
    """
    Abstrakte Basisklasse für alle Datensammler.

    Jeder Collector implementiert _fetch() und optional _parse().
    Die Basisklasse übernimmt:
    - HTTP-Client-Management
    - Rate-Limiting pro Domain
    - Retry-Logic mit exponential backoff
    - robots.txt-Prüfung
    - Einheitliches Error-Handling
    """

    # Standard HTTP-Client (geteilt über Instanzen)
    _http_client: Optional[httpx.AsyncClient] = None

    def __init__(self) -> None:
        self.settings = get_settings()
        self._robots_cache: dict[str, RobotFileParser] = {}

    @property
    def http_client(self) -> httpx.AsyncClient:
        """Shared HTTP-Client mit Browser-Headers."""
        if BaseCollector._http_client is None or BaseCollector._http_client.is_closed:
            BaseCollector._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.settings.scraping_timeout),
                headers={
                    "User-Agent":      self.settings.user_agent,
                    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
                    "Accept-Encoding": "gzip, deflate",
                    "DNT":             "1",
                },
                follow_redirects=True,
                max_redirects=5,
            )
        return BaseCollector._http_client

    @abstractmethod
    async def _fetch(self, url: str, **kwargs) -> CollectorResult:
        """
        Eigentliche Fetch-Logik – von Unterklassen zu implementieren.
        Muss CollectorResult zurückgeben.
        """
        ...

    async def collect(self, url: str, **kwargs) -> CollectorResult:
        """
        Öffentliche Methode: Holt URL mit Retry, Rate-Limit, robots.txt.
        """
        # robots.txt prüfen
        if self.settings.respect_robots_txt:
            if not await self._is_allowed(url):
                logger.info(f"robots.txt verbietet: {url}")
                return CollectorResult(
                    url=url, success=False,
                    error="robots.txt: Zugriff nicht erlaubt"
                )

        # Rate-Limiting
        await self._rate_limit(url)

        # Fetch mit Retry
        return await self._fetch_with_retry(url, **kwargs)

    async def collect_many(self, urls: list[str], **kwargs) -> list[CollectorResult]:
        """
        Mehrere URLs mit Parallelitäts-Kontrolle sammeln.
        """
        semaphore = asyncio.Semaphore(self.settings.max_concurrent_scrapers)

        async def _limited_collect(url: str) -> CollectorResult:
            async with semaphore:
                return await self.collect(url, **kwargs)

        return await asyncio.gather(*[_limited_collect(u) for u in urls])

    async def _fetch_with_retry(
        self, url: str, max_retries: int = 3, **kwargs
    ) -> CollectorResult:
        """Retry-Logic mit exponential backoff."""
        last_error: Optional[str] = None

        for attempt in range(max_retries):
            try:
                result = await self._fetch(url, **kwargs)
                if result.success:
                    return result
                last_error = result.error

            except httpx.HTTPStatusError as e:
                last_error = f"HTTP {e.response.status_code}"
                if e.response.status_code in (403, 404, 410):
                    # Endgültige Fehler: nicht erneut versuchen
                    break
                if e.response.status_code == 429:
                    # Rate-Limit: länger warten
                    await asyncio.sleep(60)

            except httpx.TimeoutException:
                last_error = "Timeout"

            except Exception as e:
                last_error = str(e)

            if attempt < max_retries - 1:
                # Exponential backoff: 2s, 4s, 8s
                wait = (2 ** (attempt + 1)) + random.uniform(0, 1)
                logger.debug(f"Retry {attempt + 1}/{max_retries} für {url} in {wait:.1f}s")
                await asyncio.sleep(wait)

        logger.warning(f"Alle Retries fehlgeschlagen für {url}: {last_error}")
        return CollectorResult(url=url, success=False, error=last_error)

    async def _rate_limit(self, url: str) -> None:
        """Mindestabstand zwischen Requests zur gleichen Domain."""
        domain = urlparse(url).netloc
        delay  = random.uniform(
            self.settings.scraping_delay_min,
            self.settings.scraping_delay_max,
        )

        async with _domain_lock:
            last = _domain_last_request.get(domain, 0)
            elapsed = time.monotonic() - last
            if elapsed < delay:
                wait = delay - elapsed
                await asyncio.sleep(wait)
            _domain_last_request[domain] = time.monotonic()

    async def _is_allowed(self, url: str) -> bool:
        """robots.txt-Check mit Caching."""
        domain = urlparse(url).netloc
        if domain not in self._robots_cache:
            robots_url = f"{urlparse(url).scheme}://{domain}/robots.txt"
            rp = RobotFileParser()
            rp.set_url(robots_url)
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    response = await client.get(robots_url)
                    if response.status_code == 200:
                        rp.parse(response.text.splitlines())
                    else:
                        # Kein robots.txt → alles erlaubt
                        return True
            except Exception:
                return True  # Bei Fehler: erlauben
            self._robots_cache[domain] = rp

        return self._robots_cache[domain].can_fetch(self.settings.user_agent, url)

    async def close(self) -> None:
        """HTTP-Client schließen."""
        if BaseCollector._http_client and not BaseCollector._http_client.is_closed:
            await BaseCollector._http_client.aclose()
            BaseCollector._http_client = None
