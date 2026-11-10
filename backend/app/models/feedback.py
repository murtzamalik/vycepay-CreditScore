"""LoanFeedback ORM model for partner bank loan outcomes (Phase 6 enhanced)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class LoanFeedback(TimestampMixin, Base):
    __tablename__ = "loan_feedback"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    loan_id: Mapped[str | None] = mapped_column(
        String(100), unique=True, nullable=True, index=True,
        comment="Unique loan reference from partner bank",
    )
    national_id_hash: Mapped[str] = mapped_column(
        String(64), index=True, nullable=False, comment="SHA-256 hash of the national ID"
    )
    loan_outcome: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="e.g. performing, default, delinquent, restructured"
    )
    dpd: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Days past due"
    )
    is_default: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, comment="Whether loan is classified as defaulted"
    )
    loan_amount: Mapped[float | None] = mapped_column(
        Numeric(15, 2), nullable=True, comment="Loan amount in KES"
    )
    disbursement_date: Mapped[date | None] = mapped_column(
        Date, nullable=True, comment="Date the loan was disbursed"
    )
    outcome_date: Mapped[date | None] = mapped_column(
        Date, nullable=True, comment="Date of the outcome observation"
    )
    partner_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="Reporting partner bank identifier"
    )
    reported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
