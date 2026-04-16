"""CRUD-Endpunkte für Topics."""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_db
from models.topic import ResearchInterval, Topic
from core.scheduler.scheduler import get_scheduler

router = APIRouter()


# ----------------------------------------------------------
# Pydantic Schemas
# ----------------------------------------------------------
class TopicCreate(BaseModel):
    name:          str
    description:   Optional[str]  = None
    category:      Optional[str]  = None
    schedule_type: str             = "sporadic"
    llm_provider:  Optional[str]  = None
    llm_model:     Optional[str]  = None
    search_config: Optional[dict] = None
    system_prompt: Optional[str]  = None
    tags:          Optional[list] = None
    priority:      int             = Field(5, ge=1, le=10)


class TopicUpdate(BaseModel):
    name:          Optional[str]  = None
    description:   Optional[str]  = None
    category:      Optional[str]  = None
    schedule_type: Optional[str]  = None
    status:        Optional[str]  = None
    llm_provider:  Optional[str]  = None
    llm_model:     Optional[str]  = None
    search_config: Optional[dict] = None
    system_prompt: Optional[str]  = None
    tags:          Optional[list] = None
    priority:      Optional[int]  = None


class IntervalCreate(BaseModel):
    interval_type:    str            = "fixed"
    interval_seconds: Optional[int] = None
    cron_expression:  Optional[str] = None
    timeout_seconds:  int            = 300


# ----------------------------------------------------------
# Routen
# ----------------------------------------------------------
@router.get("/")
async def list_topics(
    status:   Optional[str] = None,
    category: Optional[str] = None,
    page:     int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Alle Topics auflisten (paginiert)."""
    query = select(Topic)
    if status:
        query = query.where(Topic.status == status)
    if category:
        query = query.where(Topic.category == category)

    # Paginierung
    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total        = total_result.scalar()

    query  = query.order_by(Topic.priority, Topic.name)
    query  = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    topics = result.scalars().all()

    return {
        "total":   total,
        "page":    page,
        "per_page": per_page,
        "items":   [_topic_to_dict(t) for t in topics],
    }


@router.post("/", status_code=201)
async def create_topic(data: TopicCreate, db: AsyncSession = Depends(get_db)):
    """Neues Topic anlegen."""
    # Slug aus Name generieren
    slug = _make_slug(data.name)
    existing = await db.execute(select(Topic).where(Topic.slug == slug))
    if existing.scalar_one_or_none():
        slug = f"{slug}-{int(__import__('time').time())}"

    topic = Topic(slug=slug, **data.model_dump())
    db.add(topic)
    await db.flush()
    await db.refresh(topic)
    return _topic_to_dict(topic)


@router.get("/{topic_id}")
async def get_topic(topic_id: int, db: AsyncSession = Depends(get_db)):
    """Einzelnes Topic abrufen."""
    topic = await _get_or_404(db, topic_id)
    return _topic_to_dict(topic)


@router.put("/{topic_id}")
async def update_topic(
    topic_id: int, data: TopicUpdate, db: AsyncSession = Depends(get_db)
):
    """Topic aktualisieren."""
    topic = await _get_or_404(db, topic_id)
    for key, value in data.model_dump(exclude_none=True).items():
        setattr(topic, key, value)
    await db.flush()
    await db.refresh(topic)

    # Scheduler anpassen wenn Status geändert
    scheduler = get_scheduler()
    if data.status == "paused":
        await scheduler.pause_topic_job(topic_id)
    elif data.status == "active":
        await scheduler.resume_topic_job(topic_id)

    return _topic_to_dict(topic)


@router.delete("/{topic_id}", status_code=204)
async def delete_topic(topic_id: int, db: AsyncSession = Depends(get_db)):
    """Topic löschen (inkl. aller Ergebnisse via CASCADE)."""
    topic = await _get_or_404(db, topic_id)
    await get_scheduler().remove_topic_job(topic_id)
    await db.delete(topic)


@router.post("/{topic_id}/trigger")
async def trigger_research(topic_id: int, db: AsyncSession = Depends(get_db)):
    """Sofortige Recherche für ein Topic auslösen."""
    topic = await _get_or_404(db, topic_id)
    if topic.status != "active":
        raise HTTPException(400, "Topic ist nicht aktiv")

    job_id = await get_scheduler().trigger_now(topic_id)
    return {"job_id": job_id, "message": f"Recherche für '{topic.name}' gestartet"}


@router.post("/{topic_id}/interval")
async def set_interval(
    topic_id: int, data: IntervalCreate, db: AsyncSession = Depends(get_db)
):
    """Recherche-Intervall für ein Topic setzen."""
    topic = await _get_or_404(db, topic_id)

    # Alte Intervalle deaktivieren
    old = await db.execute(select(ResearchInterval).where(ResearchInterval.topic_id == topic_id))
    for interval in old.scalars():
        interval.is_active = False

    # Neues Intervall
    new_interval = ResearchInterval(
        topic_id         = topic_id,
        interval_type    = data.interval_type,
        interval_seconds = data.interval_seconds,
        cron_expression  = data.cron_expression,
        timeout_seconds  = data.timeout_seconds,
        is_active        = True,
    )
    db.add(new_interval)
    await db.flush()

    # Scheduler aktualisieren
    await get_scheduler().schedule_topic_job(topic_id, new_interval)

    return {"message": "Intervall gesetzt", "interval_id": new_interval.id}


# ----------------------------------------------------------
# Hilfsfunktionen
# ----------------------------------------------------------
async def _get_or_404(db: AsyncSession, topic_id: int) -> Topic:
    result = await db.execute(select(Topic).where(Topic.id == topic_id))
    topic  = result.scalar_one_or_none()
    if not topic:
        raise HTTPException(404, f"Topic {topic_id} nicht gefunden")
    return topic


def _make_slug(name: str) -> str:
    import re
    slug = name.lower().replace(" ", "-")
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    return slug[:200]


def _topic_to_dict(t: Topic) -> dict:
    return {
        "id":             t.id,
        "name":           t.name,
        "slug":           t.slug,
        "description":    t.description,
        "category":       t.category,
        "schedule_type":  t.schedule_type,
        "status":         t.status,
        "llm_provider":   t.llm_provider,
        "llm_model":      t.llm_model,
        "search_config":  t.search_config,
        "tags":           t.tags,
        "priority":       t.priority,
        "created_at":     t.created_at.isoformat(),
        "updated_at":     t.updated_at.isoformat(),
        "last_researched": t.last_researched.isoformat() if t.last_researched else None,
    }
