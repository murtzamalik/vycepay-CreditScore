"""Tests for ComplianceFeatureBridge (Phase 15.4)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.compliance_check import (
    ComplianceCheckStatus,
    ComplianceCheckType,
)
from app.services.compliance_feature_bridge import ComplianceFeatureBridge, ComplianceFeatures


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_kyc_check(
    *,
    days_ago: float = 5.0,
    confidence: float = 0.95,
    status: ComplianceCheckStatus = ComplianceCheckStatus.PASSED,
) -> MagicMock:
    """Create a mock KYC compliance check."""
    check = MagicMock()
    check.check_id = uuid.uuid4()
    check.subject_id = uuid.uuid4()
    check.check_type = ComplianceCheckType.KYC
    check.status = status
    check.provider = "smile_id"
    check.provider_reference = "job-123"
    check.confidence_score = confidence
    check.risk_score = None
    check.checked_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    check.expires_at = None
    return check


def _make_aml_check(
    *,
    risk_score: float = 0.1,
    status: ComplianceCheckStatus = ComplianceCheckStatus.PASSED,
) -> MagicMock:
    """Create a mock AML compliance check."""
    check = MagicMock()
    check.check_id = uuid.uuid4()
    check.subject_id = uuid.uuid4()
    check.check_type = ComplianceCheckType.AML
    check.status = status
    check.provider = "comply_advantage"
    check.provider_reference = "search-123"
    check.confidence_score = None
    check.risk_score = risk_score
    check.checked_at = datetime.now(timezone.utc)
    check.expires_at = None
    return check


# ---------------------------------------------------------------------------
# Tests: ComplianceFeatures dataclass
# ---------------------------------------------------------------------------


class TestComplianceFeatures:
    def test_to_dict(self) -> None:
        features = ComplianceFeatures(
            kyc_verification_days=10.0,
            aml_risk_score=0.3,
            identity_match_confidence=0.95,
            sanctions_list_flag=0.0,
            pep_flag=0.0,
        )
        d = features.to_dict()
        assert d["kyc_verification_days"] == 10.0
        assert d["aml_risk_score"] == 0.3
        assert d["identity_match_confidence"] == 0.95
        assert d["sanctions_list_flag"] == 0.0
        assert d["pep_flag"] == 0.0

    def test_to_dict_with_none(self) -> None:
        features = ComplianceFeatures(
            kyc_verification_days=None,
            aml_risk_score=None,
            identity_match_confidence=None,
            sanctions_list_flag=0.0,
            pep_flag=0.0,
        )
        d = features.to_dict()
        assert d["kyc_verification_days"] is None
        assert d["aml_risk_score"] is None


# ---------------------------------------------------------------------------
# Tests: Feature Computation Methods
# ---------------------------------------------------------------------------


class TestFeatureComputation:
    def test_compute_kyc_days(self) -> None:
        bridge = ComplianceFeatureBridge()
        check = _make_kyc_check(days_ago=10.0)
        ref = datetime.now(timezone.utc)
        days = bridge._compute_kyc_days(check, ref)
        assert days is not None
        assert 9.5 < days < 10.5

    def test_compute_kyc_days_none_when_no_check(self) -> None:
        bridge = ComplianceFeatureBridge()
        ref = datetime.now(timezone.utc)
        days = bridge._compute_kyc_days(None, ref)
        assert days is None

    def test_compute_kyc_days_none_when_failed(self) -> None:
        bridge = ComplianceFeatureBridge()
        check = _make_kyc_check(status=ComplianceCheckStatus.FAILED)
        ref = datetime.now(timezone.utc)
        days = bridge._compute_kyc_days(check, ref)
        assert days is None

    def test_compute_identity_confidence(self) -> None:
        bridge = ComplianceFeatureBridge()
        check = _make_kyc_check(confidence=0.92)
        confidence = bridge._compute_identity_confidence(check)
        assert confidence == pytest.approx(0.92)

    def test_compute_identity_confidence_none(self) -> None:
        bridge = ComplianceFeatureBridge()
        confidence = bridge._compute_identity_confidence(None)
        assert confidence is None

    def test_compute_identity_confidence_clamped(self) -> None:
        bridge = ComplianceFeatureBridge()
        check = _make_kyc_check(confidence=1.5)
        confidence = bridge._compute_identity_confidence(check)
        assert confidence == pytest.approx(1.0)

    def test_compute_aml_risk_score(self) -> None:
        bridge = ComplianceFeatureBridge()
        check = _make_aml_check(risk_score=0.4)
        score = bridge._compute_aml_risk_score(check)
        assert score == pytest.approx(0.4)

    def test_compute_aml_risk_score_none(self) -> None:
        bridge = ComplianceFeatureBridge()
        score = bridge._compute_aml_risk_score(None)
        assert score is None

    def test_compute_aml_risk_score_clamped(self) -> None:
        bridge = ComplianceFeatureBridge()
        check = _make_aml_check(risk_score=1.5)
        score = bridge._compute_aml_risk_score(check)
        assert score == pytest.approx(1.0)

    def test_compute_sanctions_flag_flagged(self) -> None:
        bridge = ComplianceFeatureBridge()
        check = _make_aml_check(
            risk_score=1.0, status=ComplianceCheckStatus.FAILED,
        )
        flag = bridge._compute_sanctions_flag(check)
        assert flag == 1.0

    def test_compute_sanctions_flag_clear(self) -> None:
        bridge = ComplianceFeatureBridge()
        check = _make_aml_check(
            risk_score=0.1, status=ComplianceCheckStatus.PASSED,
        )
        flag = bridge._compute_sanctions_flag(check)
        assert flag == 0.0

    def test_compute_sanctions_flag_none(self) -> None:
        bridge = ComplianceFeatureBridge()
        flag = bridge._compute_sanctions_flag(None)
        assert flag == 0.0

    def test_compute_pep_flag_review(self) -> None:
        bridge = ComplianceFeatureBridge()
        check = _make_aml_check(status=ComplianceCheckStatus.REVIEW)
        flag = bridge._compute_pep_flag(check)
        assert flag == 1.0

    def test_compute_pep_flag_clear(self) -> None:
        bridge = ComplianceFeatureBridge()
        check = _make_aml_check(status=ComplianceCheckStatus.PASSED)
        flag = bridge._compute_pep_flag(check)
        assert flag == 0.0

    def test_compute_pep_flag_none(self) -> None:
        bridge = ComplianceFeatureBridge()
        flag = bridge._compute_pep_flag(None)
        assert flag == 0.0


# ---------------------------------------------------------------------------
# Tests: Full Feature Extraction
# ---------------------------------------------------------------------------


class TestFeatureExtraction:
    @pytest.mark.asyncio
    async def test_extract_features_with_both_checks(self) -> None:
        """Test feature extraction with both KYC and AML checks present."""
        bridge = ComplianceFeatureBridge()
        subject_id = uuid.uuid4()

        kyc_check = _make_kyc_check(days_ago=5.0, confidence=0.92)
        aml_check = _make_aml_check(risk_score=0.2)

        mock_db = AsyncMock()

        # Mock the database queries
        with patch.object(
            bridge, "_get_latest_check",
            side_effect=[kyc_check, aml_check],
        ):
            features = await bridge.extract_features(mock_db, subject_id)

        assert features.kyc_verification_days is not None
        assert 4.5 < features.kyc_verification_days < 5.5
        assert features.identity_match_confidence == pytest.approx(0.92)
        assert features.aml_risk_score == pytest.approx(0.2)
        assert features.sanctions_list_flag == 0.0
        assert features.pep_flag == 0.0

    @pytest.mark.asyncio
    async def test_extract_features_no_checks(self) -> None:
        """Test feature extraction with no compliance checks."""
        bridge = ComplianceFeatureBridge()
        subject_id = uuid.uuid4()
        mock_db = AsyncMock()

        with patch.object(
            bridge, "_get_latest_check",
            side_effect=[None, None],
        ):
            features = await bridge.extract_features(mock_db, subject_id)

        assert features.kyc_verification_days is None
        assert features.identity_match_confidence is None
        assert features.aml_risk_score is None
        assert features.sanctions_list_flag == 0.0
        assert features.pep_flag == 0.0

    @pytest.mark.asyncio
    async def test_extract_features_sanctioned(self) -> None:
        """Test feature extraction for a sanctioned individual."""
        bridge = ComplianceFeatureBridge()
        subject_id = uuid.uuid4()

        kyc_check = _make_kyc_check(confidence=0.85)
        aml_check = _make_aml_check(
            risk_score=1.0, status=ComplianceCheckStatus.FAILED,
        )

        mock_db = AsyncMock()

        with patch.object(
            bridge, "_get_latest_check",
            side_effect=[kyc_check, aml_check],
        ):
            features = await bridge.extract_features(mock_db, subject_id)

        assert features.sanctions_list_flag == 1.0
        assert features.aml_risk_score == pytest.approx(1.0)
