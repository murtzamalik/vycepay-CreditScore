"""Tests for ml.deployment.canary module."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from ml.deployment.canary import (
    CanaryConfig,
    CanaryDeployment,
    CanaryMetrics,
    CanaryPrediction,
)


def _make_mock_model(probability: float) -> MagicMock:
    """Create a mock XGBoost model that returns a fixed probability."""
    model = MagicMock()
    model.predict_proba.return_value = np.array([[1 - probability, probability]])
    return model


def _make_features() -> pd.DataFrame:
    """Create a single-row feature DataFrame."""
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


class TestCanaryDeployment:
    """Tests for CanaryDeployment."""

    def test_predict_returns_valid_result(self) -> None:
        prod = _make_mock_model(0.3)
        cand = _make_mock_model(0.4)
        config = CanaryConfig(traffic_percentage=50.0)

        canary = CanaryDeployment(prod, cand, config=config)
        result = canary.predict(_make_features())

        assert isinstance(result, CanaryPrediction)
        assert result.model_used in ("production", "candidate")
        assert 300 <= result.score <= 900

    def test_zero_traffic_always_uses_production(self) -> None:
        prod = _make_mock_model(0.3)
        cand = _make_mock_model(0.9)
        config = CanaryConfig(traffic_percentage=0.0)

        canary = CanaryDeployment(prod, cand, config=config)
        for _ in range(20):
            result = canary.predict(_make_features())
            assert result.model_used == "production"

    def test_hundred_percent_traffic_always_uses_candidate(self) -> None:
        prod = _make_mock_model(0.3)
        cand = _make_mock_model(0.9)
        config = CanaryConfig(traffic_percentage=100.0)

        canary = CanaryDeployment(prod, cand, config=config)
        for _ in range(20):
            result = canary.predict(_make_features())
            assert result.model_used == "candidate"

    def test_metrics_are_tracked(self) -> None:
        prod = _make_mock_model(0.3)
        cand = _make_mock_model(0.4)
        config = CanaryConfig(traffic_percentage=50.0)

        canary = CanaryDeployment(prod, cand, config=config)
        for _ in range(100):
            canary.predict(_make_features())

        metrics = canary.get_metrics()
        assert "production" in metrics
        assert "candidate" in metrics

        total = (
            metrics["production"].total_predictions
            + metrics["candidate"].total_predictions
        )
        assert total == 100

    def test_rollback_routes_to_production(self) -> None:
        prod = _make_mock_model(0.3)
        cand = _make_mock_model(0.9)
        config = CanaryConfig(traffic_percentage=100.0)

        canary = CanaryDeployment(prod, cand, config=config)
        canary.rollback(reason="test")

        assert canary.is_rolled_back is True

        result = canary.predict(_make_features())
        assert result.model_used == "production"

    def test_set_traffic_percentage(self) -> None:
        canary = CanaryDeployment(
            _make_mock_model(0.3),
            _make_mock_model(0.4),
        )
        canary.set_traffic_percentage(25.0)
        assert canary.traffic_percentage == 25.0

    def test_set_invalid_traffic_percentage_raises(self) -> None:
        canary = CanaryDeployment(
            _make_mock_model(0.3),
            _make_mock_model(0.4),
        )
        with pytest.raises(ValueError, match="between 0 and 100"):
            canary.set_traffic_percentage(150.0)

    def test_promote_candidate(self) -> None:
        canary = CanaryDeployment(
            _make_mock_model(0.3),
            _make_mock_model(0.4),
        )
        canary.promote_candidate()
        assert canary.is_active is False

    def test_stop_returns_metrics(self) -> None:
        canary = CanaryDeployment(
            _make_mock_model(0.3),
            _make_mock_model(0.4),
        )
        canary.predict(_make_features())
        metrics = canary.stop()

        assert "production" in metrics
        assert "candidate" in metrics
