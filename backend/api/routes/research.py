"""Recherche-Endpunkte: Ergebnisse abrufen, on-demand triggern, WebSocket."""

from __future__ import annotations

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_db
from core.scheduler.scheduler import get_scheduler
from models.research import ResearchResult
from models.topic import Topic

router = APIRouter()


class AdHocResearch(BaseModel):
    query:         str
    urls:          list[str]       = []
    llm_provider:  Optional[str]  = None
    save_as_topic: bool            = False
    topic_name:    Optional[str]  = None


@router.get("/results/{topic_id}")
async def get_results(
    topic_id:  int,
    page:      int = Query(1, ge=1),
    per_page:  int = Query(20, ge=1, le=100),
    min_score: Optional[float] = None,
    db:        AsyncSession = Depends(get_db),
):
    """Alle Recherche-Ergebnisse für ein Topic (paginiert)."""
    query = (
        select(ResearchResult)
        .where(ResearchResult.topic_id == topic_id)
        .order_by(desc(ResearchResult.created_at))
    )
    if min_score:
        query = query.where(ResearchResult.relevance_score >= min_score)

    total_q = await db.execute(
        select(__import__('sqlalchemy').func.count()).select_from(query.subquery())
    )
    total  = total_q.scalar()
    result = await db.execute(query.offset((page - 1) * per_page).limit(per_page))
    items  = result.scalars().all()

    return {
        "total":   total,
        "page":    page,
        "per_page": per_page,
        "items":   [_result_to_dict(r) for r in items],
    }


@router.get("/results/{topic_id}/latest")
async def get_latest_result(topic_id: int, db: AsyncSession = Depends(get_db)):
    """Neuestes Recherche-Ergebnis für ein Topic."""
    result = await db.execute(
        select(ResearchResult)
        .where(ResearchResult.topic_id == topic_id)
        .order_by(desc(ResearchResult.created_at))
        .limit(1)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(404, "Noch keine Ergebnisse für dieses Topic")
    return _result_to_dict(item)


@router.post("/trigger/{topic_id}")
async def trigger_research(topic_id: int, db: AsyncSession = Depends(get_db)):
    """Sofortige Recherche für ein Topic (async)."""
    topic_r = await db.execute(select(Topic).where(Topic.id == topic_id))
    topic   = topic_r.scalar_one_or_none()
    if not topic:
        raise HTTPException(404, "Topic nicht gefunden")
    if topic.status != "active":
        raise HTTPException(400, "Topic ist nicht aktiv")

    # Im Hintergrund ausführen
    asyncio.create_task(
        get_scheduler().job_manager.run_research_job(topic_id=topic_id, triggered_by="api")
    )
    return {"message": f"Recherche für '{topic.name}' gestartet", "topic_id": topic_id}


@router.post("/adhoc")
async def adhoc_research(data: AdHocResearch):
    """
    Ad-hoc Recherche ohne gespeichertes Topic.
    Ohne URLs: automatische Suche via SearXNG.
    """
    from core.collectors.web_scraper import WebScraper
    from core.collectors.search_collector import SearchCollector
    from core.processors.llm_processor import get_llm_processor
    from core.processors.text_processor import get_text_processor
    from config.settings import get_settings

    scraper  = WebScraper()
    text_p   = get_text_processor()
    llm_p    = get_llm_processor()
    results  = []

    urls = data.urls[:5]

    # Keine URLs angegeben → SearXNG suchen
    if not urls:
        try:
            settings = get_settings()
            searcher = SearchCollector(searxng_url=settings.searxng_url)
            search_results = await searcher.search(data.query, num_results=5)
            urls = [r["url"] for r in search_results if r.get("url")]
        except Exception as e:
            pass  # Ohne SearXNG direkt leere Antwort

    for url in urls:
        try:
            collected = await scraper.collect(url)
            if collected.success and text_p.is_meaningful(collected.content):
                summary = await llm_p.summarize(
                    content     = collected.content,
                    topic_name  = data.query,
                    llm_provider= data.llm_provider,
                )
                results.append({
                    "url":     url,
                    "title":   collected.title,
                    "summary": summary,
                    "content": text_p.truncate(collected.content, 500),
                })
        except Exception:
            continue

    return {"query": data.query, "results": results, "count": len(results)}


@router.websocket("/ws/{job_id}")
async def websocket_job_status(websocket: WebSocket, job_id: int):
    """WebSocket: Live-Updates für einen laufenden Job."""
    await websocket.accept()
    try:
        while True:
            status = await get_scheduler().job_manager.get_job_status(job_id)
            if status:
                await websocket.send_text(json.dumps(status))
                if status["status"] in ("completed", "failed", "cancelled"):
                    break
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
    finally:
        await websocket.close()


def _result_to_dict(r: ResearchResult) -> dict:
    return {
        "id":              r.id,
        "topic_id":        r.topic_id,
        "source_id":       r.source_id,
        "title":           r.title,
        "summary":         r.summary,
        "delta_summary":   r.delta_summary,
        "relevance_score": float(r.relevance_score) if r.relevance_score else None,
        "language":        r.language,
        "version":         r.version,
        "meta_data":       r.meta_data,
        "source_url":      r.source_url,
        "created_at":      r.created_at.isoformat(),
    }
