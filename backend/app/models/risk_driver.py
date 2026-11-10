"""RiskDriver entity — SHAP-based explainability factors (BRD §11.1.3)."""

from __future__ import annotations

import enum
import uuid
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ImpactDirection(str, enum.Enum):
    """Whether the factor improves or worsens the score."""

    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"


class RiskDriver(Base):
    """A single risk driver (SHAP explanation) linked to a Score.

    Satisfies Kenya DPA 2019 requirement for "meaningful information about
    the logic involved" in automated credit decisions.
    """

    __tablename__ = "risk_drivers"
    __table_args__ = (
        CheckConstraint("rank BETWEEN 1 AND 10", name="ck_risk_drivers_rank_range"),
    )

    driver_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    score_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scores.score_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    rank: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Importance rank (1 = most impactful)",
    )
    factor_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Human-readable factor name",
    )
    impact: Mapped[ImpactDirection] = mapped_column(
        Enum(ImpactDirection, name="impact_direction"),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    shap_value: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 6),
        nullable=True,
        comment="SHAP contribution value",
    )
    feature_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Internal ML feature name (e.g. CBLRI, UTDI)",
    )

    # --- Relationships ---
    score: Mapped[Score] = relationship(
        "Score", back_populates="risk_drivers",
    )

    def __repr__(self) -> str:
        return f"<RiskDriver {self.driver_id} rank={self.rank} factor={self.factor_name!r}>"


from app.models.score import Score  # noqa: E402, F401
