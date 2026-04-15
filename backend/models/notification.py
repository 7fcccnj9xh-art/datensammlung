"""ORM-Models: Notification, Annotation"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON, BigInteger, Boolean, DateTime, Enum, Index, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id:          Mapped[int]            = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    level:       Mapped[str]            = mapped_column(Enum("info", "warning", "alert", "error"), nullable=False, default="info")
    title:       Mapped[str]            = mapped_column(String(300), nullable=False)
    message:     Mapped[Optional[str]]  = mapped_column(Text)
    source_type: Mapped[Optional[str]]  = mapped_column(String(50))
    source_id:   Mapped[Optional[str]]  = mapped_column(String(50))
    is_read:     Mapped[bool]           = mapped_column(Boolean, nullable=False, default=False)
    sent_via:    Mapped[Optional[dict]] = mapped_column(JSON)
    created_at:  Mapped[datetime]       = mapped_column(DateTime, nullable=False, default=func.now())

    __table_args__ = (
        Index("idx_read_level", "is_read", "level", "created_at"),
        Index("idx_created",    "created_at"),
    )
