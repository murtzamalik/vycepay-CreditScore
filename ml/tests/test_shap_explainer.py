"""Tests for ml.explainability.shap_explainer — SHAP-based explainability."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import xgboost as xgb

from ml.explainability.shap_explainer import (
    FEATURE_DISPLAY_NAMES,
    ExplanationResult,
    RiskDriver,
    VyceScoreExplainer,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FEATURES = ["cblri", "utdi", "scfv", "ddc_ratio", "niq_score", "gos_index"]


@pytest.fixture()
def trained_model() -> xgb.XGBClassifier:
    """Train a small XGBoost model on synthetic data."""
    np.random.seed(42)
    n = 200
    X = pd.DataFrame({feat: np.random.uniform(0, 1, n) for feat in FEATURES})
    y = (
        0.3 * X["cblri"]
        + 0.25 * X["utdi"]
        + 0.15 * X["scfv"]
        + 0.15 * X["ddc_ratio"]
        + 0.1 * X["niq_score"]
        + 0.05 * X["gos_index"]
        + np.random.normal(0, 0.1, n)
    )
    y_binary = (y > y.median()).astype(int)

    model = xgb.XGBClassifier(
        n_estimators=20,
        max_depth=3,
        random_state=42,
        use_label_encoder=False,
        eval_metric="logloss",
    )
    model.fit(X, y_binary)
    return model


@pytest.fixture()
def explainer(trained_model: xgb.XGBClassifier) -> VyceScoreExplainer:
    """Create a VyceScoreExplainer with the trained model."""
    return VyceScoreExplainer(trained_model)


@pytest.fixture()
def single_row_features() -> pd.DataFrame:
    """A single row of features for prediction."""
    return pd.DataFrame({
        "cblri": [0.7],
        "utdi": [0.5],
        "scfv": [0.3],
        "ddc_ratio": [0.8],
        "niq_score": [0.6],
        "gos_index": [0.4],
    })


@pytest.fixture()
def multi_row_features() -> pd.DataFrame:
    """Multiple rows of features for batch prediction."""
    np.random.seed(42)
    n = 5
    return pd.DataFrame({feat: np.random.uniform(0, 1, n) for feat in FEATURES})


# ---------------------------------------------------------------------------
# Test VyceScoreExplainer
# ---------------------------------------------------------------------------

class TestVyceScoreExplainer:
    def test_initialization(self, trained_model: xgb.XGBClassifier) -> None:
        explainer = VyceScoreExplainer(trained_model)
        assert explainer.explainer is not None

    def test_custom_feature_names(
        self, trained_model: xgb.XGBClassifier
    ) -> None:
        custom = {"cblri": "Custom CBLRI Name"}
        explainer = VyceScoreExplainer(trained_model, feature_names=custom)
        assert explainer._feature_names["cblri"] == "Custom CBLRI Name"
        # Other defaults should still be present
        assert "utdi" in explainer._feature_names


class TestExplain:
    def test_single_prediction(
        self,
        explainer: VyceScoreExplainer,
        single_row_features: pd.DataFrame,
    ) -> None:
        result = explainer.explain(single_row_features)
        assert isinstance(result, ExplanationResult)
        assert len(result.risk_drivers) == 3
        assert len(result.shap_values) == 6
        assert 0.0 <= result.prediction_probability <= 1.0

    def test_risk_drivers_structure(
        self,
        explainer: VyceScoreExplainer,
        single_row_features: pd.DataFrame,
    ) -> None:
        result = explainer.explain(single_row_features)
        for driver in result.risk_drivers:
            assert isinstance(driver, RiskDriver)
            assert driver.factor != ""
            assert driver.impact in ("positive", "negative")
            assert driver.description != ""
            assert 0.0 <= driver.contribution <= 100.0
            assert driver.feature_name in FEATURES

    def test_contributions_sum_close_to_100(
        self,
        explainer: VyceScoreExplainer,
        single_row_features: pd.DataFrame,
    ) -> None:
        # Top 6 drivers should sum to 100%
        result = explainer.explain(single_row_features, top_n=6)
        total = sum(d.contribution for d in result.risk_drivers)
        assert abs(total - 100.0) < 1.0  # Allow small rounding

    def test_top_n_parameter(
        self,
        explainer: VyceScoreExplainer,
        single_row_features: pd.DataFrame,
    ) -> None:
        result_2 = explainer.explain(single_row_features, top_n=2)
        result_5 = explainer.explain(single_row_features, top_n=5)
        assert len(result_2.risk_drivers) == 2
        assert len(result_5.risk_drivers) == 5

    def test_drivers_sorted_by_contribution(
        self,
        explainer: VyceScoreExplainer,
        single_row_features: pd.DataFrame,
    ) -> None:
        result = explainer.explain(single_row_features)
        contributions = [d.contribution for d in result.risk_drivers]
        assert contributions == sorted(contributions, reverse=True)

    def test_multi_row_raises_error(
        self,
        explainer: VyceScoreExplainer,
        multi_row_features: pd.DataFrame,
    ) -> None:
        with pytest.raises(ValueError, match="single-row"):
            explainer.explain(multi_row_features)

    def test_human_readable_names(
        self,
        explainer: VyceScoreExplainer,
        single_row_features: pd.DataFrame,
    ) -> None:
        result = explainer.explain(single_row_features, top_n=6)
        for driver in result.risk_drivers:
            # Should use display name, not raw feature name
            assert driver.factor != driver.feature_name
            assert driver.factor == FEATURE_DISPLAY_NAMES[driver.feature_name]

    def test_shap_values_dict(
        self,
        explainer: VyceScoreExplainer,
        single_row_features: pd.DataFrame,
    ) -> None:
        result = explainer.explain(single_row_features)
        for feat in FEATURES:
            assert feat in result.shap_values
            assert isinstance(result.shap_values[feat], float)


class TestExplainBatch:
    def test_batch_predictions(
        self,
        explainer: VyceScoreExplainer,
        multi_row_features: pd.DataFrame,
    ) -> None:
        results = explainer.explain_batch(multi_row_features)
        assert len(results) == len(multi_row_features)
        for result in results:
            assert isinstance(result, ExplanationResult)
            assert len(result.risk_drivers) == 3


class TestToApiFormat:
    def test_api_format(
        self,
        explainer: VyceScoreExplainer,
        single_row_features: pd.DataFrame,
    ) -> None:
        result = explainer.explain(single_row_features)
        api_output = explainer.to_api_format(result)
        assert isinstance(api_output, list)
        assert len(api_output) == 3
        for item in api_output:
            assert "factor" in item
            assert "impact" in item
            assert "description" in item
            assert "contribution" in item
            # Should NOT include raw feature names in API output
            assert "feature_name" not in item
            assert "shap_value" not in item
