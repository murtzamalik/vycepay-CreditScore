"""Tests for ComplyAdvantageClient AML service (Phase 15.2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.schemas.aml import AMLRiskRating, AMLStatusEnum
from app.services.aml_service import CircuitBreaker, CircuitBreakerOpen, ComplyAdvantageClient


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

    def test_check_raises_when_open(self) -> None:
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        with pytest.raises(CircuitBreakerOpen):
            cb.check()


# ---------------------------------------------------------------------------
# ComplyAdvantageClient Tests
# ---------------------------------------------------------------------------


class TestComplyAdvantageClient:
    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        settings = MagicMock()
        settings.comply_advantage_api_key = "test-api-key"
        settings.comply_advantage_base_url = "https://api.complyadvantage.com"
        settings.comply_advantage_timeout_seconds = 5
        settings.comply_advantage_max_retries = 2
        return settings

    @pytest.fixture
    def client(self, mock_settings: MagicMock) -> ComplyAdvantageClient:
        return ComplyAdvantageClient(settings=mock_settings)

    @pytest.mark.asyncio
    async def test_screen_individual_clear(self, client: ComplyAdvantageClient) -> None:
        """Test AML screening with no hits (clear result)."""
        mock_response = httpx.Response(
            200,
            json={
                "content": {
                    "data": {
                        "hits": [],
                        "total_hits": 0,
                    }
                }
            },
            request=httpx.Request("POST", "https://test.com"),
        )

        with patch("app.services.aml_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.screen_individual(
                name="John Doe",
                national_id="12345678",
                nationality="KE",
            )

        assert result.status == AMLStatusEnum.CLEAR
        assert result.risk_rating == AMLRiskRating.LOW
        assert result.risk_score == pytest.approx(0.0)
        assert result.is_sanctioned is False
        assert result.is_pep is False
        assert result.adverse_media_found is False
        assert len(result.matches) == 0

    @pytest.mark.asyncio
    async def test_screen_individual_sanctioned(
        self, client: ComplyAdvantageClient,
    ) -> None:
        """Test AML screening with sanctions hit."""
        mock_response = httpx.Response(
            200,
            json={
                "content": {
                    "data": {
                        "hits": [
                            {
                                "types": ["sanction"],
                                "match_score": 95.0,
                                "doc": {"name": "UN Sanctions List"},
                            }
                        ],
                        "total_hits": 1,
                    }
                }
            },
            request=httpx.Request("POST", "https://test.com"),
        )

        with patch("app.services.aml_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.screen_individual(
                name="John Doe",
                national_id="12345678",
            )

        assert result.status == AMLStatusEnum.FLAGGED
        assert result.risk_rating == AMLRiskRating.HIGH
        assert result.risk_score == pytest.approx(1.0)
        assert result.is_sanctioned is True
        assert len(result.matches) == 1
        assert result.matches[0].match_type == "sanctions"

    @pytest.mark.asyncio
    async def test_screen_individual_pep(
        self, client: ComplyAdvantageClient,
    ) -> None:
        """Test AML screening with PEP hit."""
        mock_response = httpx.Response(
            200,
            json={
                "content": {
                    "data": {
                        "hits": [
                            {
                                "types": ["pep"],
                                "match_score": 80.0,
                                "doc": {"name": "PEP Database"},
                            }
                        ],
                        "total_hits": 1,
                    }
                }
            },
            request=httpx.Request("POST", "https://test.com"),
        )

        with patch("app.services.aml_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.screen_individual(
                name="Jane Doe",
                national_id="87654321",
                date_of_birth="1990-01-15",
            )

        assert result.status == AMLStatusEnum.REVIEW
        assert result.is_pep is True
        assert result.is_sanctioned is False
        assert len(result.matches) == 1
        assert result.matches[0].match_type == "pep"

    @pytest.mark.asyncio
    async def test_screen_individual_adverse_media(
        self, client: ComplyAdvantageClient,
    ) -> None:
        """Test AML screening with adverse media hit."""
        mock_response = httpx.Response(
            200,
            json={
                "content": {
                    "data": {
                        "hits": [
                            {
                                "types": ["adverse-media"],
                                "match_score": 60.0,
                                "doc": {"name": "Media Source"},
                            }
                        ],
                        "total_hits": 1,
                    }
                }
            },
            request=httpx.Request("POST", "https://test.com"),
        )

        with patch("app.services.aml_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.screen_individual(
                name="John Doe",
                national_id="12345678",
            )

        assert result.adverse_media_found is True
        assert len(result.matches) == 1
        assert result.matches[0].match_type == "adverse_media"

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_when_open(
        self, client: ComplyAdvantageClient,
    ) -> None:
        """Test that requests are blocked when circuit breaker is open."""
        for _ in range(5):
            client._circuit_breaker.record_failure()

        with pytest.raises(CircuitBreakerOpen):
            await client.screen_individual(
                name="Test",
                national_id="12345678",
            )

    @pytest.mark.asyncio
    async def test_retry_on_server_error(
        self, client: ComplyAdvantageClient,
    ) -> None:
        """Test retry logic on 500 errors."""
        error_response = httpx.Response(
            500,
            json={"error": "Internal Server Error"},
            request=httpx.Request("POST", "https://test.com"),
        )
        success_response = httpx.Response(
            200,
            json={
                "content": {"data": {"hits": [], "total_hits": 0}}
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

        with patch("app.services.aml_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            with patch("app.services.aml_service.asyncio.sleep", new_callable=AsyncMock):
                result = await client.screen_individual(
                    name="John Doe",
                    national_id="12345678",
                )

        assert result.status == AMLStatusEnum.CLEAR
        assert call_count == 2

    def test_calculate_risk_sanctioned(self) -> None:
        """Test risk calculation for sanctioned entity."""
        rating, score = ComplyAdvantageClient._calculate_risk(
            total_hits=1, is_sanctioned=True, is_pep=False,
            adverse_media_found=False,
        )
        assert rating == AMLRiskRating.HIGH
        assert score == pytest.approx(1.0)

    def test_calculate_risk_pep(self) -> None:
        """Test risk calculation for PEP."""
        rating, score = ComplyAdvantageClient._calculate_risk(
            total_hits=1, is_sanctioned=False, is_pep=True,
            adverse_media_found=False,
        )
        assert rating == AMLRiskRating.HIGH
        assert score >= 0.6

    def test_calculate_risk_clear(self) -> None:
        """Test risk calculation with no hits."""
        rating, score = ComplyAdvantageClient._calculate_risk(
            total_hits=0, is_sanctioned=False, is_pep=False,
            adverse_media_found=False,
        )
        assert rating == AMLRiskRating.LOW
        assert score == pytest.approx(0.0)

    def test_calculate_risk_adverse_media_only(self) -> None:
        """Test risk calculation with adverse media only."""
        rating, score = ComplyAdvantageClient._calculate_risk(
            total_hits=1, is_sanctioned=False, is_pep=False,
            adverse_media_found=True,
        )
        assert rating == AMLRiskRating.LOW  # 0.2 is below MEDIUM threshold
        assert score > 0.0

    def test_determine_status_sanctioned(self) -> None:
        """Test status determination for sanctioned entity."""
        status = ComplyAdvantageClient._determine_status(
            is_sanctioned=True, is_pep=False, risk_rating=AMLRiskRating.HIGH,
        )
        assert status == AMLStatusEnum.FLAGGED

    def test_determine_status_pep(self) -> None:
        """Test status determination for PEP."""
        status = ComplyAdvantageClient._determine_status(
            is_sanctioned=False, is_pep=True, risk_rating=AMLRiskRating.HIGH,
        )
        assert status == AMLStatusEnum.REVIEW

    def test_determine_status_clear(self) -> None:
        """Test status determination for clear entity."""
        status = ComplyAdvantageClient._determine_status(
            is_sanctioned=False, is_pep=False, risk_rating=AMLRiskRating.LOW,
        )
        assert status == AMLStatusEnum.CLEAR

    def test_build_payload(self, client: ComplyAdvantageClient) -> None:
        """Test payload construction."""
        payload = client._build_payload(
            name="John Doe",
            date_of_birth="1990-05-15",
            nationality="KE",
            search_ref="ref-123",
        )
        assert payload["search_term"] == "John Doe"
        assert payload["client_ref"] == "ref-123"
        assert payload["filters"]["country_codes"] == ["KE"]
        assert payload["filters"]["birth_year"] == 1990

    def test_build_payload_no_dob(self, client: ComplyAdvantageClient) -> None:
        """Test payload construction without date of birth."""
        payload = client._build_payload(
            name="John Doe",
            date_of_birth=None,
            nationality="KE",
            search_ref="ref-123",
        )
        assert payload["filters"]["birth_year"] is None

    def test_get_raw_response_for_storage(
        self, client: ComplyAdvantageClient,
    ) -> None:
        """Test raw response serialization."""
        response_data = {"key": "value"}
        raw = client.get_raw_response_for_storage(response_data)
        assert '"key"' in raw
