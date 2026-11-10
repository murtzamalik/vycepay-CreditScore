"""Subject entity — the individual or business being scored (BRD §11.1.1)."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Enum, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class SubjectType(str, enum.Enum):
    """Type of credit subject."""

    INDIVIDUAL = "INDIVIDUAL"
    BUSINESS = "BUSINESS"


class KYCStatus(str, enum.Enum):
    """Know Your Customer verification status."""

    VERIFIED = "VERIFIED"
    PENDING = "PENDING"
    FAILED = "FAILED"


class AMLStatus(str, enum.Enum):
    """Anti-Money Laundering screening status."""

    CLEAR = "CLEAR"
    REVIEW = "REVIEW"
    FLAGGED = "FLAGGED"


class Subject(TimestampMixin, Base):
    """A scoreable entity — an individual or MSME.

    The ``id_hash`` column stores a SHA-256 hash of the national ID so that
    PII is never stored in plain text (Kenya DPA 2019 compliance).
    """

    __tablename__ = "subjects"

    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=None,
    )
    subject_type: Mapped[SubjectType] = mapped_column(
        Enum(SubjectType, name="subject_type"),
        nullable=False,
    )
    id_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
        comment="SHA-256 hash of National ID — PII never stored in plain text",
    )
    kyc_status: Mapped[KYCStatus] = mapped_column(
        Enum(KYCStatus, name="kyc_status"),
        default=KYCStatus.PENDING,
        server_default="PENDING",
        nullable=False,
    )
    aml_status: Mapped[AMLStatus] = mapped_column(
        Enum(AMLStatus, name="aml_status"),
        default=AMLStatus.CLEAR,
        server_default="CLEAR",
        nullable=False,
    )

    # --- Relationships ---
    scores: Mapped[list[Score]] = relationship(
        "Score", back_populates="subject", lazy="selectin",
    )
    features: Mapped[list[Feature]] = relationship(
        "Feature", back_populates="subject", lazy="selectin",
    )
    api_request_logs: Mapped[list[ApiRequestLog]] = relationship(
        "ApiRequestLog", back_populates="subject", lazy="selectin",
    )
    compliance_checks: Mapped[list[ComplianceCheck]] = relationship(
        "ComplianceCheck", back_populates="subject", lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Subject {self.subject_id} type={self.subject_type.value}>"


# Late imports for type-checking only (avoid circular imports at runtime)
from app.models.score import Score  # noqa: E402, F401
from app.models.feature import Feature  # noqa: E402, F401
from app.models.api_request_log import ApiRequestLog  # noqa: E402, F401
from app.models.compliance_check import ComplianceCheck  # noqa: E402, F401
