"""Tests for Data Subject Rights service and endpoints (Phase 12.5).

Covers:
  - Right of Access — subject data retrieval
  - Right of Rectification — correction request
  - Right to Deletion — anonymization
  - Error handling for invalid requests
  - Schema validation
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.subject import AMLStatus, KYCStatus, Subject, SubjectType
from app.schemas.data_rights import (
    CorrectionRequest,
    CorrectionResponse,
    DeletionResponse,
    FeatureRecord,
    ScoreRecord,
    SubjectDataResponse,
)
from app.services.data_rights_service import (
    CORRECTABLE_FIELDS,
    DataRightsService,
)


def _make_subject(**overrides: object) -> MagicMock:
    """Create a mock Subject."""
    defaults = {
        "subject_id": uuid.uuid4(),
        "subject_type": SubjectType.INDIVIDUAL,
        "id_hash": "a" * 64,
        "kyc_status": KYCStatus.VERIFIED,
        "aml_status": AMLStatus.CLEAR,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    subject = MagicMock(spec=Subject)
    for k, v in defaults.items():
        setattr(subject, k, v)
    return subject


def _mock_db_with_subject(subject: object | None) -> AsyncMock:
    """Return a mock AsyncSession that returns the given subject."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = subject

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.flush = AsyncMock()
    return mock_db


class TestGetSubjectData:
    """Right of Access tests."""

    @pytest.mark.asyncio
    async def test_returns_subject_data(self) -> None:
        subject = _make_subject()
        subject_id = str(subject.subject_id)

        # Setup mock DB to return subject, empty scores, empty features, 0 logs
        mock_db = AsyncMock()
        call_count = 0
        results = []

        # First call: subject lookup
        subject_result = MagicMock()
        subject_result.scalar_one_or_none.return_value = subject
        results.append(subject_result)

        # Second call: scores
        scores_result = MagicMock()
        scores_scalars = MagicMock()
        scores_scalars.all.return_value = []
        scores_result.scalars.return_value = scores_scalars
        results.append(scores_result)

        # Third call: features
        features_result = MagicMock()
        features_scalars = MagicMock()
        features_scalars.all.return_value = []
        features_result.scalars.return_value = features_scalars
        results.append(features_result)

        # Fourth call: log count
        count_result = MagicMock()
        count_result.scalar_one.return_value = 5
        results.append(count_result)

        mock_db.execute = AsyncMock(side_effect=results)

        response = await DataRightsService.get_subject_data(mock_db, subject_id)

        assert isinstance(response, SubjectDataResponse)
        assert response.subject_id == subject_id
        assert response.subject_type == "INDIVIDUAL"
        assert response.kyc_status == "VERIFIED"
        assert response.api_request_count == 5
        assert "identity" in response.data_categories

    @pytest.mark.asyncio
    async def test_subject_not_found_raises(self) -> None:
        mock_db = _mock_db_with_subject(None)

        with pytest.raises(ValueError, match="not found"):
            await DataRightsService.get_subject_data(
                mock_db, str(uuid.uuid4())
            )


class TestRequestCorrection:
    """Right of Rectification tests."""

    @pytest.mark.asyncio
    async def test_valid_correction_request(self) -> None:
        subject = _make_subject()
        subject_id = str(subject.subject_id)

        # Mock: first call returns subject
        mock_db = AsyncMock()
        subject_result = MagicMock()
        subject_result.scalar_one_or_none.return_value = subject
        mock_db.execute = AsyncMock(return_value=subject_result)

        request = CorrectionRequest(
            subject_id=subject_id,
            field_name="kyc_status",
            current_value="PENDING",
            corrected_value="VERIFIED",
            justification="KYC was completed successfully with Smile ID",
        )

        response = await DataRightsService.request_correction(mock_db, request)

        assert isinstance(response, CorrectionResponse)
        assert response.status == "PENDING"
        assert response.field_name == "kyc_status"
        assert "30 days" in response.message

    @pytest.mark.asyncio
    async def test_invalid_field_raises(self) -> None:
        mock_db = AsyncMock()

        request = CorrectionRequest(
            subject_id=str(uuid.uuid4()),
            field_name="invalid_field",
            current_value="old",
            corrected_value="new",
            justification="Testing invalid field correction",
        )

        with pytest.raises(ValueError, match="not eligible for correction"):
            await DataRightsService.request_correction(mock_db, request)

    @pytest.mark.asyncio
    async def test_subject_not_found_raises(self) -> None:
        mock_db = _mock_db_with_subject(None)

        request = CorrectionRequest(
            subject_id=str(uuid.uuid4()),
            field_name="kyc_status",
            current_value="PENDING",
            corrected_value="VERIFIED",
            justification="Testing subject not found scenario",
        )

        with pytest.raises(ValueError, match="not found"):
            await DataRightsService.request_correction(mock_db, request)


class TestRequestDeletion:
    """Right to Erasure (anonymization) tests."""

    @pytest.mark.asyncio
    async def test_successful_anonymization(self) -> None:
        subject = _make_subject()
        subject_id = str(subject.subject_id)
        original_hash = subject.id_hash

        mock_db = _mock_db_with_subject(subject)

        response = await DataRightsService.request_deletion(mock_db, subject_id)

        assert isinstance(response, DeletionResponse)
        assert response.status == "COMPLETED"
        assert "anonymized" in response.message.lower()
        assert len(response.anonymized_fields) > 0
        assert len(response.retained_fields) > 0
        # id_hash should have been changed
        assert subject.id_hash != original_hash

    @pytest.mark.asyncio
    async def test_subject_not_found_raises(self) -> None:
        mock_db = _mock_db_with_subject(None)

        with pytest.raises(ValueError, match="not found"):
            await DataRightsService.request_deletion(
                mock_db, str(uuid.uuid4())
            )


class TestCorrectableFields:
    """Correctable fields configuration tests."""

    def test_correctable_fields_exist(self) -> None:
        assert "kyc_status" in CORRECTABLE_FIELDS
        assert "aml_status" in CORRECTABLE_FIELDS
        assert "subject_type" in CORRECTABLE_FIELDS

    def test_sensitive_fields_not_correctable(self) -> None:
        assert "id_hash" not in CORRECTABLE_FIELDS
        assert "subject_id" not in CORRECTABLE_FIELDS


class TestSchemas:
    """Schema validation tests."""

    def test_correction_request_validation(self) -> None:
        req = CorrectionRequest(
            subject_id=str(uuid.uuid4()),
            field_name="kyc_status",
            current_value="PENDING",
            corrected_value="VERIFIED",
            justification="Valid justification text here",
        )
        assert req.field_name == "kyc_status"

    def test_correction_request_short_justification_fails(self) -> None:
        with pytest.raises(Exception):  # Pydantic validation error
            CorrectionRequest(
                subject_id=str(uuid.uuid4()),
                field_name="kyc_status",
                current_value="PENDING",
                corrected_value="VERIFIED",
                justification="short",  # Less than 10 chars
            )

    def test_score_record_schema(self) -> None:
        record = ScoreRecord(
            score_id=str(uuid.uuid4()),
            vyce_score=750,
            niq_score=85,
            score_date="2026-01-01",
            model_version="v1.0.0",
        )
        assert record.vyce_score == 750

    def test_feature_record_schema(self) -> None:
        record = FeatureRecord(
            feature_name="CBLRI",
            feature_value="0.85",
            feature_date="2026-01-01",
            feature_category="TRANSACTION",
        )
        assert record.feature_name == "CBLRI"
