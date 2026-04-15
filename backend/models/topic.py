"""
ORM-Models: Topic, ResearchInterval, TopicSource
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON, Boolean, DateTime, Enum, ForeignKey, Index,
    Integer, SmallInteger, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config.database import Base


class Topic(Base):
    """Themen-Verwaltung – zentrale Einheit für Recherchen."""

    __tablename__ = "topics"

    id:              Mapped[int]            = mapped_column(Integer,      primary_key=True, autoincrement=True)
    name:            Mapped[str]            = mapped_column(String(200),  nullable=False)
    slug:            Mapped[str]            = mapped_column(String(200),  nullable=False, unique=True)
    description:     Mapped[Optional[str]]  = mapped_column(Text)
    category:        Mapped[Optional[str]]  = mapped_column(String(100))
    schedule_type:   Mapped[str]            = mapped_column(
        Enum("continuous", "sporadic", "once"), nullable=False, default="sporadic"
    )
    status:          Mapped[str]            = mapped_column(
        Enum("active", "paused", "archived"), nullable=False, default="active"
    )
    llm_provider:    Mapped[Optional[str]]  = mapped_column(
        Enum("ollama", "claude", "openai", "auto")
    )
    llm_model:       Mapped[Optional[str]]  = mapped_column(String(100))
    search_config:   Mapped[Optional[dict]] = mapped_column(JSON)
    system_prompt:   Mapped[Optional[str]]  = mapped_column(Text)
    tags:            Mapped[Optional[list]] = mapped_column(JSON)
    priority:        Mapped[int]            = mapped_column(SmallInteger, nullable=False, default=5)
    created_at:      Mapped[datetime]       = mapped_column(DateTime,     nullable=False, default=func.now())
    updated_at:      Mapped[datetime]       = mapped_column(DateTime,     nullable=False,
                                                            default=func.now(), onupdate=func.now())
    last_researched: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Beziehungen
    intervals:       Mapped[list["ResearchInterval"]] = relationship(
        "ResearchInterval", back_populates="topic", cascade="all, delete-orphan"
    )
    topic_sources:   Mapped[list["TopicSource"]]      = relationship(
        "TopicSource", back_populates="topic", cascade="all, delete-orphan"
    )
    research_results: Mapped[list["ResearchResult"]]  = relationship(
        "ResearchResult", back_populates="topic", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_status",   "status"),
        Index("idx_category", "category"),
        Index("idx_schedule", "schedule_type", "status"),
    )

    def __repr__(self) -> str:
        return f"<Topic id={self.id} slug={self.slug!r} status={self.status}>"

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @property
    def keywords(self) -> list[str]:
        """Suchbegriffe aus search_config."""
        if self.search_config and isinstance(self.search_config, dict):
            return self.search_config.get("keywords", [])
        return []


class ResearchInterval(Base):
    """Intervall-Konfiguration für automatische Recherchen."""

    __tablename__ = "research_intervals"

    id:               Mapped[int]            = mapped_column(Integer,   primary_key=True, autoincrement=True)
    topic_id:         Mapped[int]            = mapped_column(Integer,   ForeignKey("topics.id", ondelete="CASCADE"), nullable=False)
    interval_type:    Mapped[str]            = mapped_column(Enum("fixed", "cron", "smart"), nullable=False, default="fixed")
    interval_seconds: Mapped[Optional[int]]  = mapped_column(Integer)
    cron_expression:  Mapped[Optional[str]]  = mapped_column(String(100))
    next_run:         Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_run:         Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_run_status:  Mapped[Optional[str]]  = mapped_column(Enum("success", "failed", "skipped"))
    is_active:        Mapped[bool]           = mapped_column(Boolean,   nullable=False, default=True)
    timeout_seconds:  Mapped[int]            = mapped_column(Integer,   nullable=False, default=300)
    created_at:       Mapped[datetime]       = mapped_column(DateTime,  nullable=False, default=func.now())
    updated_at:       Mapped[datetime]       = mapped_column(DateTime,  nullable=False,
                                                             default=func.now(), onupdate=func.now())

    # Beziehungen
    topic: Mapped["Topic"] = relationship("Topic", back_populates="intervals")

    __table_args__ = (
        Index("idx_next_run", "next_run", "is_active"),
        Index("idx_topic",    "topic_id"),
    )

    def __repr__(self) -> str:
        return f"<ResearchInterval topic_id={self.topic_id} type={self.interval_type}>"


class TopicSource(Base):
    """Verknüpfungstabelle: bevorzugte Quellen pro Topic."""

    __tablename__ = "topic_sources"

    topic_id:   Mapped[int]      = mapped_column(Integer, ForeignKey("topics.id",  ondelete="CASCADE"), primary_key=True)
    source_id:  Mapped[int]      = mapped_column(Integer, ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True)
    priority:   Mapped[int]      = mapped_column(SmallInteger, nullable=False, default=5)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())

    # Beziehungen
    topic:  Mapped["Topic"]  = relationship("Topic",  back_populates="topic_sources")
    source: Mapped["Source"] = relationship("Source", back_populates="topic_sources")
