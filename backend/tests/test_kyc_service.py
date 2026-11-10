"""Tests for SmileIDClient KYC service (Phase 15.1)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.schemas.kyc import BiometricData, IDType, KYCStatusEnum
from app.services.kyc_service import CircuitBreaker, CircuitBreakerOpen, SmileIDClient


# ---------------------------------------------------------------------------
# Circuit Breaker Tests
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    def test_starts_closed(self) -> None:
        cb = CircuitBreaker(failure_threshold=3)
        assert cb.state == "CLOSED"

    def test_opens_after_threshold(self) -> None:
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == "OPEN"

    def test_resets_on_success(self) -> None:
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.state == "CLOSED"

    def test_check_raises_when_open(self) -> None:
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        with pytest.raises(CircuitBreakerOpen):
            cb.check()

    def test_half_open_after_recovery_timeout(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout_seconds=0.0)
        cb.record_failure()
        # With 0 timeout, immediately transitions to HALF_OPEN
        assert cb.state == "HALF_OPEN"


# ---------------------------------------------------------------------------
# SmileIDClient Tests
# ---------------------------------------------------------------------------


class TestSmileIDClient:
    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        settings = MagicMock()
        settings.smile_id_api_key = "test-api-key"
        settings.smile_id_partner_id = "test-partner-id"
        settings.smile_id_base_url = "https://api.smileidentity.com/v1"
        settings.smile_id_timeout_seconds = 5
        settings.smile_id_max_retries = 2
        return settings

    @pytest.fixture
    def client(self, mock_settings: MagicMock) -> SmileIDClient:
        return SmileIDClient(settings=mock_settings)

    @pytest.mark.asyncio
    async def test_verify_identity_success(self, client: SmileIDClient) -> None:
        """Test successful identity verification."""
        mock_response = httpx.Response(
            200,
            json={
                "ResultCode": "1012",
                "ResultText": "ID Verified",
                "ConfidenceValue": 95.5,
                "Actions": {
                    "Verify_ID_Number": "Verified",
                    "Selfie_Check": "Passed",
                    "Liveness_Check": "Passed",
                },
                "FaceMatchConfidence": 88.0,
            },
            request=httpx.Request("POST", "https://test.com"),
        )

        with patch("app.services.kyc_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.verify_identity(
                national_id="12345678",
                id_type=IDType.NATIONAL_ID,
                country="KE",
            )

        assert result.status == KYCStatusEnum.VERIFIED
        assert result.confidence_score == pytest.approx(0.955)
        assert result.face_match_score == pytest.approx(0.88)
        assert result.liveness_passed is True
        assert result.provider_reference is not None
        assert result.verified_at is not None

    @pytest.mark.asyncio
    async def test_verify_identity_failed(self, client: SmileIDClient) -> None:
        """Test failed identity verification."""
        mock_response = httpx.Response(
            200,
            json={
                "ResultCode": "1015",
                "ResultText": "ID Not Found",
                "ConfidenceValue": 0.0,
                "Actions": {
                    "Verify_ID_Number": "Not Verified",
                },
            },
            request=httpx.Request("POST", "https://test.com"),
        )

        with patch("app.services.kyc_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.verify_identity(
                national_id="99999999",
                id_type=IDType.NATIONAL_ID,
            )

        assert result.status == KYCStatusEnum.FAILED
        assert result.failure_reason is not None
        assert result.verified_at is None

    @pytest.mark.asyncio
    async def test_verify_identity_with_biometric(self, client: SmileIDClient) -> None:
        """Test identity verification with biometric data."""
        mock_response = httpx.Response(
            200,
            json={
                "ResultCode": "1020",
                "ResultText": "Verified",
                "ConfidenceValue": 92.0,
                "Actions": {
                    "Verify_ID_Number": "Verified",
                    "Selfie_Check": "Passed",
                    "Liveness_Check": "Passed",
                },
                "FaceMatchConfidence": 95.0,
            },
            request=httpx.Request("POST", "https://test.com"),
        )

        with patch("app.services.kyc_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            biometric = BiometricData(
                selfie_image_base64="base64encodedimage",
                id_image_base64="base64encodedidimage",
            )
            result = await client.verify_identity(
                national_id="12345678",
                id_type=IDType.PASSPORT,
                biometric_data=biometric,
                first_name="John",
                last_name="Doe",
            )

        assert result.status == KYCStatusEnum.VERIFIED
        assert result.face_match_score == pytest.approx(0.95)
        assert result.liveness_passed is True

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_when_open(
        self, client: SmileIDClient,
    ) -> None:
        """Test that requests are blocked when circuit breaker is open."""
        # Force circuit breaker open
        for _ in range(5):
            client._circuit_breaker.record_failure()

        with pytest.raises(CircuitBreakerOpen):
            await client.verify_identity(national_id="12345678")

    @pytest.mark.asyncio
    async def test_retry_on_server_error(self, client: SmileIDClient) -> None:
        """Test retry logic on 500 errors."""
        error_response = httpx.Response(
            500,
            json={"error": "Internal Server Error"},
            request=httpx.Request("POST", "https://test.com"),
        )
        success_response = httpx.Response(
            200,
            json={
                "ResultCode": "1012",
                "ResultText": "ID Verified",
                "ConfidenceValue": 90.0,
                "Actions": {"Verify_ID_Number": "Verified"},
            },
            request=httpx.Request("POST", "https://test.com"),
        )

        call_count = 0

        async def mock_post(*args, **kwargs):  # noqa: ANN002, ANN003
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                return error_response
            return success_response

        with patch("app.services.kyc_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            with patch("app.services.kyc_service.asyncio.sleep", new_callable=AsyncMock):
                result = await client.verify_identity(national_id="12345678")

        assert result.status == KYCStatusEnum.VERIFIED
        assert call_count == 2

    def test_build_payload_national_id(self, client: SmileIDClient) -> None:
        """Test payload construction for national ID."""
        payload = client._build_payload(
            national_id="12345678",
            id_type=IDType.NATIONAL_ID,
            biometric_data=None,
            first_name="John",
            last_name="Doe",
            country="KE",
            job_id="test-job-id",
        )
        assert payload["id_type"] == "NATIONAL_ID"
        assert payload["country"] == "KE"
        assert payload["first_name"] == "John"
        assert payload["job_type"] == 5  # Enhanced KYC without biometric

    def test_build_payload_with_biometric(self, client: SmileIDClient) -> None:
        """Test payload construction with biometric data."""
        biometric = BiometricData(
            selfie_image_base64="selfie_data",
            id_image_base64="id_data",
        )
        payload = client._build_payload(
            national_id="12345678",
            id_type=IDType.NATIONAL_ID,
            biometric_data=biometric,
            first_name=None,
            last_name=None,
            country="KE",
            job_id="test-job-id",
        )
        assert payload["job_type"] == 1  # Biometric KYC
        assert payload["image"] == "selfie_data"
        assert payload["id_image"] == "id_data"

    def test_map_response_verified(self, client: SmileIDClient) -> None:
        """Test response mapping for verified result."""
        response_data = {
            "ResultCode": "1012",
            "ResultText": "ID Verified",
            "ConfidenceValue": 95.0,
            "Actions": {
                "Verify_ID_Number": "Verified",
                "Liveness_Check": "Passed",
            },
            "FaceMatchConfidence": 88.0,
        }
        result = client._map_response(response_data, "job-123")
        assert result.status == KYCStatusEnum.VERIFIED
        assert result.confidence_score == pytest.approx(0.95)
        assert result.face_match_score == pytest.approx(0.88)
        assert result.liveness_passed is True

    def test_map_response_pending(self, client: SmileIDClient) -> None:
        """Test response mapping for pending result."""
        response_data = {
            "ResultCode": "1013",
            "ResultText": "Pending verification",
            "ConfidenceValue": 0.0,
            "Actions": {},
        }
        result = client._map_response(response_data, "job-456")
        assert result.status == KYCStatusEnum.PENDING

    def test_get_raw_response_for_storage(self, client: SmileIDClient) -> None:
        """Test raw response serialization."""
        response_data = {"key": "value", "nested": {"a": 1}}
        raw = client.get_raw_response_for_storage(response_data)
        assert '"key"' in raw
        assert '"value"' in raw
