"""ORM-Model: Source (Quellen-Verwaltung)"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    JSON, Boolean, DateTime, Enum, Index, Integer,
    Numeric, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config.database import Base


class Source(Base):
    """Quellen-Tabelle: alle Datenquellen (Websites, RSS, APIs)."""

    __tablename__ = "sources"

    id:                 Mapped[int]             = mapped_column(Integer,  primary_key=True, autoincrement=True)
    url:                Mapped[str]             = mapped_column(String(2000), nullable=False)
    domain:             Mapped[str]             = mapped_column(String(255),  nullable=False)
    title:              Mapped[Optional[str]]   = mapped_column(String(500))
    description:        Mapped[Optional[str]]   = mapped_column(Text)
    source_type:        Mapped[str]             = mapped_column(
        Enum("website", "api", "rss", "pdf", "youtube", "github", "custom"),
        nullable=False, default="website"
    )
    trust_score:        Mapped[Decimal]         = mapped_column(Numeric(3, 2), nullable=False, default=Decimal("0.50"))
    auth_config:        Mapped[Optional[dict]]  = mapped_column(JSON)
    custom_headers:     Mapped[Optional[dict]]  = mapped_column(JSON)
    extraction_config:  Mapped[Optional[dict]]  = mapped_column(JSON)
    is_active:          Mapped[bool]            = mapped_column(Boolean,  nullable=False, default=True)
    first_seen:         Mapped[datetime]        = mapped_column(DateTime, nullable=False, default=func.now())
    last_fetched:       Mapped[Optional[datetime]] = mapped_column(DateTime)
    fetch_count:        Mapped[int]             = mapped_column(Integer,  nullable=False, default=0)
    error_count:        Mapped[int]             = mapped_column(Integer,  nullable=False, default=0)
    created_at:         Mapped[datetime]        = mapped_column(DateTime, nullable=False, default=func.now())
    updated_at:         Mapped[datetime]        = mapped_column(DateTime, nullable=False,
                                                                default=func.now(), onupdate=func.now())

    # Beziehungen
    topic_sources:   Mapped[list["TopicSource"]]    = relationship("TopicSource",   back_populates="source")
    research_results: Mapped[list["ResearchResult"]] = relationship("ResearchResult", back_populates="source")

    __table_args__ = (
        Index("idx_domain",     "domain"),
        Index("idx_type",       "source_type"),
        Index("idx_trust",      "trust_score"),
        Index("idx_last_fetch", "last_fetched"),
    )

    def __repr__(self) -> str:
        return f"<Source id={self.id} domain={self.domain!r} type={self.source_type}>"

    @property
    def error_rate(self) -> float:
        """Fehlerrate als Anteil (0.0–1.0)."""
        total = self.fetch_count + self.error_count
        return self.error_count / total if total > 0 else 0.0

    @property
    def is_rss(self) -> bool:
        return self.source_type == "rss"

    @property
    def is_api(self) -> bool:
        return self.source_type == "api"
