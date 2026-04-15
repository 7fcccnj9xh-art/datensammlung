"""ORM-Model: Job (Ausführungsprotokoll)"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON, BigInteger, DateTime, Enum, Index, Integer,
    SmallInteger, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base


class Job(Base):
    """Job-Ausführungsprotokoll für alle Scraping/Recherche-Jobs."""

    __tablename__ = "jobs"

    id:               Mapped[int]             = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_key:          Mapped[str]             = mapped_column(String(200), nullable=False)
    job_type:         Mapped[str]             = mapped_column(
        Enum("research", "weather_fetch", "api_sync", "on_demand", "backup", "export"),
        nullable=False
    )
    topic_id:         Mapped[Optional[int]]   = mapped_column(Integer)
    triggered_by:     Mapped[str]             = mapped_column(
        Enum("scheduler", "api", "user", "cron"), nullable=False, default="scheduler"
    )
    status:           Mapped[str]             = mapped_column(
        Enum("queued", "running", "completed", "failed", "cancelled", "timeout"),
        nullable=False, default="queued"
    )
    progress_pct:     Mapped[int]             = mapped_column(SmallInteger, nullable=False, default=0)
    status_message:   Mapped[Optional[str]]   = mapped_column(String(500))
    error_detail:     Mapped[Optional[str]]   = mapped_column(Text)
    metrics:          Mapped[Optional[dict]]  = mapped_column(JSON)
    parameters:       Mapped[Optional[dict]]  = mapped_column(JSON)
    started_at:       Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at:     Mapped[Optional[datetime]] = mapped_column(DateTime)
    duration_seconds: Mapped[Optional[int]]   = mapped_column(Integer)
    created_at:       Mapped[datetime]        = mapped_column(DateTime, nullable=False, default=func.now())

    __table_args__ = (
        Index("idx_type_status", "job_type", "status"),
        Index("idx_topic",       "topic_id"),
        Index("idx_created",     "created_at"),
        Index("idx_status",      "status", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Job id={self.id} type={self.job_type} status={self.status}>"

    @property
    def is_running(self) -> bool:
        return self.status in ("queued", "running")

    @property
    def is_done(self) -> bool:
        return self.status in ("completed", "failed", "cancelled", "timeout")
