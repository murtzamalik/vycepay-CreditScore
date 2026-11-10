"""Tests for audit log retention policy service (Phase 12.4).

Covers:
  - Retention period lookup per category
  - Cutoff date calculation
  - Expired entry counting
  - Cleanup execution (with dry run)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.audit_log import AuditLogCategory
from app.services.audit_retention import (
    RETENTION_POLICIES,
    AuditRetentionService,
    CleanupSummary,
    RetentionResult,
)


class TestRetentionPolicies:
    """Retention period configuration tests."""

    def test_api_request_10_years(self) -> None:
        assert RETENTION_POLICIES[AuditLogCategory.API_REQUEST] == 10

    def test_authentication_7_years(self) -> None:
        assert RETENTION_POLICIES[AuditLogCategory.AUTHENTICATION] == 7

    def test_score_calculation_10_years(self) -> None:
        assert RETENTION_POLICIES[AuditLogCategory.SCORE_CALCULATION] == 10

    def test_admin_action_10_years(self) -> None:
        assert RETENTION_POLICIES[AuditLogCategory.ADMIN_ACTION] == 10

    def test_system_event_3_years(self) -> None:
        assert RETENTION_POLICIES[AuditLogCategory.SYSTEM_EVENT] == 3

    def test_all_categories_have_policy(self) -> None:
        for cat in AuditLogCategory:
            assert cat in RETENTION_POLICIES


class TestRetentionYearsLookup:
    """get_retention_years method tests."""

    def test_known_category(self) -> None:
        years = AuditRetentionService.get_retention_years(AuditLogCategory.AUTHENTICATION)
        assert years == 7

    def test_system_event_short_retention(self) -> None:
        years = AuditRetentionService.get_retention_years(AuditLogCategory.SYSTEM_EVENT)
        assert years == 3


class TestCutoffDateCalculation:
    """Cutoff date calculation tests."""

    def test_cutoff_10_years_ago(self) -> None:
        cutoff = AuditRetentionService.get_cutoff_date(10)
        expected = datetime.now(timezone.utc) - timedelta(days=10 * 365)
        # Allow 1 second tolerance
        assert abs((cutoff - expected).total_seconds()) < 1

    def test_cutoff_3_years_ago(self) -> None:
        cutoff = AuditRetentionService.get_cutoff_date(3)
        expected = datetime.now(timezone.utc) - timedelta(days=3 * 365)
        assert abs((cutoff - expected).total_seconds()) < 1


class TestCountExpiredEntries:
    """count_expired_entries method tests."""

    @pytest.mark.asyncio
    async def test_count_returns_dict(self) -> None:
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 0
        mock_db.execute = AsyncMock(return_value=mock_result)

        counts = await AuditRetentionService.count_expired_entries(mock_db)
        assert isinstance(counts, dict)

    @pytest.mark.asyncio
    async def test_count_with_expired_entries(self) -> None:
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 42
        mock_db.execute = AsyncMock(return_value=mock_result)

        counts = await AuditRetentionService.count_expired_entries(
            mock_db, category=AuditLogCategory.SYSTEM_EVENT
        )
        assert "SYSTEM_EVENT" in counts
        assert counts["SYSTEM_EVENT"] == 42


class TestCleanupCategory:
    """cleanup_category method tests."""

    @pytest.mark.asyncio
    async def test_dry_run_does_not_delete(self) -> None:
        mock_db = AsyncMock()
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 5
        mock_db.execute = AsyncMock(return_value=mock_count_result)

        result = await AuditRetentionService.cleanup_category(
            db=mock_db,
            category=AuditLogCategory.SYSTEM_EVENT,
            dry_run=True,
        )

        assert isinstance(result, RetentionResult)
        assert result.category == "SYSTEM_EVENT"
        assert result.retention_years == 3
        assert result.entries_deleted == 5  # Reported but not actually deleted

    @pytest.mark.asyncio
    async def test_no_expired_entries(self) -> None:
        mock_db = AsyncMock()
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0
        mock_db.execute = AsyncMock(return_value=mock_count_result)

        result = await AuditRetentionService.cleanup_category(
            db=mock_db,
            category=AuditLogCategory.API_REQUEST,
        )

        assert result.entries_deleted == 0


class TestFullCleanup:
    """run_full_cleanup method tests."""

    @pytest.mark.asyncio
    async def test_dry_run_returns_summary(self) -> None:
        mock_db = AsyncMock()
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0
        mock_db.execute = AsyncMock(return_value=mock_count_result)

        summary = await AuditRetentionService.run_full_cleanup(
            db=mock_db, dry_run=True,
        )

        assert isinstance(summary, CleanupSummary)
        assert summary.run_timestamp is not None
        assert len(summary.results) == len(AuditLogCategory)
        assert len(summary.errors) == 0


class TestRetentionResult:
    """RetentionResult dataclass tests."""

    def test_creation(self) -> None:
        result = RetentionResult(
            category="SYSTEM_EVENT",
            retention_years=3,
            cutoff_date=datetime.now(timezone.utc),
            entries_deleted=10,
            entries_archived=0,
        )
        assert result.category == "SYSTEM_EVENT"
        assert result.entries_deleted == 10
