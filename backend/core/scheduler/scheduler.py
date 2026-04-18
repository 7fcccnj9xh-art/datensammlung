"""
Scheduler: APScheduler-basiertes Job-Scheduling.
Lädt beim Start alle aktiven Topics und plant Jobs ein.
Unterstützt: fixed Intervalle, Cron-Expressions, on-demand Trigger.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from config.database import get_db_session
from config.settings import get_settings
from models.topic import ResearchInterval, Topic
from core.scheduler.job_manager import JobManager

logger = logging.getLogger(__name__)


class KnowledgeScheduler:
    """
    Zentraler Scheduler für alle automatischen Jobs.
    Läuft als Hintergrundservice innerhalb der FastAPI-App.
    """

    def __init__(self) -> None:
        self.settings    = get_settings()
        self.job_manager = JobManager()
        self._scheduler  = AsyncIOScheduler(
            timezone="Europe/Berlin",
            job_defaults={
                "coalesce":       True,   # Verpasste Jobs zusammenfassen
                "max_instances":  1,      # Kein paralleler Start desselben Jobs
                "misfire_grace_time": 300, # Jobs bis 5min nach Fälligkeit noch starten
            }
        )
        self._running = False

    async def start(self) -> None:
        """
        Scheduler starten:
        1. Alle aktiven Topics laden
        2. Jobs einplanen
        3. Feste System-Jobs (Cleanup) hinzufügen
        """
        if self._running:
            return

        self._scheduler.start()
        self._running = True
        logger.info("Scheduler gestartet")

        # Topics laden und Jobs einplanen
        await self._load_topic_jobs()

        # System-Jobs
        self._schedule_cleanup_job()

        logger.info(f"Scheduler aktiv: {len(self._scheduler.get_jobs())} Jobs geplant")

    async def stop(self) -> None:
        """Scheduler sauber stoppen."""
        if self._running:
            self._scheduler.shutdown(wait=False)
            self._running = False
            logger.info("Scheduler gestoppt")

    async def _load_topic_jobs(self) -> None:
        """Alle aktiven Topic-Intervalle aus DB laden und einplanen."""
        async with get_db_session() as db:
            result = await db.execute(
                select(ResearchInterval)
                .join(Topic, ResearchInterval.topic_id == Topic.id)
                .where(
                    ResearchInterval.is_active == True,
                    Topic.status == "active",
                )
            )
            intervals = result.scalars().all()

        for interval in intervals:
            await self.schedule_topic_job(interval.topic_id, interval)

        logger.info(f"{len(intervals)} Topic-Jobs aus DB geladen")

    async def schedule_topic_job(
        self, topic_id: int, interval: ResearchInterval
    ) -> Optional[str]:
        """
        Einen Topic-Job im Scheduler eintragen.
        Gibt APScheduler Job-ID zurück.
        """
        job_id = f"research_topic_{topic_id}"

        # Bestehenden Job entfernen (falls Update)
        existing = self._scheduler.get_job(job_id)
        if existing:
            existing.remove()

        # Trigger bestimmen
        if interval.interval_type == "cron" and interval.cron_expression:
            try:
                trigger = CronTrigger.from_crontab(interval.cron_expression)
            except Exception as e:
                logger.error(f"Ungültige Cron-Expression für Topic {topic_id}: {e}")
                return None

        elif interval.interval_type == "fixed" and interval.interval_seconds:
            trigger = IntervalTrigger(seconds=interval.interval_seconds)

        else:
            logger.warning(f"Kein Trigger für Topic {topic_id} Interval {interval.id}")
            return None

        # Job hinzufügen
        self._scheduler.add_job(
            func=self._run_research_job,
            trigger=trigger,
            id=job_id,
            name=f"Recherche Topic #{topic_id}",
            args=[topic_id],
            replace_existing=True,
        )

        logger.debug(f"Job geplant: {job_id} ({interval.interval_type})")
        return job_id

    async def remove_topic_job(self, topic_id: int) -> None:
        """Topic-Job aus Scheduler entfernen."""
        job_id = f"research_topic_{topic_id}"
        job    = self._scheduler.get_job(job_id)
        if job:
            job.remove()
            logger.debug(f"Job entfernt: {job_id}")

    async def pause_topic_job(self, topic_id: int) -> None:
        """Topic-Job pausieren."""
        job = self._scheduler.get_job(f"research_topic_{topic_id}")
        if job:
            job.pause()

    async def resume_topic_job(self, topic_id: int) -> None:
        """Pausierten Topic-Job fortsetzen."""
        job = self._scheduler.get_job(f"research_topic_{topic_id}")
        if job:
            job.resume()

    async def trigger_now(self, topic_id: int) -> int:
        """
        Topic-Recherche sofort auslösen (on-demand).
        Gibt Job-DB-ID zurück.
        """
        return await self.job_manager.run_research_job(
            topic_id=topic_id,
            triggered_by="user",
        )

    def get_scheduled_jobs(self) -> list[dict]:
        """Liste aller geplanten Jobs für das Dashboard."""
        jobs = []
        for job in self._scheduler.get_jobs():
            next_run = job.next_run_time
            jobs.append({
                "id":       job.id,
                "name":     job.name,
                "next_run": next_run.isoformat() if next_run else None,
                "paused":   next_run is None,
            })
        return jobs

    # ----------------------------------------------------------
    # Job-Ausführungs-Callbacks
    # ----------------------------------------------------------

    async def _run_research_job(self, topic_id: int) -> None:
        """Wrapper für Recherche-Job (von APScheduler aufgerufen)."""
        try:
            await self.job_manager.run_research_job(
                topic_id=topic_id,
                triggered_by="scheduler",
            )
        except Exception as e:
            logger.error(f"Recherche-Job für Topic {topic_id} fehlgeschlagen: {e}", exc_info=True)

    def _schedule_cleanup_job(self) -> None:
        """Täglicher Cleanup: alte Jobs, Logs etc."""
        self._scheduler.add_job(
            func=self._run_cleanup,
            trigger=CronTrigger(hour=3, minute=0),   # 3:00 Uhr nachts
            id="daily_cleanup",
            name="Täglicher Cleanup",
            replace_existing=True,
        )

    async def _run_cleanup(self) -> None:
        """Alte Job-Einträge aus DB löschen (> 30 Tage)."""
        from datetime import timedelta
        from sqlalchemy import delete
        from models.job import Job

        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        async with get_db_session() as db:
            await db.execute(
                delete(Job).where(Job.created_at < cutoff, Job.status.in_(["completed", "failed"]))
            )
        logger.info("Cleanup: Alte Job-Einträge gelöscht")


# Singleton
_scheduler_instance: Optional[KnowledgeScheduler] = None


def get_scheduler() -> KnowledgeScheduler:
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = KnowledgeScheduler()
    return _scheduler_instance
