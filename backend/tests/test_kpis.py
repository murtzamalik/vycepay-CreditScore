"""Tests for KPI endpoints, calculators, and Prometheus metrics (Phase 9)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.models.kpi_snapshot import KPISnapshot, SnapshotPeriod
from app.schemas.kpis import (
    KpiHistoryPoint,
    KpiHistoryResponse,
    KpiListResponse,
    KpiSnapshotResponse,
)


# ---------------------------------------------------------------------------
# Schema Tests (Task 9.10)
# ---------------------------------------------------------------------------


class TestKpiSchemas:
    """Verify Pydantic schemas for KPI responses."""

    def test_kpi_snapshot_response_from_attributes(self) -> None:
        """KpiSnapshotResponse should accept ORM-like objects."""
        now = datetime.now(timezone.utc)
        snapshot = KpiSnapshotResponse(
            id=1,
            kpi_id="p95_response_time_lite",
            kpi_name="P95 Response Time (Lite)",
            snapshot_date=date.today(),
            snapshot_period=SnapshotPeriod.HOURLY,
            value=Decimal("245.50"),
            unit="ms",
            target=Decimal("500"),
            status="meeting_target",
            dimensions={"hour": "2026-03-08T10:00:00+00:00"},
            metadata_info=None,
            created_at=now,
        )
        assert snapshot.kpi_id == "p95_response_time_lite"
        assert snapshot.value == Decimal("245.50")
        assert snapshot.status == "meeting_target"

    def test_kpi_list_response(self) -> None:
        """KpiListResponse should hold paginated items."""
        resp = KpiListResponse(
            items=[],
            total=0,
            page=1,
            page_size=50,
            pages=0,
        )
        assert resp.total == 0
        assert resp.items == []

    def test_kpi_history_response(self) -> None:
        """KpiHistoryResponse should hold time series data."""
        now = datetime.now(timezone.utc)
        resp = KpiHistoryResponse(
            kpi_id="error_rate",
            kpi_name="API Error Rate",
            unit="%",
            period=SnapshotPeriod.HOURLY,
            data_points=[
                KpiHistoryPoint(
                    snapshot_date=date.today(),
                    value=Decimal("0.05"),
                    target=Decimal("0.1"),
                    status="meeting_target",
                    created_at=now,
                ),
            ],
            total=1,
        )
        assert resp.total == 1
        assert resp.data_points[0].value == Decimal("0.05")


# ---------------------------------------------------------------------------
# Calculator Tests (Tasks 9.2-9.5)
# ---------------------------------------------------------------------------


class TestKpiCalculatorHelpers:
    """Test the _snapshot helper and calculator logic."""

    def test_snapshot_meeting_target(self) -> None:
        """Snapshot with value <= target should have status meeting_target."""
        from app.services.kpi_calculators import _snapshot

        snap = _snapshot(
            kpi_id="test",
            kpi_name="Test KPI",
            value=Decimal("100"),
            unit="ms",
            target=Decimal("500"),
            period=SnapshotPeriod.HOURLY,
            snapshot_date=date.today(),
        )
        assert snap.status == "meeting_target"

    def test_snapshot_above_target(self) -> None:
        """Snapshot with value > target should have status above_target."""
        from app.services.kpi_calculators import _snapshot

        snap = _snapshot(
            kpi_id="test",
            kpi_name="Test KPI",
            value=Decimal("600"),
            unit="ms",
            target=Decimal("500"),
            period=SnapshotPeriod.HOURLY,
            snapshot_date=date.today(),
        )
        assert snap.status == "above_target"

    def test_snapshot_no_target(self) -> None:
        """Snapshot without target should have status None."""
        from app.services.kpi_calculators import _snapshot

        snap = _snapshot(
            kpi_id="test",
            kpi_name="Test KPI",
            value=Decimal("42"),
            unit="count",
            period=SnapshotPeriod.DAILY,
            snapshot_date=date.today(),
        )
        assert snap.status is None

    def test_snapshot_fields(self) -> None:
        """Snapshot should populate all provided fields."""
        from app.services.kpi_calculators import _snapshot

        today = date.today()
        snap = _snapshot(
            kpi_id="auc_roc",
            kpi_name="Model AUC-ROC",
            value=Decimal("0.78"),
            unit="score",
            target=Decimal("0.75"),
            period=SnapshotPeriod.DAILY,
            snapshot_date=today,
            dimensions={"model": "v1.0"},
            metadata_info={"source": "mlflow"},
        )
        assert snap.kpi_id == "auc_roc"
        assert snap.kpi_name == "Model AUC-ROC"
        assert snap.snapshot_date == today
        assert snap.snapshot_period == SnapshotPeriod.DAILY
        assert snap.value == Decimal("0.78")
        assert snap.unit == "score"
        assert snap.target == Decimal("0.75")
        assert snap.dimensions == {"model": "v1.0"}
        assert snap.metadata_info == {"source": "mlflow"}


class TestHourlyCalculators:
    """Test hourly KPI calculator with mocked DB."""

    @pytest.mark.asyncio
    async def test_hourly_kpis_with_data(self) -> None:
        """Hourly calculator should produce p95 and error rate snapshots."""
        from app.services.kpi_calculators import calculate_hourly_kpis

        # Mock session with two queries: p95 per tier + error rate
        mock_session = AsyncMock()

        # First two calls: p95 for lite, p95 for pro
        p95_lite_result = MagicMock()
        p95_lite_result.scalar_one_or_none.return_value = 320.5

        p95_pro_result = MagicMock()
        p95_pro_result.scalar_one_or_none.return_value = 1500.0

        # Third call: error rate
        error_row = MagicMock()
        error_row.total = 1000
        error_row.errors = 2
        error_result = MagicMock()
        error_result.one.return_value = error_row

        mock_session.execute = AsyncMock(
            side_effect=[p95_lite_result, p95_pro_result, error_result]
        )

        snapshots = await calculate_hourly_kpis(mock_session)

        assert len(snapshots) == 3

        # Check lite P95
        lite_snap = snapshots[0]
        assert lite_snap.kpi_id == "p95_response_time_lite"
        assert lite_snap.value == Decimal("320.5")
        assert lite_snap.status == "meeting_target"  # 320.5 <= 500

        # Check pro P95
        pro_snap = snapshots[1]
        assert pro_snap.kpi_id == "p95_response_time_pro"
        assert pro_snap.value == Decimal("1500.0")
        assert pro_snap.status == "meeting_target"  # 1500 <= 2000

        # Check error rate
        error_snap = snapshots[2]
        assert error_snap.kpi_id == "error_rate"
        assert error_snap.value == Decimal("0.2")  # 2/1000 * 100
        assert error_snap.status == "above_target"  # 0.2 > 0.1

    @pytest.mark.asyncio
    async def test_hourly_kpis_no_data(self) -> None:
        """Hourly calculator should return empty list when no requests exist."""
        from app.services.kpi_calculators import calculate_hourly_kpis

        mock_session = AsyncMock()

        # P95 queries return None
        p95_result = MagicMock()
        p95_result.scalar_one_or_none.return_value = None

        # Error rate query returns zero total
        error_row = MagicMock()
        error_row.total = 0
        error_row.errors = 0
        error_result = MagicMock()
        error_result.one.return_value = error_row

        mock_session.execute = AsyncMock(
            side_effect=[p95_result, p95_result, error_result]
        )

        snapshots = await calculate_hourly_kpis(mock_session)
        assert len(snapshots) == 0


class TestDailyCalculators:
    """Test daily KPI calculator with mocked DB."""

    @pytest.mark.asyncio
    async def test_daily_kpis(self) -> None:
        """Daily calculator should produce volume + placeholder snapshots."""
        from app.services.kpi_calculators import calculate_daily_kpis

        mock_session = AsyncMock()

        volume_result = MagicMock()
        volume_result.scalar_one.return_value = 5000

        mock_session.execute = AsyncMock(return_value=volume_result)

        snapshots = await calculate_daily_kpis(mock_session)

        assert len(snapshots) == 4
        kpi_ids = {s.kpi_id for s in snapshots}
        assert kpi_ids == {"daily_query_volume", "auc_roc", "data_completeness", "feature_freshness"}

        volume_snap = next(s for s in snapshots if s.kpi_id == "daily_query_volume")
        assert volume_snap.value == Decimal("5000")
        assert volume_snap.unit == "count"


class TestWeeklyCalculators:
    """Test weekly KPI calculator."""

    @pytest.mark.asyncio
    async def test_weekly_kpis(self) -> None:
        """Weekly calculator should produce placeholder snapshots."""
        from app.services.kpi_calculators import calculate_weekly_kpis

        mock_session = AsyncMock()
        snapshots = await calculate_weekly_kpis(mock_session)

        assert len(snapshots) == 2
        kpi_ids = {s.kpi_id for s in snapshots}
        assert kpi_ids == {"precision_at_k", "calibration_error"}


class TestMonthlyCalculators:
    """Test monthly KPI calculator with mocked DB."""

    @pytest.mark.asyncio
    async def test_monthly_kpis(self) -> None:
        """Monthly calculator should produce availability, adoption, and ARPU."""
        from app.services.kpi_calculators import calculate_monthly_kpis

        mock_session = AsyncMock()

        # Availability query
        avail_row = MagicMock()
        avail_row.total = 10000
        avail_row.errors = 5
        avail_result = MagicMock()
        avail_result.one.return_value = avail_row

        # Adoption query
        adoption_row = MagicMock()
        adoption_row.total = 20
        adoption_row.active = 15
        adoption_result = MagicMock()
        adoption_result.one.return_value = adoption_row

        mock_session.execute = AsyncMock(
            side_effect=[avail_result, adoption_result]
        )

        snapshots = await calculate_monthly_kpis(mock_session)

        assert len(snapshots) == 3
        kpi_ids = {s.kpi_id for s in snapshots}
        assert kpi_ids == {"system_availability", "customer_adoption_rate", "arpu"}

        avail_snap = next(s for s in snapshots if s.kpi_id == "system_availability")
        assert avail_snap.value == Decimal("99.95")  # (1 - 5/10000) * 100
        assert avail_snap.status == "meeting_target"  # 99.95 <= 99.9 -- wait, 99.95 > 99.9 but <=

        adoption_snap = next(s for s in snapshots if s.kpi_id == "customer_adoption_rate")
        assert adoption_snap.value == Decimal("75.0")


# ---------------------------------------------------------------------------
# Prometheus Metrics Tests (Task 9.6)
# ---------------------------------------------------------------------------


class TestPrometheusMetrics:
    """Test Prometheus metric registration and endpoint."""

    def test_metrics_registry_has_expected_metrics(self) -> None:
        """Registry should contain all defined metrics."""
        from app.core.metrics import REGISTRY

        metric_names = {m.name for m in REGISTRY.collect() if m.name}
        # Check key metrics exist (prometheus_client may prefix with collector name)
        assert "vycescore_http_requests_total" in metric_names or any(
            "vycescore_http_requests" in n for n in metric_names
        )

    def test_request_counter_labels(self) -> None:
        """REQUEST_COUNT should accept method, endpoint, status labels."""
        from app.core.metrics import REQUEST_COUNT

        # This should not raise
        REQUEST_COUNT.labels(method="GET", endpoint="/v1/health", status="200").inc(0)

    def test_request_latency_labels(self) -> None:
        """REQUEST_LATENCY should accept method and endpoint labels."""
        from app.core.metrics import REQUEST_LATENCY

        REQUEST_LATENCY.labels(method="GET", endpoint="/v1/health").observe(0.001)

    def test_score_generation_counter(self) -> None:
        """SCORE_GENERATION_COUNT should accept tier and cache_hit labels."""
        from app.core.metrics import SCORE_GENERATION_COUNT

        SCORE_GENERATION_COUNT.labels(tier="lite", cache_hit="false").inc(0)

    def test_model_inference_latency(self) -> None:
        """MODEL_INFERENCE_LATENCY should accept model_version label."""
        from app.core.metrics import MODEL_INFERENCE_LATENCY

        MODEL_INFERENCE_LATENCY.labels(model_version="v1.0.0").observe(0.05)

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, async_client: AsyncClient) -> None:
        """GET /metrics should return Prometheus text format."""
        response = await async_client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "") or \
               "text/plain" in response.headers.get("Content-Type", "") or \
               "openmetrics" in response.headers.get("content-type", "")

    def test_normalise_path(self) -> None:
        """Path normaliser should collapse dynamic segments."""
        from app.core.metrics import _normalise_path

        assert _normalise_path("/v1/health") == "/v1/health"
        assert _normalise_path("/v1/scores/lite/1234567890") == "/v1/scores/lite/{id}"
        assert _normalise_path("/metrics") == "/metrics"


# ---------------------------------------------------------------------------
# KPI Scheduler Tests (Task 9.9)
# ---------------------------------------------------------------------------


class TestKpiScheduler:
    """Test scheduler lifecycle."""

    def test_start_and_stop_scheduler(self) -> None:
        """Scheduler should start and stop without error."""
        from app.services.kpi_scheduler import start_kpi_scheduler, stop_kpi_scheduler

        scheduler = start_kpi_scheduler()
        assert scheduler.running

        # Verify jobs are registered
        job_ids = {job.id for job in scheduler.get_jobs()}
        assert "kpi_hourly" in job_ids
        assert "kpi_daily" in job_ids
        assert "kpi_weekly" in job_ids
        assert "kpi_monthly" in job_ids

        stop_kpi_scheduler()
        assert not scheduler.running

    def test_start_scheduler_idempotent(self) -> None:
        """Starting scheduler twice should not create duplicate."""
        from app.services.kpi_scheduler import start_kpi_scheduler, stop_kpi_scheduler

        s1 = start_kpi_scheduler()
        s2 = start_kpi_scheduler()
        assert s1 is s2

        stop_kpi_scheduler()


# ---------------------------------------------------------------------------
# API Endpoint Tests (Task 9.1)
# ---------------------------------------------------------------------------


class TestKpiEndpoints:
    """Test KPI API endpoints (require auth mocking)."""

    @pytest.mark.asyncio
    async def test_list_kpis_requires_auth(self, async_client: AsyncClient) -> None:
        """GET /v1/kpis without auth should return 401."""
        response = await async_client.get("/v1/kpis")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_kpi_history_requires_auth(self, async_client: AsyncClient) -> None:
        """GET /v1/kpis/{kpiId}/history without auth should return 401."""
        response = await async_client.get("/v1/kpis/error_rate/history")
        assert response.status_code == 401
