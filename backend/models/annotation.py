"""ORM-Model: Annotation (Notizen zu Topics/Ergebnissen/Quellen)"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base


class Annotation(Base):
    __tablename__ = "annotations"

    id:          Mapped[int]      = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity_type: Mapped[str]      = mapped_column(Enum("topic", "result", "source"), nullable=False)
    entity_id:   Mapped[int]      = mapped_column(BigInteger, nullable=False)
    note:        Mapped[str]      = mapped_column(Text, nullable=False)
    created_at:  Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    updated_at:  Mapped[datetime] = mapped_column(DateTime, nullable=False,
                                                  default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_entity", "entity_type", "entity_id"),
    )
