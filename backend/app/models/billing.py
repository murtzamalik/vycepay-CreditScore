"""Billing and embed configuration ORM models (BRD §7.3.2, §7.2.7)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class BillingStatus(str, enum.Enum):
    """Status of a billing record."""

    DRAFT = "DRAFT"
    FINALIZED = "FINALIZED"
    PAID = "PAID"
    OVERDUE = "OVERDUE"


class BillingRecord(TimestampMixin, Base):
    """Monthly billing record per customer (BRD §7.3.2).

    Tracks monthly usage charges by tier, including base fees and overage costs.
    """

    __tablename__ = "billing_records"
    __table_args__ = (
        Index(
            "ix_billing_records_customer_period",
            "customer_id",
            "billing_period",
            unique=True,
        ),
    )

    billing_id: Mapped[uuid.UUID] = mapped_column(
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
    billing_period: Mapped[str] = mapped_column(
        String(7),
        nullable=False,
        comment="YYYY-MM format",
    )
    status: Mapped[BillingStatus] = mapped_column(
        Enum(BillingStatus, name="billing_status"),
        default=BillingStatus.DRAFT,
        server_default="DRAFT",
        nullable=False,
    )

    # Query counts
    lite_queries: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False,
    )
    pro_queries: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False,
    )
    batch_queries: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False,
    )
    total_queries: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False,
    )

    # Pricing breakdown
    base_fee: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False,
    )
    lite_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False,
    )
    pro_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False,
    )
    overage_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False,
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3), default="KES", server_default="KES", nullable=False,
    )

    # Included queries in base plan
    included_queries: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False,
    )
    overage_queries: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False,
    )

    # --- Relationships ---
    customer: Mapped[Customer] = relationship("Customer", back_populates="billing_records")

    def __repr__(self) -> str:
        return (
            f"<BillingRecord {self.billing_id} "
            f"customer={self.customer_id} period={self.billing_period} "
            f"total={self.total_amount}>"
        )


class EmbedConfig(TimestampMixin, Base):
    """White-label embed configuration for a customer (BRD §7.2.7)."""

    __tablename__ = "embed_configs"

    embed_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.customer_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    customer_token: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
        comment="Public token for retrieving embed config",
    )
    allowed_origins: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="List of allowed embedding origins (domains)",
    )
    theme_config: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="White-label theme settings (colors, logo, etc.)",
    )
    widget_config: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Widget behavior configuration",
    )
    is_active: Mapped[bool] = mapped_column(
        default=True, server_default="true", nullable=False,
    )

    # --- Relationships ---
    customer: Mapped[Customer] = relationship("Customer", back_populates="embed_config")

    def __repr__(self) -> str:
        return f"<EmbedConfig {self.embed_config_id} customer={self.customer_id}>"


# Avoid circular imports
from app.models.customer import Customer  # noqa: E402, F401
