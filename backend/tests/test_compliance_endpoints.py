"""Tests for KYC and AML API endpoints (Phase 15.1, 15.2)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.subject import AMLStatus, KYCStatus, SubjectType
from app.schemas.aml import AMLResult, AMLRiskRating, AMLStatusEnum
from app.schemas.kyc import KYCResult, KYCStatusEnum


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_subject(
    subject_id: uuid.UUID | None = None,
    kyc_status: KYCStatus = KYCStatus.PENDING,
    aml_status: AMLStatus = AMLStatus.CLEAR,
) -> MagicMock:
    """Create a mock Subject entity for testing."""
    subject = MagicMock()
    subject.subject_id = subject_id or uuid.uuid4()
    subject.subject_type = SubjectType.INDIVIDUAL
    subject.id_hash = "a" * 64
    subject.kyc_status = kyc_status
    subject.aml_status = aml_status
    return subject


# ---------------------------------------------------------------------------
# KYC Endpoint Tests
# ---------------------------------------------------------------------------


class TestKYCVerifyEndpoint:
    @pytest.mark.asyncio
    async def test_verify_kyc_success(self) -> None:
        """Test POST /v1/compliance/kyc/verify returns verification result."""
        subject = _make_subject()
        kyc_result = KYCResult(
            status=KYCStatusEnum.VERIFIED,
            confidence_score=0.95,
            face_match_score=0.88,
            liveness_passed=True,
            provider_reference="job-123",
            verified_at=datetime.now(timezone.utc),
        )

        mock_db_result = MagicMock()
        mock_db_result.scalar_one_or_none.return_value = subject

        # Patch the database dependency and compliance service
        with patch(
            "app.api.v1.endpoints.kyc.ComplianceService"
        ) as mock_service_cls:
            mock_service = MagicMock()
            mock_service.run_kyc_check = AsyncMock(return_value=kyc_result)
            mock_service_cls.return_value = mock_service

            async def mock_get_db():  # noqa: ANN202
                mock_session = AsyncMock()
                mock_session.execute = AsyncMock(return_value=mock_db_result)
                mock_session.commit = AsyncMock()
                yield mock_session

            app.dependency_overrides[
                __import__("app.database", fromlist=["get_db"]).get_db
            ] = mock_get_db

            try:
                transport = ASGITransport(app=app)
                async with AsyncClient(
                    transport=transport, base_url="http://test",
                ) as client:
                    response = await client.post(
                        "/v1/compliance/kyc/verify",
                        json={
                            "national_id": "12345678",
                            "id_type": "NATIONAL_ID",
                        },
                    )

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "VERIFIED"
                assert data["confidence_score"] == pytest.approx(0.95)
                assert data["provider_reference"] == "job-123"
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_verify_kyc_subject_not_found(self) -> None:
        """Test POST /v1/compliance/kyc/verify with unknown subject."""
        mock_db_result = MagicMock()
        mock_db_result.scalar_one_or_none.return_value = None

        async def mock_get_db():  # noqa: ANN202
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(return_value=mock_db_result)
            mock_session.commit = AsyncMock()
            yield mock_session

        app.dependency_overrides[
            __import__("app.database", fromlist=["get_db"]).get_db
        ] = mock_get_db

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test",
            ) as client:
                response = await client.post(
                    "/v1/compliance/kyc/verify",
                    json={"national_id": "99999999"},
                )

            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()


class TestKYCStatusEndpoint:
    @pytest.mark.asyncio
    async def test_get_kyc_status(self) -> None:
        """Test GET /v1/compliance/kyc/status/{subjectId}."""
        subject = _make_subject(kyc_status=KYCStatus.VERIFIED)

        mock_db_result = MagicMock()
        mock_db_result.scalar_one_or_none.return_value = subject

        with patch(
            "app.api.v1.endpoints.kyc.ComplianceService"
        ) as mock_service_cls:
            mock_service = MagicMock()
            mock_service.get_latest_kyc_check = AsyncMock(return_value=None)
            mock_service_cls.return_value = mock_service

            async def mock_get_db():  # noqa: ANN202
                mock_session = AsyncMock()
                mock_session.execute = AsyncMock(return_value=mock_db_result)
                mock_session.commit = AsyncMock()
                yield mock_session

            app.dependency_overrides[
                __import__("app.database", fromlist=["get_db"]).get_db
            ] = mock_get_db

            try:
                transport = ASGITransport(app=app)
                async with AsyncClient(
                    transport=transport, base_url="http://test",
                ) as client:
                    response = await client.get(
                        f"/v1/compliance/kyc/status/{subject.subject_id}",
                    )

                assert response.status_code == 200
                data = response.json()
                assert data["kyc_status"] == "VERIFIED"
            finally:
                app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# AML Endpoint Tests
# ---------------------------------------------------------------------------


class TestAMLScreenEndpoint:
    @pytest.mark.asyncio
    async def test_screen_aml_success(self) -> None:
        """Test POST /v1/compliance/aml/screen returns screening result."""
        subject = _make_subject()
        aml_result = AMLResult(
            status=AMLStatusEnum.CLEAR,
            risk_rating=AMLRiskRating.LOW,
            risk_score=0.0,
            is_sanctioned=False,
            is_pep=False,
            adverse_media_found=False,
            matches=[],
            provider_reference="search-123",
            screened_at=datetime.now(timezone.utc),
        )

        mock_db_result = MagicMock()
        mock_db_result.scalar_one_or_none.return_value = subject

        with patch(
            "app.api.v1.endpoints.aml.ComplianceService"
        ) as mock_service_cls:
            mock_service = MagicMock()
            mock_service.run_aml_check = AsyncMock(return_value=aml_result)
            mock_service_cls.return_value = mock_service

            async def mock_get_db():  # noqa: ANN202
                mock_session = AsyncMock()
                mock_session.execute = AsyncMock(return_value=mock_db_result)
                mock_session.commit = AsyncMock()
                yield mock_session

            app.dependency_overrides[
                __import__("app.database", fromlist=["get_db"]).get_db
            ] = mock_get_db

            try:
                transport = ASGITransport(app=app)
                async with AsyncClient(
                    transport=transport, base_url="http://test",
                ) as client:
                    response = await client.post(
                        "/v1/compliance/aml/screen",
                        json={
                            "name": "John Doe",
                            "national_id": "12345678",
                            "nationality": "KE",
                        },
                    )

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "CLEAR"
                assert data["risk_rating"] == "LOW"
                assert data["is_sanctioned"] is False
                assert data["match_count"] == 0
            finally:
                app.dependency_overrides.clear()


class TestAMLStatusEndpoint:
    @pytest.mark.asyncio
    async def test_get_aml_status(self) -> None:
        """Test GET /v1/compliance/aml/status/{subjectId}."""
        subject = _make_subject(aml_status=AMLStatus.CLEAR)

        mock_db_result = MagicMock()
        mock_db_result.scalar_one_or_none.return_value = subject

        with patch(
            "app.api.v1.endpoints.aml.ComplianceService"
        ) as mock_service_cls:
            mock_service = MagicMock()
            mock_service.get_latest_aml_check = AsyncMock(return_value=None)
            mock_service_cls.return_value = mock_service

            async def mock_get_db():  # noqa: ANN202
                mock_session = AsyncMock()
                mock_session.execute = AsyncMock(return_value=mock_db_result)
                mock_session.commit = AsyncMock()
                yield mock_session

            app.dependency_overrides[
                __import__("app.database", fromlist=["get_db"]).get_db
            ] = mock_get_db

            try:
                transport = ASGITransport(app=app)
                async with AsyncClient(
                    transport=transport, base_url="http://test",
                ) as client:
                    response = await client.get(
                        f"/v1/compliance/aml/status/{subject.subject_id}",
                    )

                assert response.status_code == 200
                data = response.json()
                assert data["aml_status"] == "CLEAR"
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_aml_status_not_found(self) -> None:
        """Test GET /v1/compliance/aml/status with unknown subject."""
        mock_db_result = MagicMock()
        mock_db_result.scalar_one_or_none.return_value = None

        async def mock_get_db():  # noqa: ANN202
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(return_value=mock_db_result)
            mock_session.commit = AsyncMock()
            yield mock_session

        app.dependency_overrides[
            __import__("app.database", fromlist=["get_db"]).get_db
        ] = mock_get_db

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test",
            ) as client:
                response = await client.get(
                    f"/v1/compliance/aml/status/{uuid.uuid4()}",
                )

            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()
