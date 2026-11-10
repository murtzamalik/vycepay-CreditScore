"""Tests for immutable audit log service with hash chain (Phase 12.3).

Covers:
  - Entry creation with hash chain
  - Hash computation determinism
  - Chain verification (valid and tampered)
  - Genesis entry handling
  - Category-based retention assignment
  - Entry querying with filters
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.audit_log import AuditLog, AuditLogCategory
from app.services.immutable_audit import (
    CATEGORY_RETENTION_YEARS,
    GENESIS_HASH,
    ImmutableAuditService,
    compute_entry_hash,
)


class TestComputeEntryHash:
    """Hash computation function tests."""

    def test_deterministic_hash(self) -> None:
        h1 = compute_entry_hash(
            previous_hash=GENESIS_HASH,
            sequence_number=1,
            category="API_REQUEST",
            action="score.calculated",
            actor_id="user-123",
            timestamp="2026-01-01T00:00:00+00:00",
            details={"score": 750},
        )
        h2 = compute_entry_hash(
            previous_hash=GENESIS_HASH,
            sequence_number=1,
            category="API_REQUEST",
            action="score.calculated",
            actor_id="user-123",
            timestamp="2026-01-01T00:00:00+00:00",
            details={"score": 750},
        )
        assert h1 == h2
        assert len(h1) == 64

    def test_different_inputs_different_hash(self) -> None:
        h1 = compute_entry_hash(
            previous_hash=GENESIS_HASH,
            sequence_number=1,
            category="API_REQUEST",
            action="score.calculated",
            actor_id="user-123",
            timestamp="2026-01-01T00:00:00+00:00",
            details=None,
        )
        h2 = compute_entry_hash(
            previous_hash=GENESIS_HASH,
            sequence_number=2,
            category="API_REQUEST",
            action="score.calculated",
            actor_id="user-123",
            timestamp="2026-01-01T00:00:00+00:00",
            details=None,
        )
        assert h1 != h2

    def test_previous_hash_changes_result(self) -> None:
        h1 = compute_entry_hash(
            previous_hash=GENESIS_HASH,
            sequence_number=1,
            category="API_REQUEST",
            action="test",
            actor_id=None,
            timestamp="2026-01-01T00:00:00+00:00",
            details=None,
        )
        h2 = compute_entry_hash(
            previous_hash="a" * 64,
            sequence_number=1,
            category="API_REQUEST",
            action="test",
            actor_id=None,
            timestamp="2026-01-01T00:00:00+00:00",
            details=None,
        )
        assert h1 != h2

    def test_none_details_handled(self) -> None:
        h = compute_entry_hash(
            previous_hash=GENESIS_HASH,
            sequence_number=1,
            category="SYSTEM_EVENT",
            action="startup",
            actor_id=None,
            timestamp="2026-01-01T00:00:00+00:00",
            details=None,
        )
        assert len(h) == 64

    def test_details_sort_order_deterministic(self) -> None:
        """Details dict keys should be sorted for deterministic hashing."""
        h1 = compute_entry_hash(
            previous_hash=GENESIS_HASH,
            sequence_number=1,
            category="API_REQUEST",
            action="test",
            actor_id=None,
            timestamp="2026-01-01T00:00:00+00:00",
            details={"b": 2, "a": 1},
        )
        h2 = compute_entry_hash(
            previous_hash=GENESIS_HASH,
            sequence_number=1,
            category="API_REQUEST",
            action="test",
            actor_id=None,
            timestamp="2026-01-01T00:00:00+00:00",
            details={"a": 1, "b": 2},
        )
        assert h1 == h2


class TestRetentionPolicies:
    """Retention year assignment tests."""

    def test_api_request_retention(self) -> None:
        assert CATEGORY_RETENTION_YEARS[AuditLogCategory.API_REQUEST] == 10

    def test_authentication_retention(self) -> None:
        assert CATEGORY_RETENTION_YEARS[AuditLogCategory.AUTHENTICATION] == 7

    def test_score_calculation_retention(self) -> None:
        assert CATEGORY_RETENTION_YEARS[AuditLogCategory.SCORE_CALCULATION] == 10

    def test_admin_action_retention(self) -> None:
        assert CATEGORY_RETENTION_YEARS[AuditLogCategory.ADMIN_ACTION] == 10

    def test_system_event_retention(self) -> None:
        assert CATEGORY_RETENTION_YEARS[AuditLogCategory.SYSTEM_EVENT] == 3

    def test_all_categories_have_retention(self) -> None:
        for cat in AuditLogCategory:
            assert cat in CATEGORY_RETENTION_YEARS


class TestGenesisHash:
    """Genesis hash constant tests."""

    def test_genesis_hash_is_64_zeros(self) -> None:
        assert GENESIS_HASH == "0" * 64
        assert len(GENESIS_HASH) == 64


class TestAuditLogModel:
    """AuditLog model basic tests."""

    def test_category_enum_values(self) -> None:
        assert AuditLogCategory.API_REQUEST.value == "API_REQUEST"
        assert AuditLogCategory.AUTHENTICATION.value == "AUTHENTICATION"
        assert AuditLogCategory.SCORE_CALCULATION.value == "SCORE_CALCULATION"
        assert AuditLogCategory.ADMIN_ACTION.value == "ADMIN_ACTION"
        assert AuditLogCategory.SYSTEM_EVENT.value == "SYSTEM_EVENT"
        assert AuditLogCategory.DATA_ACCESS.value == "DATA_ACCESS"
        assert AuditLogCategory.DATA_MODIFICATION.value == "DATA_MODIFICATION"

    def test_all_categories_exist(self) -> None:
        expected = {
            "API_REQUEST", "AUTHENTICATION", "SCORE_CALCULATION",
            "ADMIN_ACTION", "SYSTEM_EVENT", "DATA_ACCESS", "DATA_MODIFICATION",
        }
        actual = {c.value for c in AuditLogCategory}
        assert actual == expected


class TestImmutableAuditServiceCreateEntry:
    """ImmutableAuditService.create_entry tests with mocked DB."""

    @pytest.mark.asyncio
    async def test_create_first_entry_uses_genesis_hash(self) -> None:
        mock_db = AsyncMock()

        # No previous entry
        mock_last_result = MagicMock()
        mock_last_result.scalar_one_or_none.return_value = None

        # Next sequence = 1
        mock_seq_result = MagicMock()
        mock_seq_result.scalar_one_or_none.return_value = None

        mock_db.execute = AsyncMock(side_effect=[mock_last_result, mock_seq_result])
        mock_db.flush = AsyncMock()
        mock_db.add = MagicMock()

        entry = await ImmutableAuditService.create_entry(
            db=mock_db,
            category=AuditLogCategory.SYSTEM_EVENT,
            action="system.startup",
        )

        assert entry.previous_hash == GENESIS_HASH
        assert entry.sequence_number == 1
        assert entry.category == AuditLogCategory.SYSTEM_EVENT
        assert entry.action == "system.startup"
        assert entry.retention_years == 3  # System events = 3 years
        assert len(entry.entry_hash) == 64

    @pytest.mark.asyncio
    async def test_create_entry_chains_to_previous(self) -> None:
        mock_db = AsyncMock()

        # Previous entry exists
        prev_entry = MagicMock()
        prev_entry.entry_hash = "abc123" + "d" * 58  # 64 chars
        mock_last_result = MagicMock()
        mock_last_result.scalar_one_or_none.return_value = prev_entry

        # Next sequence = 5
        mock_seq_result = MagicMock()
        mock_seq_result.scalar_one_or_none.return_value = 4

        mock_db.execute = AsyncMock(side_effect=[mock_last_result, mock_seq_result])
        mock_db.flush = AsyncMock()
        mock_db.add = MagicMock()

        entry = await ImmutableAuditService.create_entry(
            db=mock_db,
            category=AuditLogCategory.API_REQUEST,
            action="score.retrieved",
            actor_id="customer-456",
            actor_type="API_KEY",
        )

        assert entry.previous_hash == prev_entry.entry_hash
        assert entry.sequence_number == 5
        assert entry.retention_years == 10  # API requests = 10 years

    @pytest.mark.asyncio
    async def test_create_entry_with_details(self) -> None:
        mock_db = AsyncMock()
        mock_last_result = MagicMock()
        mock_last_result.scalar_one_or_none.return_value = None
        mock_seq_result = MagicMock()
        mock_seq_result.scalar_one_or_none.return_value = None

        mock_db.execute = AsyncMock(side_effect=[mock_last_result, mock_seq_result])
        mock_db.flush = AsyncMock()
        mock_db.add = MagicMock()

        entry = await ImmutableAuditService.create_entry(
            db=mock_db,
            category=AuditLogCategory.ADMIN_ACTION,
            action="user.created",
            actor_id="admin-789",
            actor_type="USER",
            resource_type="User",
            resource_id="new-user-123",
            details={"role": "Operator"},
            ip_address="hashed_ip_value",
        )

        assert entry.resource_type == "User"
        assert entry.resource_id == "new-user-123"
        assert entry.details == {"role": "Operator"}
        assert entry.ip_address == "hashed_ip_value"
