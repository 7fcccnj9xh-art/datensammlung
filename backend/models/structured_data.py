"""ORM-Model: StructuredData (generischer Daten-Container)"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON, BigInteger, DateTime, ForeignKey, Index, Integer, String, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config.database import Base


class StructuredData(Base):
    """Generischer Container für strukturierte Daten (Energie, Preise, Sensordaten, etc.)."""

    __tablename__ = "structured_data"

    id:             Mapped[int]             = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    data_type:      Mapped[str]             = mapped_column(String(100), nullable=False)
    source_id:      Mapped[Optional[int]]   = mapped_column(Integer,     ForeignKey("sources.id", ondelete="SET NULL"))
    data:           Mapped[dict]            = mapped_column(JSON,        nullable=False)
    data_timestamp: Mapped[datetime]        = mapped_column(DateTime,    nullable=False)
    location:       Mapped[Optional[dict]]  = mapped_column(JSON)
    created_at:     Mapped[datetime]        = mapped_column(DateTime,    nullable=False, default=func.now())

    # Beziehung
    source: Mapped[Optional["Source"]] = relationship("Source")

    __table_args__ = (
        Index("idx_type_time", "data_type", "data_timestamp"),
        Index("idx_data_time", "data_timestamp"),
    )

    def __repr__(self) -> str:
        return f"<StructuredData type={self.data_type!r} at={self.data_timestamp}>"
