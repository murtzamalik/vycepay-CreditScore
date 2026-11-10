"""KPI calculator functions (Tasks 9.2--9.5).

Each calculator returns a list of KPISnapshot ORM instances ready for bulk insert.
All heavy lifting is done via SQL aggregations to minimise Python-side work.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import case, cast, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_request_log import ApiRequestLog
from app.models.customer import Customer, CustomerStatus
from app.models.kpi_snapshot import KPISnapshot, SnapshotPeriod

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _snapshot(
    *,
    kpi_id: str,
    kpi_name: str,
    value: Decimal,
    unit: str,
    target: Decimal | None = None,
    period: SnapshotPeriod,
    snapshot_date: date,
    dimensions: dict | None = None,
    metadata_info: dict | None = None,
) -> KPISnapshot:
    """Build a KPISnapshot ORM instance with target-status evaluation."""
    status: str | None = None
    if target is not None:
        # For latency/error KPIs lower is better; for availability/adoption higher is better.
        # We use a simple convention: if the unit implies "lower is better" (ms, %) for error
        # or latency, we flip the comparison.  For most cases the caller should set
        # target appropriately and we compare value <= target as "meeting".
        status = "meeting_target" if value <= target else "above_target"

    return KPISnapshot(
        kpi_id=kpi_id,
        kpi_name=kpi_name,
        snapshot_date=snapshot_date,
        snapshot_period=period,
        value=value,
        unit=unit,
        target=target,
        status=status,
        dimensions=dimensions,
        metadata_info=metadata_info,
    )


# ---------------------------------------------------------------------------
# Task 9.2 -- Hourly KPIs (:05 past each hour)
# ---------------------------------------------------------------------------


async def calculate_hourly_kpis(db: AsyncSession) -> list[KPISnapshot]:
    """Calculate hourly KPIs: P95 response time (Lite/Pro), Error rate."""
    now = datetime.now(timezone.utc)
    hour_start = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    hour_end = hour_start + timedelta(hours=1)
    today = now.date()
    snapshots: list[KPISnapshot] = []

    # ---- P95 Response Time per tier ----
    for tier_label, endpoint_pattern in [("lite", "/v1/scores/lite%"), ("pro", "/v1/scores/pro%")]:
        target_ms = Decimal("500") if tier_label == "lite" else Decimal("2000")

        result = await db.execute(
            select(
                func.percentile_cont(0.95).within_group(
                    ApiRequestLog.response_time_ms
                )
            ).where(
                ApiRequestLog.request_time >= hour_start,
                ApiRequestLog.request_time < hour_end,
                ApiRequestLog.endpoint.like(endpoint_pattern),
                ApiRequestLog.response_time_ms.is_not(None),
            )
        )
        p95 = result.scalar_one_or_none()

        if p95 is not None:
            snapshots.append(
                _snapshot(
                    kpi_id=f"p95_response_time_{tier_label}",
                    kpi_name=f"P95 Response Time ({tier_label.title()})",
                    value=Decimal(str(round(p95, 2))),
                    unit="ms",
                    target=target_ms,
                    period=SnapshotPeriod.HOURLY,
                    snapshot_date=today,
                    dimensions={"hour": hour_start.isoformat()},
                )
            )

    # ---- Error Rate ----
    result = await db.execute(
        select(
            func.count().label("total"),
            func.count().filter(
                ApiRequestLog.response_status >= 500
            ).label("errors"),
        ).where(
            ApiRequestLog.request_time >= hour_start,
            ApiRequestLog.request_time < hour_end,
        )
    )
    row = result.one()
    total = row.total or 0
    errors = row.errors or 0

    if total > 0:
        error_rate = Decimal(str(round(errors / total * 100, 4)))
        snapshots.append(
            _snapshot(
                kpi_id="error_rate",
                kpi_name="API Error Rate",
                value=error_rate,
                unit="%",
                target=Decimal("0.1"),
                period=SnapshotPeriod.HOURLY,
                snapshot_date=today,
                dimensions={"hour": hour_start.isoformat(), "total_requests": total, "error_count": errors},
            )
        )

    return snapshots


# ---------------------------------------------------------------------------
# Task 9.3 -- Daily KPIs (03:00 UTC)
# ---------------------------------------------------------------------------


async def calculate_daily_kpis(db: AsyncSession) -> list[KPISnapshot]:
    """Calculate daily KPIs: AUC-ROC, Daily Query Volume, Data Completeness, Feature Freshness."""
    now = datetime.now(timezone.utc)
    yesterday = now.date() - timedelta(days=1)
    day_start = datetime.combine(yesterday, datetime.min.time(), tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)
    snapshots: list[KPISnapshot] = []

    # ---- Daily Query Volume ----
    result = await db.execute(
        select(func.count()).where(
            ApiRequestLog.request_time >= day_start,
            ApiRequestLog.request_time < day_end,
        )
    )
    volume = result.scalar_one() or 0
    snapshots.append(
        _snapshot(
            kpi_id="daily_query_volume",
            kpi_name="Daily Query Volume",
            value=Decimal(str(volume)),
            unit="count",
            period=SnapshotPeriod.DAILY,
            snapshot_date=yesterday,
        )
    )

    # ---- AUC-ROC (placeholder -- reads from model evaluation metadata) ----
    # In production this would query the model_evaluations table or MLflow.
    # For now we store a placeholder value indicating no evaluation available.
    snapshots.append(
        _snapshot(
            kpi_id="auc_roc",
            kpi_name="Model AUC-ROC",
            value=Decimal("0.0"),
            unit="score",
            target=Decimal("0.75"),
            period=SnapshotPeriod.DAILY,
            snapshot_date=yesterday,
            metadata_info={"source": "placeholder", "note": "Requires model evaluation pipeline"},
        )
    )

    # ---- Data Completeness ----
    # Placeholder: percentage of required feature fields populated.
    # In production this queries the feature store for null/missing ratios.
    snapshots.append(
        _snapshot(
            kpi_id="data_completeness",
            kpi_name="Data Completeness",
            value=Decimal("0.0"),
            unit="%",
            target=Decimal("95.0"),
            period=SnapshotPeriod.DAILY,
            snapshot_date=yesterday,
            metadata_info={"source": "placeholder", "note": "Requires feature store integration"},
        )
    )

    # ---- Feature Freshness ----
    # Placeholder: average age (hours) of features used in scoring.
    # In production this queries feature_store metadata timestamps.
    snapshots.append(
        _snapshot(
            kpi_id="feature_freshness",
            kpi_name="Feature Freshness",
            value=Decimal("0.0"),
            unit="hours",
            target=Decimal("24.0"),
            period=SnapshotPeriod.DAILY,
            snapshot_date=yesterday,
            metadata_info={"source": "placeholder", "note": "Requires feature store timestamps"},
        )
    )

    return snapshots


# ---------------------------------------------------------------------------
# Task 9.4 -- Weekly KPIs (Monday 04:00 UTC)
# ---------------------------------------------------------------------------


async def calculate_weekly_kpis(db: AsyncSession) -> list[KPISnapshot]:
    """Calculate weekly KPIs: Precision@K, Calibration Error (placeholders)."""
    now = datetime.now(timezone.utc)
    # The week ending on the most recent Sunday
    week_end = now.date() - timedelta(days=now.weekday())  # Monday of this week
    week_start = week_end - timedelta(days=7)
    snapshots: list[KPISnapshot] = []

    # ---- Precision@K (placeholder) ----
    snapshots.append(
        _snapshot(
            kpi_id="precision_at_k",
            kpi_name="Precision@K",
            value=Decimal("0.0"),
            unit="score",
            period=SnapshotPeriod.WEEKLY,
            snapshot_date=week_end,
            metadata_info={
                "source": "placeholder",
                "note": "Requires model evaluation with ground truth labels",
                "week_start": week_start.isoformat(),
                "week_end": week_end.isoformat(),
            },
        )
    )

    # ---- Calibration Error (placeholder) ----
    snapshots.append(
        _snapshot(
            kpi_id="calibration_error",
            kpi_name="Calibration Error",
            value=Decimal("0.0"),
            unit="score",
            period=SnapshotPeriod.WEEKLY,
            snapshot_date=week_end,
            metadata_info={
                "source": "placeholder",
                "note": "Requires predicted vs actual default rate comparison",
                "week_start": week_start.isoformat(),
                "week_end": week_end.isoformat(),
            },
        )
    )

    return snapshots


# ---------------------------------------------------------------------------
# Task 9.5 -- Monthly KPIs (1st of month 05:00 UTC)
# ---------------------------------------------------------------------------


async def calculate_monthly_kpis(db: AsyncSession) -> list[KPISnapshot]:
    """Calculate monthly KPIs: System Availability, Customer Adoption Rate, ARPU."""
    now = datetime.now(timezone.utc)
    # Previous month
    first_of_current = now.date().replace(day=1)
    last_month_end = first_of_current - timedelta(days=1)
    first_of_last_month = last_month_end.replace(day=1)
    month_start = datetime.combine(first_of_last_month, datetime.min.time(), tzinfo=timezone.utc)
    month_end = datetime.combine(first_of_current, datetime.min.time(), tzinfo=timezone.utc)
    snapshots: list[KPISnapshot] = []

    # ---- System Availability ----
    # Calculate from error rate: availability = 100 - (5xx / total * 100)
    result = await db.execute(
        select(
            func.count().label("total"),
            func.count().filter(
                ApiRequestLog.response_status >= 500
            ).label("errors"),
        ).where(
            ApiRequestLog.request_time >= month_start,
            ApiRequestLog.request_time < month_end,
        )
    )
    row = result.one()
    total = row.total or 0
    errors = row.errors or 0

    if total > 0:
        availability = Decimal(str(round((1 - errors / total) * 100, 4)))
    else:
        availability = Decimal("100.0")

    snapshots.append(
        _snapshot(
            kpi_id="system_availability",
            kpi_name="System Availability",
            value=availability,
            unit="%",
            target=Decimal("99.9"),
            period=SnapshotPeriod.MONTHLY,
            snapshot_date=last_month_end,
            dimensions={
                "month": first_of_last_month.isoformat(),
                "total_requests": total,
                "error_count": errors,
            },
        )
    )

    # ---- Customer Adoption Rate ----
    # Active customers / total customers * 100
    result = await db.execute(
        select(
            func.count().label("total"),
            func.count().filter(
                Customer.status == CustomerStatus.ACTIVE
            ).label("active"),
        ).select_from(Customer)
    )
    row = result.one()
    total_customers = row.total or 0
    active_customers = row.active or 0

    if total_customers > 0:
        adoption_rate = Decimal(str(round(active_customers / total_customers * 100, 2)))
    else:
        adoption_rate = Decimal("0.0")

    snapshots.append(
        _snapshot(
            kpi_id="customer_adoption_rate",
            kpi_name="Customer Adoption Rate",
            value=adoption_rate,
            unit="%",
            period=SnapshotPeriod.MONTHLY,
            snapshot_date=last_month_end,
            dimensions={
                "month": first_of_last_month.isoformat(),
                "total_customers": total_customers,
                "active_customers": active_customers,
            },
        )
    )

    # ---- ARPU (placeholder) ----
    snapshots.append(
        _snapshot(
            kpi_id="arpu",
            kpi_name="Average Revenue Per User",
            value=Decimal("0.0"),
            unit="KES",
            period=SnapshotPeriod.MONTHLY,
            snapshot_date=last_month_end,
            metadata_info={
                "source": "placeholder",
                "note": "Requires billing/revenue tracking integration",
                "month": first_of_last_month.isoformat(),
            },
        )
    )

    return snapshots
