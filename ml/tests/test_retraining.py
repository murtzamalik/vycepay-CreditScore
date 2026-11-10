"""Tests for ml.active_learning.retraining module."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.active_learning.ground_truth import GroundTruthStats
from ml.active_learning.retraining import (
    RetrainingConfig,
    RetrainingOutcome,
    RetrainingResult,
    assemble_training_data,
)
from ml.training.pipeline import CORE_FEATURES, TARGET_COLUMN


def _make_vod_df(n: int = 50) -> pd.DataFrame:
    """Create a VOD-labeled DataFrame."""
    np.random.seed(42)
    data = {
        "entity_id": [f"ent_{i:04d}" for i in range(n)],
        "label": np.random.choice([0, 1], size=n, p=[0.8, 0.2]),
        "confidence": np.random.uniform(0.5, 1.0, n),
        "label_source": ["vod"] * n,
    }
    for feat in CORE_FEATURES:
        data[feat] = np.random.uniform(0, 1, n)
    return pd.DataFrame(data)


def _make_feedback_df(n: int = 20) -> pd.DataFrame:
    """Create a feedback DataFrame."""
    np.random.seed(99)
    dpds = np.random.choice([0, 30, 60, 90, 120], size=n)
    return pd.DataFrame(
        {
            "national_id_hash": [f"ent_{i + 50:04d}" for i in range(n)],
            "dpd": dpds,
            "is_default": dpds >= 90,
            "loan_outcome": np.where(dpds >= 90, "default", "performing"),
            "disbursement_date": pd.to_datetime("2025-01-01"),
            "outcome_date": pd.to_datetime("2025-09-01"),
            "partner_id": "bank_a",
        }
    )


def _make_feature_df(entity_ids: list[str]) -> pd.DataFrame:
    """Create a feature DataFrame for given entity IDs."""
    np.random.seed(123)
    n = len(entity_ids)
    data = {"entity_id": entity_ids}
    for feat in CORE_FEATURES:
        data[feat] = np.random.uniform(0, 1, n)
    return pd.DataFrame(data)


class TestAssembleTrainingData:
    """Tests for assemble_training_data."""

    def test_assembles_from_vod_and_feedback(self) -> None:
        vod_df = _make_vod_df(50)
        feedback_df = _make_feedback_df(20)

        # Feature df needs to cover all entity IDs
        all_ids = list(vod_df["entity_id"]) + [f"ent_{i + 50:04d}" for i in range(20)]
        feature_df = _make_feature_df(all_ids)

        result, stats = assemble_training_data(vod_df, feedback_df, feature_df)

        assert isinstance(stats, GroundTruthStats)
        assert len(result) > 0
        assert TARGET_COLUMN in result.columns

    def test_empty_feedback(self) -> None:
        vod_df = _make_vod_df(50)
        feedback_df = pd.DataFrame()
        feature_df = _make_feature_df(list(vod_df["entity_id"]))

        result, stats = assemble_training_data(vod_df, feedback_df, feature_df)

        assert len(result) > 0  # Should still have VOD data
        assert stats.total_ground_truth == 0

    def test_empty_vod(self) -> None:
        vod_df = pd.DataFrame(
            columns=["entity_id", "label", "confidence", "label_source"]
        )
        feedback_df = _make_feedback_df(20)
        entity_ids = [f"ent_{i + 50:04d}" for i in range(20)]
        feature_df = _make_feature_df(entity_ids)

        result, stats = assemble_training_data(vod_df, feedback_df, feature_df)

        assert len(result) > 0
        assert stats.total_vod == 0

    def test_requires_feature_columns(self) -> None:
        vod_df = _make_vod_df(10)
        feedback_df = pd.DataFrame()
        # Feature df with wrong columns
        feature_df = pd.DataFrame(
            {"entity_id": vod_df["entity_id"], "wrong_col": range(10)}
        )

        result, _ = assemble_training_data(vod_df, feedback_df, feature_df)
        assert len(result) == 0  # No matching features


class TestRetrainingConfig:
    """Tests for RetrainingConfig."""

    def test_defaults(self) -> None:
        config = RetrainingConfig()
        assert config.min_total_samples == 500
        assert config.min_ground_truth_samples == 100
        assert config.min_improvement_auc == 0.005

    def test_custom_config(self) -> None:
        config = RetrainingConfig(
            min_total_samples=1000,
            min_improvement_auc=0.01,
        )
        assert config.min_total_samples == 1000


class TestRetrainingResult:
    """Tests for RetrainingResult."""

    def test_outcome_enum(self) -> None:
        result = RetrainingResult(
            outcome=RetrainingOutcome.INSUFFICIENT_DATA,
            message="Not enough data",
        )
        assert result.outcome == RetrainingOutcome.INSUFFICIENT_DATA
        assert result.training_result is None

    def test_timestamp_is_set(self) -> None:
        result = RetrainingResult(
            outcome=RetrainingOutcome.SUCCESS,
        )
        assert result.timestamp is not None
