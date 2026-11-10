"""Feature entity — computed ML features for a subject (BRD §11.1.4)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Feature(Base):
    """A single feature value for a subject on a given date.

    Represents one row in the feature store.  Features are computed by the
    Feature Engineering Service from VycePay, VyceTrade, and compliance
    data sources.

    Partitioning note (BRD §11.4):
        In production, this table should be range-partitioned by
        ``feature_date`` (monthly).  The composite index on
        ``(subject_id, feature_date)`` supports partition pruning.
    """

    __tablename__ = "features"
    __table_args__ = (
        CheckConstraint(
            "quality_score IS NULL OR (quality_score >= 0 AND quality_score <= 1)",
            name="ck_features_quality_score_range",
        ),
        Index("ix_features_subject_feature_date", "subject_id", "feature_date"),
        {"comment": "Partition by feature_date in production (range, monthly)"},
    )

    feature_id: Mapped[uuid.UUID] = mapped_column(
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
    feature_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    feature_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Feature identifier (e.g. CBLRI, UTDI, SCFV, DDC_RATIO, NIQ, GOS)",
    )
    feature_value: Mapped[Decimal] = mapped_column(
        Numeric(20, 6),
        nullable=False,
    )
    feature_category: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="TRANSACTION | NETWORK | SUPPLY_CHAIN | COMPLIANCE",
    )
    data_source: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="VYCEPAY | VYCETRADE | COMPLIANCE",
    )
    quality_score: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 2),
        nullable=True,
        comment="Data quality indicator 0.00-1.00",
    )

    # --- Relationships ---
    subject: Mapped[Subject] = relationship(
        "Subject", back_populates="features",
    )

    def __repr__(self) -> str:
        return f"<Feature {self.feature_id} name={self.feature_name!r} value={self.feature_value}>"


from app.models.subject import Subject  # noqa: E402, F401
