"""Strukturierte Daten Endpunkte (generisch)."""

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from config.database import get_db
from models.structured_data import StructuredData

router = APIRouter()


class StructuredDataCreate(BaseModel):
    """Request-Body für externe POSTs (z.B. Whisper-Transkriptions-Pipeline)."""
    data:           dict
    data_timestamp: Optional[datetime] = None
    source_id:      Optional[int]      = None
    location:       Optional[dict]     = None


@router.get("/types")
async def list_data_types(db: AsyncSession = Depends(get_db)):
    """Alle vorhandenen Datentypen auflisten."""
    from sqlalchemy import distinct, func
    result = await db.execute(
        select(StructuredData.data_type, func.count().label("count"))
        .group_by(StructuredData.data_type)
    )
    return [{"type": row[0], "count": row[1]} for row in result]


@router.post("/{data_type}", status_code=201)
async def create_data(
    data_type: str,
    payload:   StructuredDataCreate,
    db:        AsyncSession = Depends(get_db),
):
    """Legt einen StructuredData-Eintrag an. data_type ist frei wählbar
    (z.B. 'transcript'); das gesamte payload.data landet als JSON im 'data'-Feld."""
    eintrag = StructuredData(
        data_type      = data_type,
        data           = payload.data,
        data_timestamp = payload.data_timestamp or datetime.utcnow(),
        source_id      = payload.source_id,
        location       = payload.location,
    )
    db.add(eintrag)
    await db.flush()
    return {
        "id":             eintrag.id,
        "data_type":      eintrag.data_type,
        "data_timestamp": eintrag.data_timestamp.isoformat(),
    }


@router.get("/{data_type}")
async def get_data(
    data_type: str,
    days:      int = Query(7, ge=1, le=365),
    page:      int = Query(1, ge=1),
    per_page:  int = Query(50, ge=1, le=500),
    db:        AsyncSession = Depends(get_db),
):
    """Strukturierte Daten eines Typs abrufen."""
    since = datetime.utcnow() - timedelta(days=days)
    query = (
        select(StructuredData)
        .where(StructuredData.data_type == data_type, StructuredData.data_timestamp >= since)
        .order_by(desc(StructuredData.data_timestamp))
    )
    result = await db.execute(query.offset((page - 1) * per_page).limit(per_page))
    return [
        {
            "id":             d.id,
            "data_type":      d.data_type,
            "data":           d.data,
            "data_timestamp": d.data_timestamp.isoformat(),
            "location":       d.location,
        }
        for d in result.scalars()
    ]
