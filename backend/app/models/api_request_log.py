"""ApiRequestLog entity — immutable audit trail (BRD §11.1.6)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ApiRequestLog(Base):
    """Immutable audit-trail entry for every API request.

    Supports Kenya DPA 2019 and CBK compliance requirements.
    All entries are append-only; no UPDATE or DELETE should be issued
    against this table.

    Partitioning note (BRD §11.4):
        In production, this table should be range-partitioned by
        ``request_time`` (daily or weekly).  The composite index on
        ``(customer_id, request_time)`` supports partition pruning.
    """

    __tablename__ = "api_request_logs"
    __table_args__ = (
        Index("ix_api_request_logs_customer_request_time", "customer_id", "request_time"),
        {"comment": "Partition by request_time in production (range, daily/weekly)"},
    )

    log_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.customer_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    request_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    endpoint: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subjects.subject_id", ondelete="SET NULL"),
        nullable=True,
    )
    response_status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    response_time_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Response time in milliseconds",
    )
    query_cost: Mapped[int] = mapped_column(
        Integer,
        default=1,
        server_default="1",
        nullable=False,
        comment="Number of query credits consumed",
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment="Hashed IP address — never store raw IPs",
    )

    # --- Relationships ---
    customer: Mapped[Customer] = relationship(
        "Customer", back_populates="api_request_logs",
    )
    subject: Mapped[Subject | None] = relationship(
        "Subject", back_populates="api_request_logs",
    )

    def __repr__(self) -> str:
        return f"<ApiRequestLog {self.log_id} endpoint={self.endpoint!r} status={self.response_status}>"


from app.models.customer import Customer  # noqa: E402, F401
from app.models.subject import Subject  # noqa: E402, F401
