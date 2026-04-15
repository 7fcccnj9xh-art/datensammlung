"""
Job-Manager: Erstellt, verwaltet und protokolliert Job-Ausführungen.
Verbindet Scheduler mit den eigentlichen Task-Implementierungen.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from config.database import get_db_session
from models.job import Job
from models.topic import Topic

logger = logging.getLogger(__name__)


class JobManager:
    """
    Verantwortlich für:
    - Job-Erstellung in der DB (Protokollierung)
    - Ausführung der eigentlichen Tasks
    - Status-Updates (queued → running → completed/failed)
    """

    async def run_research_job(
        self,
        topic_id: int,
        triggered_by: str = "scheduler",
        parameters: Optional[dict] = None,
    ) -> int:
        """
        Recherche-Job für ein Topic ausführen.
        Gibt die DB-Job-ID zurück.
        """
        # Job in DB anlegen
        job_db_id = await self._create_job(
            job_type     = "research",
            topic_id     = topic_id,
            triggered_by = triggered_by,
            parameters   = parameters or {},
        )

        try:
            await self._update_job(job_db_id, status="running", started_at=datetime.now(timezone.utc))

            from core.scheduler.tasks.research_task import ResearchTask
            task    = ResearchTask()
            metrics = await task.run(topic_id=topic_id, job_id=job_db_id)

            await self._update_job(
                job_db_id,
                status          = "completed",
                progress_pct    = 100,
                status_message  = f"Abgeschlossen: {metrics.get('results_saved', 0)} Ergebnisse gespeichert",
                metrics         = metrics,
                completed_at    = datetime.now(timezone.utc),
            )

            # Topic: last_researched aktualisieren
            async with get_db_session() as db:
                result = await db.execute(select(Topic).where(Topic.id == topic_id))
                topic  = result.scalar_one_or_none()
                if topic:
                    topic.last_researched = datetime.now(timezone.utc)

        except Exception as e:
            logger.error(f"Research-Job {job_db_id} fehlgeschlagen: {e}", exc_info=True)
            await self._update_job(
                job_db_id,
                status       = "failed",
                error_detail = str(e),
                completed_at = datetime.now(timezone.utc),
            )

        return job_db_id

    async def run_weather_job(self) -> int:
        """Wetterdaten-Job ausführen."""
        job_db_id = await self._create_job(
            job_type="weather_fetch", triggered_by="scheduler"
        )
        try:
            await self._update_job(job_db_id, status="running", started_at=datetime.now(timezone.utc))

            from core.scheduler.tasks.weather_task import WeatherTask
            task    = WeatherTask()
            metrics = await task.run(job_id=job_db_id)

            await self._update_job(
                job_db_id,
                status         = "completed",
                progress_pct   = 100,
                status_message = f"Wetter: {metrics.get('records_saved', 0)} Datensätze gespeichert",
                metrics        = metrics,
                completed_at   = datetime.now(timezone.utc),
            )

        except Exception as e:
            logger.error(f"Wetter-Job {job_db_id} fehlgeschlagen: {e}", exc_info=True)
            await self._update_job(
                job_db_id,
                status="failed", error_detail=str(e),
                completed_at=datetime.now(timezone.utc),
            )

        return job_db_id

    async def get_job_status(self, job_id: int) -> Optional[dict]:
        """Job-Status aus DB abrufen."""
        async with get_db_session() as db:
            result = await db.execute(select(Job).where(Job.id == job_id))
            job    = result.scalar_one_or_none()
            if not job:
                return None
            return {
                "id":             job.id,
                "job_type":       job.job_type,
                "status":         job.status,
                "progress_pct":   job.progress_pct,
                "status_message": job.status_message,
                "error_detail":   job.error_detail,
                "metrics":        job.metrics,
                "started_at":     job.started_at.isoformat() if job.started_at else None,
                "completed_at":   job.completed_at.isoformat() if job.completed_at else None,
            }

    async def cancel_job(self, job_id: int) -> bool:
        """Job als abgebrochen markieren."""
        async with get_db_session() as db:
            result = await db.execute(select(Job).where(Job.id == job_id))
            job    = result.scalar_one_or_none()
            if job and job.status in ("queued", "running"):
                job.status       = "cancelled"
                job.completed_at = datetime.now(timezone.utc)
                return True
        return False

    # ----------------------------------------------------------
    # Private DB-Hilfsmethoden
    # ----------------------------------------------------------

    async def _create_job(
        self,
        job_type: str,
        topic_id: Optional[int] = None,
        triggered_by: str = "scheduler",
        parameters: Optional[dict] = None,
    ) -> int:
        """Job in DB anlegen und ID zurückgeben."""
        job_key = f"{job_type}_{uuid.uuid4().hex[:8]}"
        async with get_db_session() as db:
            job = Job(
                job_key      = job_key,
                job_type     = job_type,
                topic_id     = topic_id,
                triggered_by = triggered_by,
                status       = "queued",
                parameters   = parameters or {},
            )
            db.add(job)
            await db.flush()
            job_id = job.id
        return job_id

    async def _update_job(self, job_id: int, **kwargs) -> None:
        """Job-Felder aktualisieren."""
        async with get_db_session() as db:
            result = await db.execute(select(Job).where(Job.id == job_id))
            job    = result.scalar_one_or_none()
            if job:
                for key, value in kwargs.items():
                    setattr(job, key, value)
                # Laufzeit berechnen
                if job.started_at and kwargs.get("completed_at"):
                    delta = kwargs["completed_at"] - job.started_at
                    job.duration_seconds = int(delta.total_seconds())
