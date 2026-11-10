"""Tests for ml.models.model_selector module."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ml.models.industry_variants import IndustryVertical
from ml.models.model_selector import (
    ModelInfo,
    ModelSelector,
    SelectionResult,
)


def _make_mock_model() -> MagicMock:
    """Create a simple mock XGBoost model."""
    return MagicMock()


@pytest.fixture()
def general_model() -> MagicMock:
    return _make_mock_model()


@pytest.fixture()
def selector(general_model: MagicMock) -> ModelSelector:
    """A ModelSelector with a general model."""
    info = ModelInfo(
        model_id="general-v1",
        vertical=IndustryVertical.GENERAL,
        horizon_days=365,
        auc_roc=0.78,
        training_samples=10000,
        model=general_model,
        is_production=True,
    )
    return ModelSelector(general_model, info)


class TestModelSelector:
    """Tests for ModelSelector."""

    def test_select_general_by_default(self, selector: ModelSelector) -> None:
        result = selector.select()
        assert isinstance(result, SelectionResult)
        assert result.selected_model.vertical == IndustryVertical.GENERAL
        assert result.fallback_used is False

    def test_select_fallback_when_no_industry_model(
        self, selector: ModelSelector
    ) -> None:
        result = selector.select(vertical="retail")
        assert result.selected_model.vertical == IndustryVertical.GENERAL
        assert result.fallback_used is True

    def test_select_industry_model_when_available(
        self, selector: ModelSelector
    ) -> None:
        retail_info = ModelInfo(
            model_id="retail-v1",
            vertical=IndustryVertical.RETAIL,
            horizon_days=365,
            auc_roc=0.80,
            training_samples=5000,
            model=_make_mock_model(),
        )
        selector.register_model(retail_info)

        result = selector.select(vertical="retail")
        assert result.selected_model.vertical == IndustryVertical.RETAIL
        assert result.fallback_used is False

    def test_fallback_when_insufficient_training_data(
        self, selector: ModelSelector
    ) -> None:
        retail_info = ModelInfo(
            model_id="retail-v1",
            vertical=IndustryVertical.RETAIL,
            horizon_days=365,
            auc_roc=0.80,
            training_samples=50,  # Below min_training_samples
            model=_make_mock_model(),
        )
        selector.register_model(retail_info)

        result = selector.select(vertical="retail")
        assert result.selected_model.vertical == IndustryVertical.GENERAL
        assert result.fallback_used is True

    def test_low_data_quality_uses_general(self, selector: ModelSelector) -> None:
        result = selector.select(
            vertical="retail",
            data_completeness=0.1,
            available_features=["cblri"],  # Only 1 of 6 features
        )
        assert result.selected_model.vertical == IndustryVertical.GENERAL
        assert result.data_quality == "low"

    def test_list_models(self, selector: ModelSelector) -> None:
        models = selector.list_models()
        assert len(models) >= 1
        assert models[0]["model_id"] == "general-v1"

    def test_register_and_unregister(self, selector: ModelSelector) -> None:
        info = ModelInfo(
            model_id="test-v1",
            vertical=IndustryVertical.SERVICES,
            horizon_days=365,
            auc_roc=0.75,
            training_samples=1000,
            model=_make_mock_model(),
        )
        selector.register_model(info)
        assert len(selector.list_models()) == 2

        selector.unregister_model("test-v1")
        assert len(selector.list_models()) == 1

    def test_cannot_unregister_general(self, selector: ModelSelector) -> None:
        with pytest.raises(ValueError, match="Cannot unregister"):
            selector.unregister_model("general-v1")

    def test_unknown_vertical_falls_back(self, selector: ModelSelector) -> None:
        result = selector.select(vertical="unknown_industry")
        assert result.selected_model.vertical == IndustryVertical.GENERAL

    def test_horizon_matching(self, selector: ModelSelector) -> None:
        model_30d = ModelInfo(
            model_id="retail-30d",
            vertical=IndustryVertical.RETAIL,
            horizon_days=30,
            auc_roc=0.82,
            training_samples=5000,
            model=_make_mock_model(),
        )
        selector.register_model(model_30d)

        # Request 365-day horizon -- should not match 30-day model
        result = selector.select(vertical="retail", horizon_days=365)
        assert result.selected_model.vertical == IndustryVertical.GENERAL
        assert result.fallback_used is True

        # Request 30-day horizon -- should match
        result = selector.select(vertical="retail", horizon_days=30)
        assert result.selected_model.model_id == "retail-30d"
