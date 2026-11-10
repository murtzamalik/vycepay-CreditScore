"""Immutable audit log entity with hash chain integrity (BRD §13.3.1, Phase 12.3).

Each log entry contains a SHA-256 hash of the previous entry, forming a
tamper-evident chain.  Any modification to a historical entry will cause
the chain verification to fail.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLogCategory(str, enum.Enum):
    """Categories of audit log entries for retention policy grouping."""

    API_REQUEST = "API_REQUEST"
    AUTHENTICATION = "AUTHENTICATION"
    SCORE_CALCULATION = "SCORE_CALCULATION"
    ADMIN_ACTION = "ADMIN_ACTION"
    SYSTEM_EVENT = "SYSTEM_EVENT"
    DATA_ACCESS = "DATA_ACCESS"
    DATA_MODIFICATION = "DATA_MODIFICATION"


class AuditLog(Base):
    """Immutable audit log entry with hash chain integrity.

    The ``entry_hash`` column contains a SHA-256 hash computed over:
    - ``previous_hash`` (hash of the preceding entry)
    - ``sequence_number``
    - ``category``
    - ``action``
    - ``actor_id``
    - ``timestamp``
    - ``details`` (JSON-serialized)

    This forms a blockchain-like chain where tampering with any entry
    invalidates all subsequent hashes.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_category_timestamp", "category", "timestamp"),
        Index("ix_audit_logs_actor_timestamp", "actor_id", "timestamp"),
        Index("ix_audit_logs_sequence", "sequence_number", unique=True),
        {"comment": "Immutable audit log with hash chain. No UPDATE/DELETE."},
    )

    log_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    sequence_number: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        unique=True,
        comment="Monotonically increasing sequence for hash chain ordering",
    )
    category: Mapped[AuditLogCategory] = mapped_column(
        Enum(AuditLogCategory, name="audit_log_category"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Description of the action, e.g. 'user.login', 'score.calculated'",
    )
    actor_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="User ID or system identifier that performed the action",
    )
    actor_type: Mapped[str] = mapped_column(
        String(50),
        default="SYSTEM",
        server_default="SYSTEM",
        nullable=False,
        comment="USER | API_KEY | SYSTEM | SCHEDULER",
    )
    resource_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Type of resource affected (e.g. 'Subject', 'Score', 'User')",
    )
    resource_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Identifier of the affected resource",
    )
    details: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional structured data about the event",
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="SHA-256 hash of the client IP address",
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    entry_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 hash of this entry (includes previous_hash for chain)",
    )
    previous_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 hash of the previous entry (genesis = '0' * 64)",
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
        comment="Chain integrity verified at write time",
    )
    retention_years: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Number of years this entry must be retained",
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog {self.log_id} seq={self.sequence_number} "
            f"action={self.action!r} category={self.category.value}>"
        )
