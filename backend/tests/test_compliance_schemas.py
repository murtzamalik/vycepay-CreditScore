"""Tests for KYC and AML Pydantic schemas (Phase 15)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.aml import (
    AMLMatchDetail,
    AMLResult,
    AMLRiskRating,
    AMLScreeningRequest,
    AMLScreeningResponse,
    AMLStatusEnum,
    AMLStatusResponse,
)
from app.schemas.kyc import (
    BiometricData,
    IDType,
    KYCResult,
    KYCStatusEnum,
    KYCStatusResponse,
    KYCVerificationRequest,
    KYCVerificationResponse,
)


# ---------------------------------------------------------------------------
# KYC Schema Tests
# ---------------------------------------------------------------------------


class TestKYCVerificationRequest:
    def test_valid_minimal(self) -> None:
        req = KYCVerificationRequest(national_id="12345678")
        assert req.national_id == "12345678"
        assert req.id_type == IDType.NATIONAL_ID
        assert req.country == "KE"
        assert req.biometric_data is None

    def test_valid_full(self) -> None:
        req = KYCVerificationRequest(
            national_id="12345678",
            id_type=IDType.PASSPORT,
            biometric_data=BiometricData(
                selfie_image_base64="abc123",
                id_image_base64="def456",
            ),
            first_name="John",
            last_name="Doe",
            country="KE",
        )
        assert req.id_type == IDType.PASSPORT
        assert req.biometric_data is not None
        assert req.first_name == "John"

    def test_empty_national_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            KYCVerificationRequest(national_id="")

    def test_invalid_country_code(self) -> None:
        with pytest.raises(ValidationError):
            KYCVerificationRequest(national_id="123", country="KENYA")


class TestKYCResult:
    def test_valid(self) -> None:
        result = KYCResult(
            status=KYCStatusEnum.VERIFIED,
            confidence_score=0.95,
            face_match_score=0.88,
            liveness_passed=True,
            provider_reference="job-123",
            verified_at=datetime.now(timezone.utc),
        )
        assert result.status == KYCStatusEnum.VERIFIED
        assert result.confidence_score == 0.95

    def test_confidence_score_bounds(self) -> None:
        with pytest.raises(ValidationError):
            KYCResult(
                status=KYCStatusEnum.VERIFIED,
                confidence_score=1.5,
                provider_reference="job-123",
            )

        with pytest.raises(ValidationError):
            KYCResult(
                status=KYCStatusEnum.VERIFIED,
                confidence_score=-0.1,
                provider_reference="job-123",
            )


class TestKYCVerificationResponse:
    def test_valid(self) -> None:
        resp = KYCVerificationResponse(
            subject_id="a" * 64,
            status=KYCStatusEnum.VERIFIED,
            confidence_score=0.9,
            provider_reference="job-123",
        )
        assert resp.subject_id == "a" * 64


class TestKYCStatusResponse:
    def test_valid(self) -> None:
        resp = KYCStatusResponse(
            subject_id="a" * 64,
            kyc_status=KYCStatusEnum.VERIFIED,
        )
        assert resp.kyc_status == KYCStatusEnum.VERIFIED


# ---------------------------------------------------------------------------
# AML Schema Tests
# ---------------------------------------------------------------------------


class TestAMLScreeningRequest:
    def test_valid_minimal(self) -> None:
        req = AMLScreeningRequest(name="John Doe", national_id="12345678")
        assert req.name == "John Doe"
        assert req.nationality == "KE"
        assert req.date_of_birth is None

    def test_valid_full(self) -> None:
        req = AMLScreeningRequest(
            name="John Doe",
            national_id="12345678",
            date_of_birth="1990-01-15",
            nationality="KE",
        )
        assert req.date_of_birth == "1990-01-15"

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AMLScreeningRequest(name="", national_id="123")


class TestAMLResult:
    def test_valid_clear(self) -> None:
        result = AMLResult(
            status=AMLStatusEnum.CLEAR,
            risk_rating=AMLRiskRating.LOW,
            risk_score=0.0,
            provider_reference="search-123",
        )
        assert result.status == AMLStatusEnum.CLEAR
        assert result.is_sanctioned is False
        assert result.is_pep is False

    def test_valid_with_matches(self) -> None:
        result = AMLResult(
            status=AMLStatusEnum.FLAGGED,
            risk_rating=AMLRiskRating.HIGH,
            risk_score=1.0,
            is_sanctioned=True,
            matches=[
                AMLMatchDetail(
                    list_name="UN Sanctions",
                    match_score=0.95,
                    match_type="sanctions",
                ),
            ],
            provider_reference="search-456",
        )
        assert len(result.matches) == 1
        assert result.matches[0].match_type == "sanctions"

    def test_risk_score_bounds(self) -> None:
        with pytest.raises(ValidationError):
            AMLResult(
                status=AMLStatusEnum.CLEAR,
                risk_rating=AMLRiskRating.LOW,
                risk_score=1.5,
                provider_reference="search-123",
            )


class TestAMLScreeningResponse:
    def test_valid(self) -> None:
        resp = AMLScreeningResponse(
            subject_id="a" * 64,
            status=AMLStatusEnum.CLEAR,
            risk_rating=AMLRiskRating.LOW,
            risk_score=0.0,
            is_sanctioned=False,
            is_pep=False,
            adverse_media_found=False,
            match_count=0,
            provider_reference="search-123",
        )
        assert resp.match_count == 0


class TestAMLStatusResponse:
    def test_valid(self) -> None:
        resp = AMLStatusResponse(
            subject_id="a" * 64,
            aml_status=AMLStatusEnum.CLEAR,
        )
        assert resp.aml_status == AMLStatusEnum.CLEAR
