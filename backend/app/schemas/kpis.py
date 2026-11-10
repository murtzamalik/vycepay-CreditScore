"""KPI response schemas (BRD SS10.5)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.models.kpi_snapshot import SnapshotPeriod


# ---------------------------------------------------------------------------
# Task 9.10 -- KPI Schemas
# ---------------------------------------------------------------------------


class KpiSnapshotResponse(BaseModel):
    """Single KPI snapshot matching BRD SS10.5 format."""

    id: int
    kpi_id: str = Field(
        ...,
        examples=["p95_response_time_lite"],
        description="Machine-readable KPI identifier",
    )
    kpi_name: str = Field(
        ...,
        examples=["P95 Response Time (Lite)"],
        description="Human-readable KPI name",
    )
    snapshot_date: date
    snapshot_period: SnapshotPeriod | None = None
    value: Decimal = Field(..., description="KPI value")
    unit: str | None = Field(None, examples=["ms", "%", "count"])
    target: Decimal | None = Field(None, description="Target value for this KPI")
    status: str | None = Field(
        None,
        examples=["meeting_target", "below_target", "above_target"],
        description="Whether the KPI is meeting its target",
    )
    dimensions: dict[str, Any] | None = Field(
        None, description="Dimensional breakdowns (e.g. by tier, region)"
    )
    metadata_info: dict[str, Any] | None = Field(
        None, description="Additional context"
    )
    created_at: datetime

    model_config = {"from_attributes": True}


class KpiListResponse(BaseModel):
    """Paginated list of KPI snapshots with filtering."""

    items: list[KpiSnapshotResponse]
    total: int
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    pages: int = Field(ge=0)


class KpiHistoryPoint(BaseModel):
    """Single data point in a KPI time series."""

    snapshot_date: date
    value: Decimal
    target: Decimal | None = None
    status: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class KpiHistoryResponse(BaseModel):
    """Time series history for a specific KPI."""

    kpi_id: str
    kpi_name: str
    unit: str | None = None
    period: SnapshotPeriod | None = None
    data_points: list[KpiHistoryPoint]
    total: int
