"""ComplianceCheck entity — KYC/AML check audit trail (BRD §5.3, Phase 15)."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ComplianceCheckType(str, enum.Enum):
    """Type of compliance check."""

    KYC = "KYC"
    AML = "AML"


class ComplianceCheckStatus(str, enum.Enum):
    """Status of a compliance check."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    PENDING = "PENDING"
    REVIEW = "REVIEW"


class ComplianceCheck(TimestampMixin, Base):
    """Records each KYC or AML check performed on a subject.

    The ``raw_response`` column stores the provider response as encrypted
    JSON text (encrypted at rest via application-level encryption).
    This supports audit trail and re-verification requirements.
    """

    __tablename__ = "compliance_checks"

    check_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=None,
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subjects.subject_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    check_type: Mapped[ComplianceCheckType] = mapped_column(
        Enum(ComplianceCheckType, name="compliance_check_type"),
        nullable=False,
    )
    status: Mapped[ComplianceCheckStatus] = mapped_column(
        Enum(ComplianceCheckStatus, name="compliance_check_status"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Provider name: smile_id or comply_advantage",
    )
    provider_reference: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Provider-specific reference/job ID for audit trail",
    )
    confidence_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Confidence score from provider (0.0 to 1.0)",
    )
    risk_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Risk score from provider (0.0 to 1.0)",
    )
    raw_response: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Encrypted JSON of full provider response",
    )
    checked_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when the check was completed by the provider",
    )
    expires_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When this check result expires and needs refresh",
    )

    # --- Relationships ---
    subject: Mapped[Subject] = relationship(
        "Subject",
        back_populates="compliance_checks",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<ComplianceCheck {self.check_id} "
            f"type={self.check_type.value} "
            f"status={self.status.value}>"
        )


# Late import to avoid circular imports
from app.models.subject import Subject  # noqa: E402, F401
