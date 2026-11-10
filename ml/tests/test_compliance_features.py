"""Tests for ml.features.compliance_features."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from ml.features.base import FeatureCategory, FeatureResult
from ml.features.compliance_features import (
    ALL_COMPLIANCE_FEATURES,
    AmlRiskScore,
    IdentityMatchConfidence,
    KycVerificationDays,
    PepFlag,
    SanctionsListFlag,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def compliance_df() -> pd.DataFrame:
    """Compliance data per entity."""
    return pd.DataFrame({
        "entity_id": ["E001", "E002", "E003", "E004"],
        "kyc_verification_date": [
            datetime(2025, 1, 15),
            datetime(2024, 6, 1),
            pd.NaT,
            datetime(2025, 3, 1),
        ],
        "aml_risk_rating": [0.1, 0.8, np.nan, 0.3],
        "biometric_confidence": [0.95, 0.70, np.nan, 0.85],
        "on_sanctions_list": [False, False, True, False],
        "is_pep": [False, True, False, False],
    })


# ---------------------------------------------------------------------------
# Tests — KycVerificationDays
# ---------------------------------------------------------------------------


class TestKycVerificationDays:
    def test_basic_computation(self, compliance_df: pd.DataFrame) -> None:
        ref = datetime(2025, 6, 15)
        computer = KycVerificationDays()
        result = computer.compute(compliance_df, reference_date=ref)

        assert isinstance(result, FeatureResult)
        assert result.metadata.name == "kyc_verification_days"
        assert result.metadata.category == FeatureCategory.COMPLIANCE
        # E001: Jan 15 -> Jun 15 = 151 days
        assert result.values.iloc[0] == pytest.approx(151.0)
        # E003: NaT -> NaN
        assert np.isnan(result.values.iloc[2])

    def test_future_date_returns_nan(self) -> None:
        ref = datetime(2025, 1, 1)
        df = pd.DataFrame({
            "kyc_verification_date": [datetime(2025, 6, 1)]
        })
        computer = KycVerificationDays()
        result = computer.compute(df, reference_date=ref)
        assert np.isnan(result.values.iloc[0])

    def test_missing_column(self) -> None:
        df = pd.DataFrame({"unrelated": [1]})
        computer = KycVerificationDays()
        result = computer.compute(df)
        assert result.data_quality_score == 0.0
        assert result.values.isna().all()


# ---------------------------------------------------------------------------
# Tests — AmlRiskScore
# ---------------------------------------------------------------------------


class TestAmlRiskScore:
    def test_basic_computation(self, compliance_df: pd.DataFrame) -> None:
        computer = AmlRiskScore()
        result = computer.compute(compliance_df)

        assert result.metadata.name == "aml_risk_score"
        assert result.values.iloc[0] == pytest.approx(0.1)
        assert result.values.iloc[1] == pytest.approx(0.8)

    def test_clamped_to_unit_interval(self) -> None:
        df = pd.DataFrame({"aml_risk_rating": [-0.5, 1.5, 0.5]})
        computer = AmlRiskScore()
        result = computer.compute(df)
        assert result.values.iloc[0] == 0.0
        assert result.values.iloc[1] == 1.0
        assert result.values.iloc[2] == 0.5


# ---------------------------------------------------------------------------
# Tests — IdentityMatchConfidence
# ---------------------------------------------------------------------------


class TestIdentityMatchConfidence:
    def test_basic_computation(self, compliance_df: pd.DataFrame) -> None:
        computer = IdentityMatchConfidence()
        result = computer.compute(compliance_df)

        assert result.values.iloc[0] == pytest.approx(0.95)
        assert result.values.iloc[1] == pytest.approx(0.70)

    def test_clamped(self) -> None:
        df = pd.DataFrame({"biometric_confidence": [1.5, -0.1]})
        computer = IdentityMatchConfidence()
        result = computer.compute(df)
        assert result.values.iloc[0] == 1.0
        assert result.values.iloc[1] == 0.0


# ---------------------------------------------------------------------------
# Tests — SanctionsListFlag
# ---------------------------------------------------------------------------


class TestSanctionsListFlag:
    def test_basic_computation(self, compliance_df: pd.DataFrame) -> None:
        computer = SanctionsListFlag()
        result = computer.compute(compliance_df)

        assert result.metadata.name == "sanctions_list_flag"
        assert result.values.iloc[0] == 0.0  # False
        assert result.values.iloc[2] == 1.0  # True

    def test_boolean_dtype(self) -> None:
        df = pd.DataFrame({"on_sanctions_list": [True, False]})
        computer = SanctionsListFlag()
        result = computer.compute(df)
        assert result.values.iloc[0] == 1.0
        assert result.values.iloc[1] == 0.0


# ---------------------------------------------------------------------------
# Tests — PepFlag
# ---------------------------------------------------------------------------


class TestPepFlag:
    def test_basic_computation(self, compliance_df: pd.DataFrame) -> None:
        computer = PepFlag()
        result = computer.compute(compliance_df)

        assert result.metadata.name == "pep_flag"
        assert result.values.iloc[0] == 0.0  # False
        assert result.values.iloc[1] == 1.0  # True


# ---------------------------------------------------------------------------
# Tests — Meta
# ---------------------------------------------------------------------------


class TestComplianceFeaturesMeta:
    def test_all_features_listed(self) -> None:
        assert len(ALL_COMPLIANCE_FEATURES) == 5

    def test_all_are_compliance_category(self) -> None:
        for cls in ALL_COMPLIANCE_FEATURES:
            assert cls().metadata.category == FeatureCategory.COMPLIANCE

    def test_data_quality_with_nan(self, compliance_df: pd.DataFrame) -> None:
        computer = AmlRiskScore()
        result = computer.compute(compliance_df)
        # 3/4 non-null => quality < 1.0
        assert 0.0 < result.data_quality_score < 1.0
