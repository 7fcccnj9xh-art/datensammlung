"""
Recherche-Task: Vollständiger Recherche-Workflow für ein Topic.
1. Topic-Config laden → 2. Suchen → 3. Scrapen → 4. LLM → 5. In DB speichern
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy import select

from config.database import get_db_session
from config.settings import get_settings
from core.collectors.rss_collector import RSSCollector
from core.collectors.web_scraper import WebScraper
from core.processors.llm_processor import get_llm_processor
from core.processors.text_processor import get_text_processor
from models.research import ResearchResult
from models.source import Source
from models.topic import Topic

logger = logging.getLogger(__name__)


class ResearchTask:
    """
    Vollständiger Recherche-Workflow für ein einzelnes Topic.
    """

    def __init__(self) -> None:
        self.settings       = get_settings()
        self.web_scraper    = WebScraper()
        self.rss_collector  = RSSCollector()
        self.text_proc      = get_text_processor()
        self.llm_proc       = get_llm_processor()

    async def run(self, topic_id: int, job_id: Optional[int] = None) -> dict:
        """
        Hauptmethode: Recherche für ein Topic durchführen.
        Gibt Metriken-Dict zurück.
        """
        metrics = {
            "topic_id":       topic_id,
            "urls_fetched":   0,
            "urls_skipped":   0,
            "results_saved":  0,
            "new_content":    False,
        }

        # Topic laden
        async with get_db_session() as db:
            result = await db.execute(select(Topic).where(Topic.id == topic_id))
            topic  = result.scalar_one_or_none()

        if not topic or not topic.is_active:
            logger.warning(f"Topic {topic_id} nicht gefunden oder inaktiv")
            return metrics

        logger.info(f"Starte Recherche für Topic: {topic.name}")

        # 1. Bevorzugte Quellen (RSS-Feeds, konfig. Websites) prüfen
        preferred_sources = await self._get_preferred_sources(topic_id)
        for source in preferred_sources:
            result_data = await self._process_source(source, topic, job_id)
            if result_data:
                metrics["results_saved"] += 1
                metrics["urls_fetched"]  += 1
                if result_data.get("is_new"):
                    metrics["new_content"] = True
            else:
                metrics["urls_skipped"] += 1

        # 2. Web-Suche für Topic-Keywords (Fallback: Topic-Name)
        keywords = topic.keywords or [topic.name]
        if keywords:
            search_results = await self._search_web_with_keywords(topic, keywords)
            for url in search_results[:self.settings.search_max_results]:
                result_data = await self._process_url(url, topic, job_id)
                if result_data:
                    metrics["results_saved"] += 1
                    metrics["urls_fetched"]  += 1
                    if result_data.get("is_new"):
                        metrics["new_content"] = True
                else:
                    metrics["urls_skipped"] += 1

        logger.info(
            f"Recherche abgeschlossen: Topic {topic.name} | "
            f"{metrics['results_saved']} gespeichert, "
            f"{metrics['urls_skipped']} übersprungen"
        )
        return metrics

    async def _get_preferred_sources(self, topic_id: int) -> list[Source]:
        """Bevorzugte Quellen für ein Topic aus DB laden."""
        async with get_db_session() as db:
            from models.topic import TopicSource
            result = await db.execute(
                select(Source)
                .join(TopicSource, Source.id == TopicSource.source_id)
                .where(TopicSource.topic_id == topic_id, Source.is_active == True)
                .order_by(TopicSource.priority)
            )
            return result.scalars().all()

    async def _process_source(
        self,
        source: Source,
        topic: Topic,
        job_id: Optional[int],
    ) -> Optional[dict]:
        """Einzelne Quelle verarbeiten."""
        if source.is_rss:
            return await self._process_rss_source(source, topic, job_id)
        else:
            return await self._process_url(source.url, topic, job_id, source_id=source.id)

    async def _process_rss_source(
        self,
        source: Source,
        topic: Topic,
        job_id: Optional[int],
    ) -> Optional[dict]:
        """RSS-Feed verarbeiten: alle neuen Einträge als Ergebnisse speichern."""
        entries = await self.rss_collector.fetch_entries(source.url)
        saved   = 0

        for entry in entries[:10]:  # Max 10 Einträge pro Feed
            content = entry.get("content", "")
            if not self.text_proc.is_meaningful(content):
                continue

            content_hash = self.text_proc.compute_hash(content)
            if await self._hash_exists(content_hash):
                continue

            summary = await self.llm_proc.summarize(
                content     = content,
                topic_name  = topic.name,
                topic_id    = topic.id,
                job_id      = job_id,
                llm_provider= topic.llm_provider,
                llm_model   = topic.llm_model,
            )

            await self._save_result(
                topic_id     = topic.id,
                source_id    = source.id,
                job_id       = job_id,
                raw_content  = content,
                clean_content= self.text_proc.clean(content),
                summary      = summary,
                content_hash = content_hash,
                meta_data    = {
                    "url":       entry.get("url"),
                    "title":     entry.get("title"),
                    "published": entry.get("published"),
                    "source":    source.url,
                },
            )
            saved += 1

        if saved:
            await self._update_source_stats(source.id, error=False)
        return {"is_new": saved > 0, "count": saved} if saved else None

    async def _process_url(
        self,
        url: str,
        topic: Topic,
        job_id: Optional[int],
        source_id: Optional[int] = None,
    ) -> Optional[dict]:
        """Einzelne URL scrapen und verarbeiten."""
        result = await self.web_scraper.collect(url)
        if not result.success or not self.text_proc.is_meaningful(result.content):
            return None

        content_hash = self.text_proc.compute_hash(result.content)
        if await self._hash_exists(content_hash):
            return None  # Duplikat

        # Relevanz prüfen
        relevance = await self.llm_proc.rate_relevance(
            content    = result.content,
            topic_name = topic.name,
            keywords   = topic.keywords,
            topic_id   = topic.id,
        )
        if relevance < 0.3:
            logger.debug(f"URL als irrelevant eingestuft (Score: {relevance}): {url}")
            return None

        # Zusammenfassung erstellen
        summary = await self.llm_proc.summarize(
            content     = result.content,
            topic_name  = topic.name,
            topic_id    = topic.id,
            job_id      = job_id,
            llm_provider= topic.llm_provider,
            llm_model   = topic.llm_model,
        )

        # In DB speichern
        await self._save_result(
            topic_id      = topic.id,
            source_id     = source_id,
            job_id        = job_id,
            raw_content   = result.content,
            clean_content = self.text_proc.clean(result.content),
            summary       = summary,
            content_hash  = content_hash,
            language      = result.language or "de",
            relevance_score = relevance,
            meta_data     = {
                **result.meta_data,
                "url":    url,
                "title":  result.title,
                "author": result.author,
            },
        )

        # Quelle in DB anlegen/aktualisieren
        if not source_id:
            await self._upsert_source(url, result)

        return {"is_new": True}

    async def _search_web_with_keywords(self, topic: Topic, keywords: list[str]) -> list[str]:
        """Web-Suche via SearXNG mit expliziten Keywords."""
        return await self._search_web_queries(keywords[:3])

    async def _search_web(self, topic: Topic) -> list[str]:
        """Web-Suche via SearXNG oder DuckDuckGo."""
        return await self._search_web_queries((topic.keywords or [topic.name])[:3])

    async def _search_web_queries(self, queries: list[str]) -> list[str]:
        """Web-Suche für eine Liste von Suchanfragen."""
        urls = []

        for query in queries:
            try:
                found = await self._searxng_search(query)
                urls.extend(found)
            except Exception:
                try:
                    found = await self._duckduckgo_search(query)
                    urls.extend(found)
                except Exception as e:
                    logger.warning(f"Suche fehlgeschlagen für '{query}': {e}")

        return list(dict.fromkeys(urls))  # Deduplizierung, Reihenfolge beibehalten

    async def _searxng_search(self, query: str) -> list[str]:
        """Suche via lokalem SearXNG."""
        params = {
            "q":       query,
            "format":  "json",
            "engines": "google,bing,duckduckgo",
            "language":"de",
        }
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{self.settings.searxng_url}/search",
                params=params,
            )
            response.raise_for_status()
            data = response.json()
        return [r["url"] for r in data.get("results", [])[:10] if r.get("url")]

    async def _duckduckgo_search(self, query: str) -> list[str]:
        """Fallback-Suche via DuckDuckGo Instant Answer API."""
        # Einfache HTML-Suche (kein offizieller API-Key nötig)
        params = {"q": query, "format": "json", "no_html": "1"}
        async with httpx.AsyncClient(timeout=10, headers={"User-Agent": self.settings.user_agent}) as client:
            response = await client.get("https://api.duckduckgo.com/", params=params)
            data     = response.json()
        urls = []
        for result in data.get("Results", []) + data.get("RelatedTopics", []):
            if result.get("FirstURL"):
                urls.append(result["FirstURL"])
        return urls[:5]

    # ----------------------------------------------------------
    # DB-Hilfsmethoden
    # ----------------------------------------------------------

    async def _hash_exists(self, content_hash: str) -> bool:
        """Prüft ob Content-Hash bereits in DB vorhanden."""
        async with get_db_session() as db:
            result = await db.execute(
                select(ResearchResult.id)
                .where(ResearchResult.content_hash == content_hash)
                .limit(1)
            )
            return result.scalar_one_or_none() is not None

    async def _save_result(self, **kwargs) -> int:
        """Recherche-Ergebnis in DB speichern."""
        # meta_data: datetime-Objekte in Strings umwandeln
        if "meta_data" in kwargs and isinstance(kwargs["meta_data"], dict):
            import json
            def _default(o):
                if hasattr(o, "isoformat"):
                    return o.isoformat()
                return str(o)
            kwargs["meta_data"] = json.loads(json.dumps(kwargs["meta_data"], default=_default))

        async with get_db_session() as db:
            result = ResearchResult(**kwargs)
            db.add(result)
            await db.flush()
            return result.id

    async def _upsert_source(self, url: str, collector_result) -> None:
        """Neue Quelle anlegen oder vorhandene aktualisieren."""
        from urllib.parse import urlparse
        from sqlalchemy.dialects.mysql import insert as mysql_insert

        domain = urlparse(url).netloc
        async with get_db_session() as db:
            existing = await db.execute(
                select(Source).where(Source.url == url).limit(1)
            )
            source = existing.scalar_one_or_none()
            if not source:
                source = Source(
                    url          = url,
                    domain       = domain,
                    title        = collector_result.title or domain,
                    source_type  = "website",
                    last_fetched = datetime.now(timezone.utc),
                    fetch_count  = 1,
                )
                db.add(source)
            else:
                source.last_fetched = datetime.now(timezone.utc)
                source.fetch_count  += 1

    async def _update_source_stats(self, source_id: int, error: bool) -> None:
        """Quellen-Statistiken aktualisieren."""
        async with get_db_session() as db:
            result = await db.execute(select(Source).where(Source.id == source_id))
            source = result.scalar_one_or_none()
            if source:
                source.last_fetched = datetime.now(timezone.utc)
                if error:
                    source.error_count += 1
                else:
                    source.fetch_count += 1
