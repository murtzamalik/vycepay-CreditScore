"""KPI endpoints (Task 9.1).

Provides read access to KPI snapshots stored in the kpi_snapshots TimescaleDB
hypertable. All endpoints require JWT authentication with Admin or Operator role.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.security import get_current_user
from app.dependencies import get_db
from app.models.kpi_snapshot import KPISnapshot, SnapshotPeriod
from app.models.user import User, UserRole
from app.schemas.kpis import (
    KpiHistoryPoint,
    KpiHistoryResponse,
    KpiListResponse,
    KpiSnapshotResponse,
)

router = APIRouter(prefix="/kpis", tags=["kpis"])


# ---------------------------------------------------------------------------
# RBAC helper
# ---------------------------------------------------------------------------

def _require_admin_or_operator(user: User) -> None:
    """Raise 403 if the user is not an Admin or Operator."""
    if user.role not in (UserRole.ADMIN, UserRole.OPERATOR):
        from app.core.exceptions import ForbiddenError

        raise ForbiddenError("Admin or Operator role required to view KPIs")


# ---------------------------------------------------------------------------
# GET /v1/kpis -- List KPI snapshots
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=KpiListResponse,
    summary="List KPI snapshots",
)
async def list_kpis(
    kpi_id: str | None = Query(None, description="Filter by KPI identifier"),
    period: SnapshotPeriod | None = Query(None, description="Filter by snapshot period"),
    start_date: date | None = Query(None, description="Start date (inclusive)"),
    end_date: date | None = Query(None, description="End date (inclusive)"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> KpiListResponse:
    """Return a paginated list of KPI snapshots with optional filtering.

    Requires **Admin** or **Operator** role.
    """
    _require_admin_or_operator(current_user)

    # Base query
    query = select(KPISnapshot)
    count_query = select(func.count()).select_from(KPISnapshot)

    # Apply filters
    if kpi_id is not None:
        query = query.where(KPISnapshot.kpi_id == kpi_id)
        count_query = count_query.where(KPISnapshot.kpi_id == kpi_id)
    if period is not None:
        query = query.where(KPISnapshot.snapshot_period == period)
        count_query = count_query.where(KPISnapshot.snapshot_period == period)
    if start_date is not None:
        query = query.where(KPISnapshot.snapshot_date >= start_date)
        count_query = count_query.where(KPISnapshot.snapshot_date >= start_date)
    if end_date is not None:
        query = query.where(KPISnapshot.snapshot_date <= end_date)
        count_query = count_query.where(KPISnapshot.snapshot_date <= end_date)

    # Count
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Fetch page
    offset = (page - 1) * limit
    query = (
        query.order_by(KPISnapshot.snapshot_date.desc(), KPISnapshot.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    items = result.scalars().all()

    pages = (total + limit - 1) // limit if total > 0 else 0

    return KpiListResponse(
        items=[KpiSnapshotResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=limit,
        pages=pages,
    )


# ---------------------------------------------------------------------------
# GET /v1/kpis/{kpiId}/history -- KPI time series
# ---------------------------------------------------------------------------


@router.get(
    "/{kpi_id}/history",
    response_model=KpiHistoryResponse,
    summary="Get KPI time series history",
)
async def get_kpi_history(
    kpi_id: str,
    period: SnapshotPeriod | None = Query(None, description="Filter by period"),
    start_date: date | None = Query(None, description="Start date (inclusive)"),
    end_date: date | None = Query(None, description="End date (inclusive)"),
    limit: int = Query(100, ge=1, le=1000, description="Max data points"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> KpiHistoryResponse:
    """Return time series data for a specific KPI.

    Requires **Admin** or **Operator** role.
    """
    _require_admin_or_operator(current_user)

    # Verify KPI exists -- fetch the most recent snapshot for metadata
    latest_query = (
        select(KPISnapshot)
        .where(KPISnapshot.kpi_id == kpi_id)
        .order_by(KPISnapshot.snapshot_date.desc())
        .limit(1)
    )
    latest_result = await db.execute(latest_query)
    latest = latest_result.scalar_one_or_none()

    if latest is None:
        raise NotFoundError(f"KPI '{kpi_id}' not found")

    # Build data points query
    query = select(KPISnapshot).where(KPISnapshot.kpi_id == kpi_id)

    if period is not None:
        query = query.where(KPISnapshot.snapshot_period == period)
    if start_date is not None:
        query = query.where(KPISnapshot.snapshot_date >= start_date)
    if end_date is not None:
        query = query.where(KPISnapshot.snapshot_date <= end_date)

    query = query.order_by(KPISnapshot.snapshot_date.asc()).limit(limit)

    result = await db.execute(query)
    rows = result.scalars().all()

    data_points = [
        KpiHistoryPoint(
            snapshot_date=row.snapshot_date,
            value=row.value,
            target=row.target,
            status=row.status,
            created_at=row.created_at,
        )
        for row in rows
    ]

    return KpiHistoryResponse(
        kpi_id=latest.kpi_id,
        kpi_name=latest.kpi_name,
        unit=latest.unit,
        period=period or latest.snapshot_period,
        data_points=data_points,
        total=len(data_points),
    )
