"""KPI Snapshot entity — operational metrics snapshots (BRD §10.5)."""

from __future__ import annotations

import enum
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Date, DateTime, Enum, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SnapshotPeriod(str, enum.Enum):
    """Granularity of the KPI snapshot."""

    HOURLY = "HOURLY"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class KPISnapshot(Base):
    """Point-in-time snapshot of a Key Performance Indicator.

    Used by the Admin UI dashboard and batch reporting pipeline.
    """

    __tablename__ = "kpi_snapshots"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    kpi_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Machine-readable KPI identifier (e.g. auc_roc, avg_latency_ms)",
    )
    kpi_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Human-readable KPI display name",
    )
    snapshot_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    snapshot_period: Mapped[SnapshotPeriod | None] = mapped_column(
        Enum(SnapshotPeriod, name="snapshot_period"),
        nullable=True,
    )
    value: Mapped[Decimal] = mapped_column(
        Numeric(20, 6),
        nullable=False,
    )
    unit: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Unit of measurement (e.g. ms, %, count)",
    )
    target: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 6),
        nullable=True,
        comment="Target value for this KPI",
    )
    status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="meeting_target | below_target | above_target",
    )
    dimensions: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Dimensional breakdowns (e.g. by tier, by region)",
    )
    metadata_info: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Additional context or notes",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<KPISnapshot {self.id} kpi={self.kpi_id!r} date={self.snapshot_date}>"
