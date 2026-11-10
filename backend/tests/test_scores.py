"""Tests for scoring endpoints and services (Phase 3).

Covers:
  - Score interpretation for all BRD §4.3 ranges
  - National ID hashing (consistent, case-insensitive)
  - Cache service (get/set/invalidate)
  - Lite endpoint correct schema
  - Pro endpoint requires Pro/DeepDive tier
  - Pro endpoint with includeHistory parameter
  - 404 for unknown subjects
  - Error response format
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.customer import Customer, CustomerStatus, LicenseTier
from app.models.risk_driver import ImpactDirection, RiskDriver
from app.models.score import Score
from app.models.subject import Subject, SubjectType, KYCStatus, AMLStatus
from app.schemas.scores import (
    ConfidenceInterval,
    RiskDriverResponse,
    ScoreInterpretation,
    ScoreLiteResponse,
    ScoreMetadata,
    ScoreProResponse,
    ScoreProWithHistoryResponse,
)
from app.services.id_hasher import hash_national_id
from app.services.score_cache import ScoreCacheService
from app.services.score_interpretation import interpret_score
from app.services.scoring import ScoringService


# =========================================================================
# 1. Score interpretation (BRD §4.3)
# =========================================================================


class TestScoreInterpretation:
    """Verify interpret_score returns correct risk levels for all ranges."""

    def test_very_low_risk_800(self) -> None:
        result = interpret_score(800)
        assert result.risk_level == "Very Low Risk"
        assert result.interpretation == "Excellent creditworthiness"

    def test_very_low_risk_900(self) -> None:
        result = interpret_score(900)
        assert result.risk_level == "Very Low Risk"
        assert result.interpretation == "Excellent creditworthiness"

    def test_very_low_risk_850(self) -> None:
        result = interpret_score(850)
        assert result.risk_level == "Very Low Risk"

    def test_low_risk_700(self) -> None:
        result = interpret_score(700)
        assert result.risk_level == "Low Risk"
        assert result.interpretation == "Good creditworthiness"

    def test_low_risk_799(self) -> None:
        result = interpret_score(799)
        assert result.risk_level == "Low Risk"

    def test_medium_risk_600(self) -> None:
        result = interpret_score(600)
        assert result.risk_level == "Medium Risk"
        assert result.interpretation == "Fair creditworthiness"

    def test_medium_risk_699(self) -> None:
        result = interpret_score(699)
        assert result.risk_level == "Medium Risk"

    def test_high_risk_500(self) -> None:
        result = interpret_score(500)
        assert result.risk_level == "High Risk"
        assert result.interpretation == "Poor creditworthiness"

    def test_high_risk_599(self) -> None:
        result = interpret_score(599)
        assert result.risk_level == "High Risk"

    def test_very_high_risk_300(self) -> None:
        result = interpret_score(300)
        assert result.risk_level == "Very High Risk"
        assert result.interpretation == "Very poor creditworthiness"

    def test_very_high_risk_499(self) -> None:
        result = interpret_score(499)
        assert result.risk_level == "Very High Risk"

    def test_very_high_risk_350(self) -> None:
        result = interpret_score(350)
        assert result.risk_level == "Very High Risk"

    def test_below_range_raises(self) -> None:
        with pytest.raises(ValueError, match="between 300 and 900"):
            interpret_score(299)

    def test_above_range_raises(self) -> None:
        with pytest.raises(ValueError, match="between 300 and 900"):
            interpret_score(901)


# =========================================================================
# 2. National ID hashing
# =========================================================================


class TestIdHasher:
    """Verify hash_national_id is consistent and case-insensitive."""

    def test_consistent_hash(self) -> None:
        """Same input produces same hash."""
        h1 = hash_national_id("12345678")
        h2 = hash_national_id("12345678")
        assert h1 == h2

    def test_case_insensitive(self) -> None:
        """Lowercase and uppercase produce the same hash."""
        h1 = hash_national_id("abc123")
        h2 = hash_national_id("ABC123")
        assert h1 == h2

    def test_strips_whitespace(self) -> None:
        """Leading/trailing whitespace is stripped before hashing."""
        h1 = hash_national_id("12345678")
        h2 = hash_national_id("  12345678  ")
        assert h1 == h2

    def test_different_ids_different_hashes(self) -> None:
        """Different IDs produce different hashes."""
        h1 = hash_national_id("11111111")
        h2 = hash_national_id("22222222")
        assert h1 != h2

    def test_returns_hex_string(self) -> None:
        """Hash is a 64-character hex string (SHA-256)."""
        h = hash_national_id("12345678")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_mixed_case_with_spaces(self) -> None:
        """Combined case and whitespace normalization."""
        h1 = hash_national_id("AbCd1234")
        h2 = hash_national_id("  abcd1234  ")
        assert h1 == h2


# =========================================================================
# 3. Cache service
# =========================================================================


class TestScoreCacheService:
    """Test Redis cache get/set/invalidate operations with mock Redis."""

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_cache_miss_returns_none(self, mock_redis: AsyncMock) -> None:
        mock_redis.get.return_value = None
        result = await ScoreCacheService.get_cached_score(mock_redis, "abc123")
        assert result is None
        mock_redis.get.assert_called_once_with("score:lite:abc123")

    @pytest.mark.asyncio
    async def test_cache_hit_returns_data(self, mock_redis: AsyncMock) -> None:
        data = {"vyce_score": 750, "niq_score": 80}
        mock_redis.get.return_value = json.dumps(data)
        result = await ScoreCacheService.get_cached_score(mock_redis, "abc123")
        assert result == data

    @pytest.mark.asyncio
    async def test_cache_set_lite(self, mock_redis: AsyncMock) -> None:
        data = {"vyce_score": 750}
        await ScoreCacheService.cache_score(mock_redis, "abc123", data, pro=False)
        mock_redis.set.assert_called_once_with(
            "score:lite:abc123",
            json.dumps(data),
            ex=ScoreCacheService.TTL,
        )

    @pytest.mark.asyncio
    async def test_cache_set_pro(self, mock_redis: AsyncMock) -> None:
        data = {"vyce_score": 750}
        await ScoreCacheService.cache_score(mock_redis, "abc123", data, pro=True)
        mock_redis.set.assert_called_once_with(
            "score:pro:abc123",
            json.dumps(data),
            ex=ScoreCacheService.TTL,
        )

    @pytest.mark.asyncio
    async def test_cache_get_pro_key(self, mock_redis: AsyncMock) -> None:
        mock_redis.get.return_value = None
        await ScoreCacheService.get_cached_score(mock_redis, "abc123", pro=True)
        mock_redis.get.assert_called_once_with("score:pro:abc123")

    @pytest.mark.asyncio
    async def test_invalidate_deletes_both_keys(self, mock_redis: AsyncMock) -> None:
        await ScoreCacheService.invalidate_cache(mock_redis, "abc123")
        mock_redis.delete.assert_called_once_with(
            "score:lite:abc123",
            "score:pro:abc123",
        )

    @pytest.mark.asyncio
    async def test_ttl_is_24_hours(self) -> None:
        assert ScoreCacheService.TTL == 86400


# =========================================================================
# 4. Scoring service unit tests
# =========================================================================


def _make_subject(id_hash: str = "testhash") -> Subject:
    """Create a mock Subject for testing."""
    s = MagicMock(spec=Subject)
    s.subject_id = uuid.uuid4()
    s.id_hash = id_hash
    s.subject_type = SubjectType.INDIVIDUAL
    return s


def _make_score(
    subject_id: uuid.UUID | None = None,
    vyce_score: int = 720,
    niq_score: int = 75,
    confidence_lower: int | None = 690,
    confidence_upper: int | None = 750,
    model_version: str = "v1.0.0",
    score_date: date | None = None,
    prediction_horizon: int = 12,
    risk_drivers: list[RiskDriver] | None = None,
) -> Score:
    """Create a mock Score for testing."""
    s = MagicMock(spec=Score)
    s.subject_id = subject_id or uuid.uuid4()
    s.vyce_score = vyce_score
    s.niq_score = niq_score
    s.confidence_lower = confidence_lower
    s.confidence_upper = confidence_upper
    s.model_version = model_version
    s.score_date = score_date or date.today()
    s.prediction_horizon = prediction_horizon
    s.created_at = datetime.now(timezone.utc)
    s.risk_drivers = risk_drivers or []
    s.feature_snapshot_id = None
    return s


def _make_risk_driver(
    rank: int = 1,
    factor_name: str = "CBLRI",
    impact: ImpactDirection = ImpactDirection.NEGATIVE,
    description: str = "Test risk driver",
    shap_value: Decimal | None = Decimal("0.15"),
) -> RiskDriver:
    """Create a mock RiskDriver for testing."""
    d = MagicMock(spec=RiskDriver)
    d.rank = rank
    d.factor_name = factor_name
    d.impact = impact
    d.description = description
    d.shap_value = shap_value
    return d


class TestScoringServiceLite:
    """Test ScoringService.get_lite_score."""

    @pytest.mark.asyncio
    async def test_lite_score_cache_miss_returns_response(self) -> None:
        """On cache miss, queries DB and returns correct schema."""
        service = ScoringService()
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        subject = _make_subject(hash_national_id("12345678"))
        score = _make_score(subject_id=subject.subject_id)

        with (
            patch.object(service, "_get_subject_by_hash", return_value=subject) as mock_subj,
            patch.object(service, "_get_latest_score", return_value=score) as mock_score,
        ):
            result = await service.get_lite_score(mock_db, mock_redis, "12345678")

        assert isinstance(result, ScoreLiteResponse)
        assert result.vyce_score == 720
        assert result.niq_score == 75
        assert result.subject_id == hash_national_id("12345678")
        assert result.metadata.model_version == "v1.0.0"

    @pytest.mark.asyncio
    async def test_lite_score_cache_hit(self) -> None:
        """On cache hit, returns cached data without DB query."""
        service = ScoringService()
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        cached_data = {
            "vyce_score": 720,
            "niq_score": 75,
            "score_date": "2026-03-08",
            "score_version": "v1.0.0",
            "subject_id": hash_national_id("12345678"),
            "metadata": {
                "model_version": "v1.0.0",
                "feature_date": "2026-03-08",
                "data_quality": "high",
            },
        }
        mock_redis.get.return_value = json.dumps(cached_data)

        result = await service.get_lite_score(mock_db, mock_redis, "12345678")
        assert isinstance(result, ScoreLiteResponse)
        assert result.vyce_score == 720

    @pytest.mark.asyncio
    async def test_lite_score_unknown_subject_raises_404(self) -> None:
        """Unknown national ID raises NotFoundError."""
        from app.core.exceptions import NotFoundError

        service = ScoringService()
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        with patch.object(
            service, "_get_subject_by_hash", side_effect=NotFoundError("Subject", "abc...")
        ):
            with pytest.raises(NotFoundError):
                await service.get_lite_score(mock_db, mock_redis, "99999999")


class TestScoringServicePro:
    """Test ScoringService.get_pro_score."""

    @pytest.mark.asyncio
    async def test_pro_score_returns_risk_drivers(self) -> None:
        """Pro score includes risk drivers and interpretation."""
        service = ScoringService()
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        subject = _make_subject(hash_national_id("12345678"))
        drivers = [
            _make_risk_driver(rank=1, factor_name="CBLRI", shap_value=Decimal("0.20")),
            _make_risk_driver(rank=2, factor_name="UTDI", impact=ImpactDirection.POSITIVE, shap_value=Decimal("0.15")),
            _make_risk_driver(rank=3, factor_name="SCFV", shap_value=Decimal("0.10")),
        ]
        score = _make_score(
            subject_id=subject.subject_id,
            vyce_score=720,
            risk_drivers=drivers,
        )

        with (
            patch.object(service, "_get_subject_by_hash", return_value=subject),
            patch.object(service, "_get_latest_score_with_drivers", return_value=score),
        ):
            result = await service.get_pro_score(mock_db, mock_redis, "12345678")

        assert isinstance(result, ScoreProResponse)
        assert result.vyce_score == 720
        assert len(result.risk_drivers) == 3
        assert result.risk_drivers[0].factor == "CBLRI"
        assert result.interpretation.risk_level == "Low Risk"
        assert result.prediction_horizon == "12_months"
        assert result.confidence_interval.lower <= result.confidence_interval.upper

    @pytest.mark.asyncio
    async def test_pro_score_with_history(self) -> None:
        """Pro score with includeHistory returns history items."""
        service = ScoringService()
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        subject = _make_subject(hash_national_id("12345678"))
        drivers = [
            _make_risk_driver(rank=1, factor_name="CBLRI", shap_value=Decimal("0.20")),
        ]
        score = _make_score(
            subject_id=subject.subject_id,
            vyce_score=720,
            risk_drivers=drivers,
        )

        from app.schemas.scores import ScoreHistoryItem

        history = [
            ScoreHistoryItem(vyce_score=710, niq_score=70, score_date="2026-02-08", model_version="v1.0.0"),
            ScoreHistoryItem(vyce_score=700, niq_score=68, score_date="2026-01-08", model_version="v1.0.0"),
        ]

        with (
            patch.object(service, "_get_subject_by_hash", return_value=subject),
            patch.object(service, "_get_latest_score_with_drivers", return_value=score),
            patch.object(service, "_get_score_history", return_value=history),
        ):
            result = await service.get_pro_score(mock_db, mock_redis, "12345678", include_history=True)

        assert isinstance(result, ScoreProWithHistoryResponse)
        assert len(result.history) == 2
        assert result.history[0].vyce_score == 710

    @pytest.mark.asyncio
    async def test_pro_score_unknown_subject_raises_404(self) -> None:
        from app.core.exceptions import NotFoundError

        service = ScoringService()
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        with patch.object(
            service, "_get_subject_by_hash", side_effect=NotFoundError("Subject", "abc...")
        ):
            with pytest.raises(NotFoundError):
                await service.get_pro_score(mock_db, mock_redis, "99999999")


# =========================================================================
# 5. Tier validation
# =========================================================================


class TestTierValidation:
    """Test the require_tier dependency."""

    def _make_customer(self, tier: LicenseTier) -> Customer:
        c = MagicMock(spec=Customer)
        c.customer_id = uuid.uuid4()
        c.license_tier = tier
        c.status = CustomerStatus.ACTIVE
        return c

    @pytest.mark.asyncio
    async def test_lite_tier_allowed_for_lite_endpoint(self) -> None:
        from app.api.v1.scores import require_tier

        checker = require_tier("LITE", "PRO", "DEEP_DIVE")
        customer = self._make_customer(LicenseTier.LITE)

        # Directly invoke the inner checker
        result = await checker(customer=customer)
        assert result.license_tier == LicenseTier.LITE

    @pytest.mark.asyncio
    async def test_lite_tier_blocked_from_pro_endpoint(self) -> None:
        from app.api.v1.scores import require_tier
        from app.core.exceptions import ForbiddenError

        checker = require_tier("PRO", "DEEP_DIVE")
        customer = self._make_customer(LicenseTier.LITE)

        with pytest.raises(ForbiddenError, match="License tier insufficient"):
            await checker(customer=customer)

    @pytest.mark.asyncio
    async def test_pro_tier_allowed_for_pro_endpoint(self) -> None:
        from app.api.v1.scores import require_tier

        checker = require_tier("PRO", "DEEP_DIVE")
        customer = self._make_customer(LicenseTier.PRO)

        result = await checker(customer=customer)
        assert result.license_tier == LicenseTier.PRO

    @pytest.mark.asyncio
    async def test_deep_dive_tier_allowed_for_pro_endpoint(self) -> None:
        from app.api.v1.scores import require_tier

        checker = require_tier("PRO", "DEEP_DIVE")
        customer = self._make_customer(LicenseTier.DEEP_DIVE)

        result = await checker(customer=customer)
        assert result.license_tier == LicenseTier.DEEP_DIVE


# =========================================================================
# 6. Schema validation
# =========================================================================


class TestScoreSchemas:
    """Test Pydantic response schemas serialize correctly."""

    def test_lite_response_schema(self) -> None:
        resp = ScoreLiteResponse(
            vyce_score=750,
            niq_score=80,
            score_date="2026-03-08",
            score_version="v1.0.0",
            subject_id="a" * 64,
            metadata=ScoreMetadata(
                model_version="v1.0.0",
                feature_date="2026-03-08",
                data_quality="high",
            ),
        )
        data = resp.model_dump()
        assert data["vyce_score"] == 750
        assert data["niq_score"] == 80
        assert data["metadata"]["data_quality"] == "high"

    def test_pro_response_schema(self) -> None:
        resp = ScoreProResponse(
            vyce_score=650,
            niq_score=55,
            risk_drivers=[
                RiskDriverResponse(
                    factor="CBLRI",
                    impact="negative",
                    description="Below peer median",
                    contribution=45,
                ),
                RiskDriverResponse(
                    factor="UTDI",
                    impact="positive",
                    description="High diversity",
                    contribution=35,
                ),
                RiskDriverResponse(
                    factor="SCFV",
                    impact="negative",
                    description="Low growth",
                    contribution=20,
                ),
            ],
            score_date="2026-03-08",
            model_version="v1.0.0",
            prediction_horizon="12_months",
            confidence_interval=ConfidenceInterval(lower=620, upper=680),
            interpretation=ScoreInterpretation(
                risk_level="Medium Risk",
                interpretation="Fair creditworthiness",
            ),
        )
        data = resp.model_dump()
        assert len(data["risk_drivers"]) == 3
        assert data["confidence_interval"]["lower"] == 620
        assert data["interpretation"]["risk_level"] == "Medium Risk"

    def test_pro_with_history_schema(self) -> None:
        from app.schemas.scores import ScoreHistoryItem

        resp = ScoreProWithHistoryResponse(
            vyce_score=650,
            niq_score=55,
            risk_drivers=[
                RiskDriverResponse(
                    factor="CBLRI", impact="negative", description="test", contribution=100,
                ),
            ],
            score_date="2026-03-08",
            model_version="v1.0.0",
            prediction_horizon="12_months",
            confidence_interval=ConfidenceInterval(lower=620, upper=680),
            interpretation=ScoreInterpretation(
                risk_level="Medium Risk", interpretation="Fair creditworthiness",
            ),
            history=[
                ScoreHistoryItem(
                    vyce_score=640, niq_score=50, score_date="2026-02-08", model_version="v1.0.0",
                ),
            ],
        )
        data = resp.model_dump()
        assert len(data["history"]) == 1
        assert data["history"][0]["vyce_score"] == 640

    def test_score_below_300_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ScoreLiteResponse(
                vyce_score=299,
                niq_score=80,
                score_date="2026-03-08",
                score_version="v1.0.0",
                subject_id="a" * 64,
                metadata=ScoreMetadata(
                    model_version="v1.0.0", feature_date="2026-03-08", data_quality="high",
                ),
            )

    def test_score_above_900_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ScoreLiteResponse(
                vyce_score=901,
                niq_score=80,
                score_date="2026-03-08",
                score_version="v1.0.0",
                subject_id="a" * 64,
                metadata=ScoreMetadata(
                    model_version="v1.0.0", feature_date="2026-03-08", data_quality="high",
                ),
            )

    def test_invalid_data_quality_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ScoreMetadata(
                model_version="v1.0.0",
                feature_date="2026-03-08",
                data_quality="excellent",  # not in [high, medium, low]
            )

    def test_invalid_impact_direction_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RiskDriverResponse(
                factor="CBLRI",
                impact="neutral",  # not in [positive, negative]
                description="test",
                contribution=50,
            )


# =========================================================================
# 7. Error response format
# =========================================================================


class TestErrorFormat:
    """Verify error responses follow the standard format."""

    def test_not_found_error_structure(self) -> None:
        from app.core.exceptions import NotFoundError

        err = NotFoundError("Subject", "abc123")
        assert err.code == "NOT_FOUND"
        assert err.status_code == 404
        assert err.details["resource"] == "Subject"

    def test_forbidden_error_structure(self) -> None:
        from app.core.exceptions import ForbiddenError

        err = ForbiddenError("License tier insufficient")
        assert err.code == "FORBIDDEN"
        assert err.status_code == 403

    def test_rate_limited_error_structure(self) -> None:
        from app.core.exceptions import RateLimitedError

        err = RateLimitedError()
        assert err.code == "RATE_LIMITED"
        assert err.status_code == 429
