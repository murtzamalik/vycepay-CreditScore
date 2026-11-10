"""Tests for ml.models.industry_variants module."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.models.industry_variants import (
    INDUSTRY_PROFILES,
    IndustryVertical,
    apply_industry_weights,
    get_industry_profile,
    get_prediction_horizon_config,
    list_supported_verticals,
)


@pytest.fixture()
def feature_df() -> pd.DataFrame:
    """Sample feature DataFrame."""
    return pd.DataFrame(
        {
            "cblri": [0.8],
            "utdi": [0.6],
            "scfv": [0.4],
            "ddc_ratio": [0.7],
            "niq_score": [55.0],
            "gos_index": [0.3],
        }
    )


class TestGetIndustryProfile:
    """Tests for get_industry_profile."""

    def test_get_general(self) -> None:
        profile = get_industry_profile(IndustryVertical.GENERAL)
        assert profile.vertical == IndustryVertical.GENERAL
        # General should have all weights at 1.0
        for w in profile.feature_weights.values():
            assert w == 1.0

    def test_get_retail(self) -> None:
        profile = get_industry_profile("retail")
        assert profile.vertical == IndustryVertical.RETAIL
        assert profile.feature_weights["utdi"] > 1.0  # Emphasised

    def test_get_manufacturing(self) -> None:
        profile = get_industry_profile("manufacturing")
        assert profile.feature_weights["scfv"] > 1.0  # Emphasised

    def test_get_agriculture(self) -> None:
        profile = get_industry_profile("agriculture")
        assert profile.feature_weights["gos_index"] > 1.0  # Emphasised

    def test_invalid_vertical_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported"):
            get_industry_profile("invalid_vertical")

    def test_all_verticals_have_profiles(self) -> None:
        for vertical in IndustryVertical:
            profile = get_industry_profile(vertical)
            assert profile is not None


class TestApplyIndustryWeights:
    """Tests for apply_industry_weights."""

    def test_general_weights_no_change(self, feature_df: pd.DataFrame) -> None:
        result = apply_industry_weights(feature_df, "general")
        pd.testing.assert_frame_equal(result, feature_df)

    def test_retail_weights_modify_utdi(self, feature_df: pd.DataFrame) -> None:
        result = apply_industry_weights(feature_df, "retail")
        # UTDI should be higher due to weight > 1.0
        assert result["utdi"].iloc[0] > feature_df["utdi"].iloc[0]

    def test_agriculture_weights_modify_gos(self, feature_df: pd.DataFrame) -> None:
        result = apply_industry_weights(feature_df, "agriculture")
        assert result["gos_index"].iloc[0] > feature_df["gos_index"].iloc[0]

    def test_original_df_unchanged(self, feature_df: pd.DataFrame) -> None:
        original = feature_df.copy()
        _ = apply_industry_weights(feature_df, "retail")
        pd.testing.assert_frame_equal(feature_df, original)


class TestPredictionHorizonConfig:
    """Tests for get_prediction_horizon_config."""

    def test_30_day_horizon(self) -> None:
        config = get_prediction_horizon_config(30)
        assert config["horizon_days"] == 30
        assert config["horizon_label"] == "30_days"
        assert config["recency_weight"] > 1.0

    def test_90_day_horizon(self) -> None:
        config = get_prediction_horizon_config(90)
        assert config["horizon_days"] == 90

    def test_365_day_horizon(self) -> None:
        config = get_prediction_horizon_config(365)
        assert config["horizon_days"] == 365
        assert config["recency_weight"] == 1.0

    def test_invalid_horizon_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported"):
            get_prediction_horizon_config(60)


class TestListSupportedVerticals:
    """Tests for list_supported_verticals."""

    def test_returns_all_verticals(self) -> None:
        verticals = list_supported_verticals()
        assert len(verticals) == len(IndustryVertical)

    def test_each_has_required_keys(self) -> None:
        for v in list_supported_verticals():
            assert "vertical" in v
            assert "description" in v
            assert "prediction_horizons" in v
