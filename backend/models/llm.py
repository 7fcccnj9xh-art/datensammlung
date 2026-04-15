"""ORM-Models: LLMConfig, LLMUsage"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    JSON, BigInteger, Boolean, Date, DateTime, Enum,
    ForeignKey, Index, Integer, Numeric, String, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config.database import Base


class LLMConfig(Base):
    """LLM-Provider-Konfigurationen und Budget-Tracking."""

    __tablename__ = "llm_configs"

    id:                 Mapped[int]             = mapped_column(Integer,  primary_key=True, autoincrement=True)
    name:               Mapped[str]             = mapped_column(String(100), nullable=False, unique=True)
    provider:           Mapped[str]             = mapped_column(
        Enum("ollama", "claude", "openai", "custom"), nullable=False
    )
    model_name:         Mapped[str]             = mapped_column(String(100), nullable=False)
    api_endpoint:       Mapped[Optional[str]]   = mapped_column(String(500))
    max_tokens:         Mapped[int]             = mapped_column(Integer, nullable=False, default=2000)
    temperature:        Mapped[Decimal]         = mapped_column(Numeric(3, 2), nullable=False, default=Decimal("0.30"))
    monthly_budget_eur: Mapped[Decimal]         = mapped_column(Numeric(8, 2), nullable=False, default=Decimal("0.00"))
    monthly_spent_eur:  Mapped[Decimal]         = mapped_column(Numeric(8, 2), nullable=False, default=Decimal("0.00"))
    budget_reset_date:  Mapped[Optional[datetime]] = mapped_column(Date)
    is_default:         Mapped[bool]            = mapped_column(Boolean,  nullable=False, default=False)
    is_active:          Mapped[bool]            = mapped_column(Boolean,  nullable=False, default=True)
    extra_config:       Mapped[Optional[dict]]  = mapped_column(JSON)
    created_at:         Mapped[datetime]        = mapped_column(DateTime, nullable=False, default=func.now())
    updated_at:         Mapped[datetime]        = mapped_column(DateTime, nullable=False,
                                                                default=func.now(), onupdate=func.now())

    # Beziehungen
    usage_records: Mapped[list["LLMUsage"]] = relationship(
        "LLMUsage", back_populates="llm_config", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_provider", "provider", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<LLMConfig name={self.name!r} provider={self.provider}>"

    @property
    def budget_exceeded(self) -> bool:
        """Monatliches Budget überschritten?"""
        if self.monthly_budget_eur and self.monthly_budget_eur > 0:
            return self.monthly_spent_eur >= self.monthly_budget_eur
        return False

    @property
    def budget_remaining_eur(self) -> Optional[Decimal]:
        """Verbleibendes Budget in EUR (None wenn kein Limit)."""
        if self.monthly_budget_eur and self.monthly_budget_eur > 0:
            return max(Decimal("0"), self.monthly_budget_eur - self.monthly_spent_eur)
        return None


class LLMUsage(Base):
    """Protokoll aller LLM-Aufrufe für Kosten-Tracking."""

    __tablename__ = "llm_usage"

    id:             Mapped[int]             = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    llm_config_id:  Mapped[int]             = mapped_column(Integer,    ForeignKey("llm_configs.id", ondelete="CASCADE"), nullable=False)
    job_id:         Mapped[Optional[int]]   = mapped_column(BigInteger)
    topic_id:       Mapped[Optional[int]]   = mapped_column(Integer)
    input_tokens:   Mapped[int]             = mapped_column(Integer,    nullable=False, default=0)
    output_tokens:  Mapped[int]             = mapped_column(Integer,    nullable=False, default=0)
    cost_eur:       Mapped[Decimal]         = mapped_column(Numeric(10, 6), nullable=False, default=Decimal("0"))
    prompt_type:    Mapped[Optional[str]]   = mapped_column(String(100))
    duration_ms:    Mapped[Optional[int]]   = mapped_column(Integer)
    from_cache:     Mapped[bool]            = mapped_column(Boolean,    nullable=False, default=False)
    created_at:     Mapped[datetime]        = mapped_column(DateTime,   nullable=False, default=func.now())

    # Beziehungen
    llm_config: Mapped["LLMConfig"] = relationship("LLMConfig", back_populates="usage_records")

    __table_args__ = (
        Index("idx_config_time", "llm_config_id", "created_at"),
        Index("idx_job",         "job_id"),
        Index("idx_topic",       "topic_id"),
    )
