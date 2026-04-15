"""Job-Monitoring Endpunkte."""

from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from config.database import get_db
from core.scheduler.scheduler import get_scheduler
from models.job import Job

router = APIRouter()


@router.get("/")
async def list_jobs(
    status:   Optional[str] = None,
    job_type: Optional[str] = None,
    page:     int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
    db:       AsyncSession = Depends(get_db),
):
    """Job-Liste mit Filter und Paginierung."""
    query = select(Job).order_by(desc(Job.created_at))
    if status:
        query = query.where(Job.status == status)
    if job_type:
        query = query.where(Job.job_type == job_type)

    total_r = await db.execute(select(func.count()).select_from(query.subquery()))
    result  = await db.execute(query.offset((page - 1) * per_page).limit(per_page))
    return {
        "total": total_r.scalar(),
        "items": [_job_to_dict(j) for j in result.scalars()],
    }


@router.get("/running")
async def get_running_jobs(db: AsyncSession = Depends(get_db)):
    """Alle aktuell laufenden Jobs."""
    result = await db.execute(
        select(Job).where(Job.status.in_(["queued", "running"])).order_by(Job.created_at)
    )
    return [_job_to_dict(j) for j in result.scalars()]


@router.get("/scheduled")
async def get_scheduled_jobs():
    """Geplante Jobs aus dem Scheduler."""
    return get_scheduler().get_scheduled_jobs()


@router.get("/{job_id}")
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job    = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, f"Job {job_id} nicht gefunden")
    return _job_to_dict(job)


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: int):
    cancelled = await get_scheduler().job_manager.cancel_job(job_id)
    if not cancelled:
        raise HTTPException(400, "Job kann nicht abgebrochen werden")
    return {"message": f"Job {job_id} abgebrochen"}


def _job_to_dict(j: Job) -> dict:
    return {
        "id":               j.id,
        "job_type":         j.job_type,
        "topic_id":         j.topic_id,
        "triggered_by":     j.triggered_by,
        "status":           j.status,
        "progress_pct":     j.progress_pct,
        "status_message":   j.status_message,
        "error_detail":     j.error_detail,
        "metrics":          j.metrics,
        "duration_seconds": j.duration_seconds,
        "started_at":       j.started_at.isoformat() if j.started_at else None,
        "completed_at":     j.completed_at.isoformat() if j.completed_at else None,
        "created_at":       j.created_at.isoformat(),
    }
