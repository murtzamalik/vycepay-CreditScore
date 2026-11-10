"""Tests for ml.deployment.shadow module."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from ml.deployment.shadow import (
    ShadowComparisonSummary,
    ShadowDeployment,
    ShadowPrediction,
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


class TestShadowDeployment:
    """Tests for ShadowDeployment."""

    def test_predict_returns_both_models(self) -> None:
        prod = _make_mock_model(0.3)
        cand = _make_mock_model(0.4)
        shadow = ShadowDeployment(prod, cand)

        result = shadow.predict(_make_features())

        assert isinstance(result, ShadowPrediction)
        assert result.production_probability == pytest.approx(0.3)
        assert result.candidate_probability == pytest.approx(0.4)

    def test_delta_is_computed(self) -> None:
        prod = _make_mock_model(0.3)
        cand = _make_mock_model(0.5)
        shadow = ShadowDeployment(prod, cand)

        result = shadow.predict(_make_features())

        assert result.delta_probability == pytest.approx(0.2)

    def test_scores_are_in_range(self) -> None:
        prod = _make_mock_model(0.1)
        cand = _make_mock_model(0.9)
        shadow = ShadowDeployment(prod, cand)

        result = shadow.predict(_make_features())

        assert 300 <= result.production_score <= 900
        assert 300 <= result.candidate_score <= 900

    def test_comparison_count_tracks_predictions(self) -> None:
        shadow = ShadowDeployment(
            _make_mock_model(0.3),
            _make_mock_model(0.4),
        )

        for _ in range(5):
            shadow.predict(_make_features())

        assert shadow.comparison_count == 5

    def test_summary_statistics(self) -> None:
        shadow = ShadowDeployment(
            _make_mock_model(0.3),
            _make_mock_model(0.4),
        )

        for _ in range(10):
            shadow.predict(_make_features())

        summary = shadow.get_summary()

        assert isinstance(summary, ShadowComparisonSummary)
        assert summary.n_predictions == 10
        assert summary.mean_probability_delta == pytest.approx(0.1, abs=0.01)
        assert summary.production_mean_prob == pytest.approx(0.3, abs=0.01)
        assert summary.candidate_mean_prob == pytest.approx(0.4, abs=0.01)

    def test_stop_returns_summary(self) -> None:
        shadow = ShadowDeployment(
            _make_mock_model(0.3),
            _make_mock_model(0.4),
        )
        shadow.predict(_make_features())
        summary = shadow.stop()

        assert isinstance(summary, ShadowComparisonSummary)
        assert shadow.is_active is False

    def test_empty_summary(self) -> None:
        shadow = ShadowDeployment(
            _make_mock_model(0.3),
            _make_mock_model(0.4),
        )
        summary = shadow.get_summary()
        assert summary.n_predictions == 0
