"""Tests for ComplianceService orchestration (Phase 15.3)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.compliance_check import ComplianceCheckStatus, ComplianceCheckType
from app.models.subject import AMLStatus, KYCStatus, SubjectType
from app.schemas.aml import AMLResult, AMLRiskRating, AMLStatusEnum
from app.schemas.kyc import IDType, KYCResult, KYCStatusEnum
from app.services.compliance_service import ComplianceService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeSession:
    """Minimal async session stub that captures ``.add()`` calls."""

    def __init__(self) -> None:
        self.added: list = []

    def add(self, obj) -> None:  # noqa: ANN001
        self.added.append(obj)


def _make_subject() -> MagicMock:
    """Create a minimal mock Subject for testing."""
    subject = MagicMock()
    subject.subject_id = uuid.uuid4()
    subject.subject_type = SubjectType.INDIVIDUAL
    subject.id_hash = "a" * 64
    subject.kyc_status = KYCStatus.PENDING
    subject.aml_status = AMLStatus.CLEAR
    return subject


def _make_kyc_result(status: KYCStatusEnum = KYCStatusEnum.VERIFIED) -> KYCResult:
    """Create a mock KYC result."""
    return KYCResult(
        status=status,
        confidence_score=0.95,
        face_match_score=0.88,
        liveness_passed=True,
        provider_reference="job-123",
        verified_at=datetime.now(timezone.utc) if status == KYCStatusEnum.VERIFIED else None,
    )


def _make_aml_result(status: AMLStatusEnum = AMLStatusEnum.CLEAR) -> AMLResult:
    """Create a mock AML result."""
    return AMLResult(
        status=status,
        risk_rating=AMLRiskRating.LOW,
        risk_score=0.0,
        is_sanctioned=False,
        is_pep=False,
        adverse_media_found=False,
        matches=[],
        provider_reference="search-123",
        screened_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Tests: KYC Check
# ---------------------------------------------------------------------------


class TestComplianceServiceKYC:
    @pytest.mark.asyncio
    async def test_run_kyc_check_verified(self) -> None:
        """Test successful KYC check updates subject and stores record."""
        session = FakeSession()
        subject = _make_subject()
        kyc_result = _make_kyc_result(KYCStatusEnum.VERIFIED)

        mock_kyc_client = MagicMock()
        mock_kyc_client.verify_identity = AsyncMock(return_value=kyc_result)

        service = ComplianceService(kyc_client=mock_kyc_client)
        result = await service.run_kyc_check(
            db=session,  # type: ignore[arg-type]
            subject=subject,
            national_id="12345678",
        )

        assert result.status == KYCStatusEnum.VERIFIED
        assert subject.kyc_status == KYCStatus.VERIFIED
        assert len(session.added) == 1
        check = session.added[0]
        assert check.check_type == ComplianceCheckType.KYC
        assert check.status == ComplianceCheckStatus.PASSED
        assert check.provider == "smile_id"

    @pytest.mark.asyncio
    async def test_run_kyc_check_failed(self) -> None:
        """Test failed KYC check updates subject status."""
        session = FakeSession()
        subject = _make_subject()
        kyc_result = _make_kyc_result(KYCStatusEnum.FAILED)

        mock_kyc_client = MagicMock()
        mock_kyc_client.verify_identity = AsyncMock(return_value=kyc_result)

        service = ComplianceService(kyc_client=mock_kyc_client)
        result = await service.run_kyc_check(
            db=session,  # type: ignore[arg-type]
            subject=subject,
            national_id="12345678",
        )

        assert result.status == KYCStatusEnum.FAILED
        assert subject.kyc_status == KYCStatus.FAILED
        assert session.added[0].status == ComplianceCheckStatus.FAILED

    @pytest.mark.asyncio
    async def test_run_kyc_check_exception_stores_failed_record(self) -> None:
        """Test KYC check exception still stores a failed record for audit."""
        session = FakeSession()
        subject = _make_subject()

        mock_kyc_client = MagicMock()
        mock_kyc_client.verify_identity = AsyncMock(side_effect=Exception("API error"))

        service = ComplianceService(kyc_client=mock_kyc_client)

        with pytest.raises(Exception, match="API error"):
            await service.run_kyc_check(
                db=session,  # type: ignore[arg-type]
                subject=subject,
                national_id="12345678",
            )

        # Audit record should still be created
        assert len(session.added) == 1
        check = session.added[0]
        assert check.check_type == ComplianceCheckType.KYC
        assert check.status == ComplianceCheckStatus.FAILED


# ---------------------------------------------------------------------------
# Tests: AML Check
# ---------------------------------------------------------------------------


class TestComplianceServiceAML:
    @pytest.mark.asyncio
    async def test_run_aml_check_clear(self) -> None:
        """Test successful AML check with clear result."""
        session = FakeSession()
        subject = _make_subject()
        aml_result = _make_aml_result(AMLStatusEnum.CLEAR)

        mock_aml_client = MagicMock()
        mock_aml_client.screen_individual = AsyncMock(return_value=aml_result)

        service = ComplianceService(aml_client=mock_aml_client)
        result = await service.run_aml_check(
            db=session,  # type: ignore[arg-type]
            subject=subject,
            name="John Doe",
            national_id="12345678",
        )

        assert result.status == AMLStatusEnum.CLEAR
        assert subject.aml_status == AMLStatus.CLEAR
        assert len(session.added) == 1
        check = session.added[0]
        assert check.check_type == ComplianceCheckType.AML
        assert check.status == ComplianceCheckStatus.PASSED
        assert check.provider == "comply_advantage"

    @pytest.mark.asyncio
    async def test_run_aml_check_flagged(self) -> None:
        """Test AML check with flagged result."""
        session = FakeSession()
        subject = _make_subject()
        aml_result = AMLResult(
            status=AMLStatusEnum.FLAGGED,
            risk_rating=AMLRiskRating.HIGH,
            risk_score=1.0,
            is_sanctioned=True,
            is_pep=False,
            adverse_media_found=False,
            matches=[],
            provider_reference="search-456",
            screened_at=datetime.now(timezone.utc),
        )

        mock_aml_client = MagicMock()
        mock_aml_client.screen_individual = AsyncMock(return_value=aml_result)

        service = ComplianceService(aml_client=mock_aml_client)
        result = await service.run_aml_check(
            db=session,  # type: ignore[arg-type]
            subject=subject,
            name="John Doe",
            national_id="12345678",
        )

        assert result.status == AMLStatusEnum.FLAGGED
        assert subject.aml_status == AMLStatus.FLAGGED
        assert session.added[0].status == ComplianceCheckStatus.FAILED

    @pytest.mark.asyncio
    async def test_run_aml_check_exception_stores_failed_record(self) -> None:
        """Test AML check exception still stores a failed record."""
        session = FakeSession()
        subject = _make_subject()

        mock_aml_client = MagicMock()
        mock_aml_client.screen_individual = AsyncMock(
            side_effect=Exception("API error"),
        )

        service = ComplianceService(aml_client=mock_aml_client)

        with pytest.raises(Exception, match="API error"):
            await service.run_aml_check(
                db=session,  # type: ignore[arg-type]
                subject=subject,
                name="John Doe",
                national_id="12345678",
            )

        assert len(session.added) == 1
        assert session.added[0].status == ComplianceCheckStatus.FAILED


# ---------------------------------------------------------------------------
# Tests: Full Compliance Check
# ---------------------------------------------------------------------------


class TestFullComplianceCheck:
    @pytest.mark.asyncio
    async def test_run_full_compliance_check_both_pass(self) -> None:
        """Test full compliance check when both KYC and AML pass."""
        session = FakeSession()
        subject = _make_subject()

        kyc_result = _make_kyc_result(KYCStatusEnum.VERIFIED)
        aml_result = _make_aml_result(AMLStatusEnum.CLEAR)

        mock_kyc_client = MagicMock()
        mock_kyc_client.verify_identity = AsyncMock(return_value=kyc_result)
        mock_aml_client = MagicMock()
        mock_aml_client.screen_individual = AsyncMock(return_value=aml_result)

        service = ComplianceService(
            kyc_client=mock_kyc_client,
            aml_client=mock_aml_client,
        )
        results = await service.run_full_compliance_check(
            db=session,  # type: ignore[arg-type]
            subject=subject,
            national_id="12345678",
            name="John Doe",
        )

        assert results["kyc"] is not None
        assert results["aml"] is not None
        assert results["kyc_error"] is None
        assert results["aml_error"] is None
        assert subject.kyc_status == KYCStatus.VERIFIED
        assert subject.aml_status == AMLStatus.CLEAR
        assert len(session.added) == 2  # One KYC check + one AML check

    @pytest.mark.asyncio
    async def test_run_full_compliance_check_kyc_fails_aml_continues(self) -> None:
        """Test that AML check still runs even if KYC fails."""
        session = FakeSession()
        subject = _make_subject()

        aml_result = _make_aml_result(AMLStatusEnum.CLEAR)

        mock_kyc_client = MagicMock()
        mock_kyc_client.verify_identity = AsyncMock(
            side_effect=Exception("KYC API down"),
        )
        mock_aml_client = MagicMock()
        mock_aml_client.screen_individual = AsyncMock(return_value=aml_result)

        service = ComplianceService(
            kyc_client=mock_kyc_client,
            aml_client=mock_aml_client,
        )
        results = await service.run_full_compliance_check(
            db=session,  # type: ignore[arg-type]
            subject=subject,
            national_id="12345678",
            name="John Doe",
        )

        assert results["kyc"] is None
        assert results["kyc_error"] is not None
        assert results["aml"] is not None
        assert results["aml_error"] is None
        # AML still succeeded
        assert subject.aml_status == AMLStatus.CLEAR
