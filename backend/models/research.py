"""ORM-Model: ResearchResult"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    JSON, BigInteger, DateTime, Enum, ForeignKey, Index,
    Integer, Numeric, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config.database import Base


class ResearchResult(Base):
    """Recherche-Ergebnisse mit Versionierung und LLM-Zusammenfassungen."""

    __tablename__ = "research_results"

    id:              Mapped[int]             = mapped_column(BigInteger,  primary_key=True, autoincrement=True)
    topic_id:        Mapped[int]             = mapped_column(Integer,     ForeignKey("topics.id",  ondelete="CASCADE"), nullable=False)
    source_id:       Mapped[Optional[int]]   = mapped_column(Integer,     ForeignKey("sources.id", ondelete="SET NULL"))
    job_id:          Mapped[Optional[int]]   = mapped_column(BigInteger)
    raw_content:     Mapped[Optional[str]]   = mapped_column(Text(16777215))   # MEDIUMTEXT
    clean_content:   Mapped[Optional[str]]   = mapped_column(Text(16777215))
    summary:         Mapped[Optional[str]]   = mapped_column(Text)
    delta_summary:   Mapped[Optional[str]]   = mapped_column(Text)
    meta_data:       Mapped[Optional[dict]]  = mapped_column(JSON)
    embedding:       Mapped[Optional[list]]  = mapped_column(JSON)
    version:         Mapped[int]             = mapped_column(Integer,     nullable=False, default=1)
    content_hash:    Mapped[Optional[str]]   = mapped_column(String(64))
    language:        Mapped[Optional[str]]   = mapped_column(String(5),   default="de")
    relevance_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2))
    created_at:      Mapped[datetime]        = mapped_column(DateTime,    nullable=False, default=func.now())
    updated_at:      Mapped[datetime]        = mapped_column(DateTime,    nullable=False,
                                                             default=func.now(), onupdate=func.now())

    # Beziehungen
    topic:  Mapped["Topic"]  = relationship("Topic",  back_populates="research_results")
    source: Mapped[Optional["Source"]] = relationship("Source", back_populates="research_results")

    __table_args__ = (
        Index("idx_topic",     "topic_id", "created_at"),
        Index("idx_hash",      "content_hash"),
        Index("idx_relevance", "relevance_score"),
        Index("idx_created",   "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ResearchResult id={self.id} topic_id={self.topic_id} v{self.version}>"

    @property
    def title(self) -> str:
        """Titel aus Metadaten oder Platzhalter."""
        if self.meta_data and isinstance(self.meta_data, dict):
            return self.meta_data.get("title", f"Ergebnis #{self.id}")
        return f"Ergebnis #{self.id}"

    @property
    def source_url(self) -> Optional[str]:
        """URL aus Metadaten."""
        if self.meta_data and isinstance(self.meta_data, dict):
            return self.meta_data.get("url")
        return None
