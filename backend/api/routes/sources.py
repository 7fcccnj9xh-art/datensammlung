"""Quellen-Verwaltung."""

from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from config.database import get_db
from models.source import Source

router = APIRouter()


class SourceCreate(BaseModel):
    url:          str
    title:        Optional[str]  = None
    description:  Optional[str]  = None
    source_type:  str             = "website"
    trust_score:  float           = 0.5


@router.get("/")
async def list_sources(
    source_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(Source).where(Source.is_active == True)
    if source_type:
        query = query.where(Source.source_type == source_type)
    query  = query.order_by(desc(Source.trust_score))

    total_r = await db.execute(select(func.count()).select_from(query.subquery()))
    result  = await db.execute(query.offset((page - 1) * per_page).limit(per_page))
    return {
        "total": total_r.scalar(),
        "items": [_source_to_dict(s) for s in result.scalars()],
    }


@router.post("/", status_code=201)
async def create_source(data: SourceCreate, db: AsyncSession = Depends(get_db)):
    from urllib.parse import urlparse
    domain = urlparse(data.url).netloc
    source = Source(domain=domain, **data.model_dump())
    db.add(source)
    await db.flush()
    return _source_to_dict(source)


@router.get("/{source_id}")
async def get_source(source_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(404, "Quelle nicht gefunden")
    return _source_to_dict(source)


@router.delete("/{source_id}", status_code=204)
async def delete_source(source_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(404, "Quelle nicht gefunden")
    source.is_active = False  # Soft-Delete


def _source_to_dict(s: Source) -> dict:
    return {
        "id":           s.id,
        "url":          s.url,
        "domain":       s.domain,
        "title":        s.title,
        "source_type":  s.source_type,
        "trust_score":  float(s.trust_score),
        "is_active":    s.is_active,
        "fetch_count":  s.fetch_count,
        "error_count":  s.error_count,
        "last_fetched": s.last_fetched.isoformat() if s.last_fetched else None,
    }
