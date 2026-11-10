"""Tests for KYC Refresh Service (Phase 15.5)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.subject import KYCStatus, SubjectType
from app.services.kyc_refresh_service import KYCRefreshService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_subject(kyc_status: KYCStatus = KYCStatus.VERIFIED) -> MagicMock:
    """Create a minimal mock Subject for testing."""
    subject = MagicMock()
    subject.subject_id = uuid.uuid4()
    subject.subject_type = SubjectType.INDIVIDUAL
    subject.id_hash = uuid.uuid4().hex + uuid.uuid4().hex
    subject.kyc_status = kyc_status
    return subject


class FakeSession:
    """Minimal async session stub."""

    def __init__(self) -> None:
        self.added: list = []

    def add(self, obj) -> None:  # noqa: ANN001
        self.added.append(obj)


# ---------------------------------------------------------------------------
# Tests: get_subjects_needing_refresh
# ---------------------------------------------------------------------------


class TestGetSubjectsNeedingRefresh:
    @pytest.mark.asyncio
    async def test_returns_empty_when_no_subjects(self) -> None:
        """Test that empty list returned when no subjects need refresh."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = KYCRefreshService()
        subjects = await service.get_subjects_needing_refresh(mock_db)
        assert subjects == []


# ---------------------------------------------------------------------------
# Tests: refresh_subject_kyc
# ---------------------------------------------------------------------------


class TestRefreshSubjectKYC:
    @pytest.mark.asyncio
    async def test_creates_pending_check_record(self) -> None:
        """Test that a pending check record is created on refresh."""
        session = FakeSession()
        subject = _make_subject(kyc_status=KYCStatus.VERIFIED)

        service = KYCRefreshService()
        check = await service.refresh_subject_kyc(
            db=session,  # type: ignore[arg-type]
            subject=subject,
        )

        assert check.provider == "smile_id"
        assert subject.kyc_status == KYCStatus.PENDING
        assert len(session.added) == 1
        assert check.expires_at is not None

    @pytest.mark.asyncio
    async def test_updates_subject_to_pending(self) -> None:
        """Test that subject status is set to PENDING during refresh."""
        session = FakeSession()
        subject = _make_subject(kyc_status=KYCStatus.VERIFIED)

        service = KYCRefreshService()
        await service.refresh_subject_kyc(
            db=session,  # type: ignore[arg-type]
            subject=subject,
        )

        assert subject.kyc_status == KYCStatus.PENDING


# ---------------------------------------------------------------------------
# Tests: run_batch_refresh
# ---------------------------------------------------------------------------


class TestRunBatchRefresh:
    @pytest.mark.asyncio
    async def test_batch_refresh_empty(self) -> None:
        """Test batch refresh with no subjects."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = KYCRefreshService()
        stats = await service.run_batch_refresh(mock_db)

        assert stats["total"] == 0
        assert stats["succeeded"] == 0
        assert stats["failed"] == 0

    @pytest.mark.asyncio
    async def test_batch_refresh_processes_subjects(self) -> None:
        """Test batch refresh processes multiple subjects."""
        subjects = [_make_subject() for _ in range(3)]

        service = KYCRefreshService()

        # Mock get_subjects_needing_refresh
        with patch.object(
            service,
            "get_subjects_needing_refresh",
            new_callable=AsyncMock,
            return_value=subjects,
        ):
            with patch("app.services.kyc_refresh_service.asyncio.sleep", new_callable=AsyncMock):
                session = FakeSession()
                stats = await service.run_batch_refresh(
                    db=session,  # type: ignore[arg-type]
                    rate_limit_per_minute=60,
                )

        assert stats["total"] == 3
        assert stats["succeeded"] == 3
        assert stats["failed"] == 0
        assert len(session.added) == 3

    @pytest.mark.asyncio
    async def test_batch_refresh_handles_failures(self) -> None:
        """Test batch refresh continues on individual failures."""
        subjects = [_make_subject() for _ in range(3)]

        service = KYCRefreshService()

        call_count = 0

        async def mock_refresh(db, subject):  # noqa: ANN001
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("Simulated failure")
            # Create a mock check record
            mock_check = MagicMock()
            mock_check.provider = "smile_id"
            mock_check.expires_at = datetime.now(timezone.utc) + timedelta(days=30)
            db.add(mock_check)
            subject.kyc_status = KYCStatus.PENDING
            return mock_check

        with patch.object(
            service,
            "get_subjects_needing_refresh",
            new_callable=AsyncMock,
            return_value=subjects,
        ):
            with patch.object(service, "refresh_subject_kyc", side_effect=mock_refresh):
                with patch(
                    "app.services.kyc_refresh_service.asyncio.sleep",
                    new_callable=AsyncMock,
                ):
                    session = FakeSession()
                    stats = await service.run_batch_refresh(
                        db=session,  # type: ignore[arg-type]
                        rate_limit_per_minute=60,
                    )

        assert stats["total"] == 3
        assert stats["succeeded"] == 2
        assert stats["failed"] == 1
