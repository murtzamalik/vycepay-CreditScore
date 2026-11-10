"""Score entity — a computed VyceScore for a subject (BRD §11.1.2)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Score(Base):
    """A credit score record.

    Partitioning note (BRD §11.4):
        In production, this table should be range-partitioned by ``score_date``
        (monthly or quarterly).  The composite index on ``(subject_id, score_date)``
        supports efficient partition pruning for per-subject lookups.
    """

    __tablename__ = "scores"
    __table_args__ = (
        CheckConstraint("vyce_score BETWEEN 300 AND 900", name="ck_scores_vyce_score_range"),
        CheckConstraint("niq_score BETWEEN 0 AND 100", name="ck_scores_niq_score_range"),
        CheckConstraint("confidence_lower IS NULL OR confidence_lower >= 300", name="ck_scores_confidence_lower"),
        CheckConstraint("confidence_upper IS NULL OR confidence_upper <= 900", name="ck_scores_confidence_upper"),
        Index("ix_scores_subject_score_date", "subject_id", "score_date"),
        {"comment": "Partition by score_date in production (range, monthly)"},
    )

    score_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subjects.subject_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    vyce_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="VyceScore in range 300-900",
    )
    niq_score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Network Interdependence & Quality score 0-100",
    )
    score_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    model_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    prediction_horizon: Mapped[int] = mapped_column(
        Integer,
        default=12,
        server_default="12",
        nullable=False,
        comment="Prediction horizon in months",
    )
    confidence_lower: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Lower bound of confidence interval",
    )
    confidence_upper: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Upper bound of confidence interval",
    )
    feature_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Reference to the feature snapshot used for this score",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    # --- Relationships ---
    subject: Mapped[Subject] = relationship(
        "Subject", back_populates="scores",
    )
    risk_drivers: Mapped[list[RiskDriver]] = relationship(
        "RiskDriver", back_populates="score", lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Score {self.score_id} vyce={self.vyce_score} date={self.score_date}>"


from app.models.subject import Subject  # noqa: E402, F401
from app.models.risk_driver import RiskDriver  # noqa: E402, F401
