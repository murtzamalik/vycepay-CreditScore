"""Customer (API consumer / partner institution) entity (BRD §11.1.5)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class LicenseTier(str, enum.Enum):
    """Product tier the customer is licensed for."""

    LITE = "LITE"
    PRO = "PRO"
    DEEP_DIVE = "DEEP_DIVE"


class CustomerStatus(str, enum.Enum):
    """Lifecycle status of a customer account."""

    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    TERMINATED = "TERMINATED"


class Customer(Base):
    """A financial institution or partner consuming the VyceScore API."""

    __tablename__ = "customers"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    contact_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Primary contact email for the customer organisation",
    )
    license_tier: Mapped[LicenseTier] = mapped_column(
        Enum(LicenseTier, name="license_tier"),
        nullable=False,
    )
    status: Mapped[CustomerStatus] = mapped_column(
        Enum(CustomerStatus, name="customer_status"),
        default=CustomerStatus.PENDING,
        server_default="PENDING",
        nullable=False,
    )
    api_key_hash: Mapped[str | None] = mapped_column(
        String(64),
        unique=True,
        nullable=True,
        comment="SHA-256 hash of the customer API key",
    )
    monthly_query_limit: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    sandbox_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )
    production_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )

    # --- Relationships ---
    api_request_logs: Mapped[list[ApiRequestLog]] = relationship(
        "ApiRequestLog", back_populates="customer", lazy="selectin",
    )
    billing_records: Mapped[list[BillingRecord]] = relationship(
        "BillingRecord", back_populates="customer", lazy="selectin",
    )
    embed_config: Mapped[EmbedConfig | None] = relationship(
        "EmbedConfig", back_populates="customer", uselist=False, lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Customer {self.customer_id} name={self.name!r} tier={self.license_tier.value}>"


from app.models.api_request_log import ApiRequestLog  # noqa: E402, F401
from app.models.billing import BillingRecord, EmbedConfig  # noqa: E402, F401
