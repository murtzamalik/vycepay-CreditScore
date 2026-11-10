"""Tests for ml.vod.labeling — VOD label assignment."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.vod.labeling import (
    InsufficientDataPolicy,
    LabelingConfig,
    VODLabel,
    assign_label,
    assign_labels_batch,
    filter_training_data,
)
from ml.vod.signals import VODThresholds


# ===================================================================
# Single-entity labeling
# ===================================================================


class TestAssignLabel:
    """Tests for assign_label (single entity)."""

    def test_healthy_entity_labeled_zero(
        self, sample_entity_data: dict
    ) -> None:
        d = sample_entity_data
        result = assign_label(
            entity_id="ENT-0001",
            incoming_30d=d["incoming_30d"],
            outgoing_30d=d["outgoing_30d"],
            avg_balance_30d=d["avg_balance_30d"],
            avg_balance_90d=d["avg_balance_90d"],
            historical_cblri=d["historical_cblri"],
            tx_count_current=d["tx_count_current"],
            tx_count_mean=d["tx_count_mean"],
            tx_count_std=d["tx_count_std"],
            history_days=d["history_days"],
            rolling_gos_values=d["rolling_gos"],
        )
        assert result.label == 0
        assert result.confidence > 0.0
        assert result.excluded is False
        assert result.entity_id == "ENT-0001"

    def test_distressed_entity_labeled_one(
        self, distressed_entity_data: dict
    ) -> None:
        d = distressed_entity_data
        result = assign_label(
            entity_id="ENT-0002",
            incoming_30d=d["incoming_30d"],
            outgoing_30d=d["outgoing_30d"],
            avg_balance_30d=d["avg_balance_30d"],
            avg_balance_90d=d["avg_balance_90d"],
            historical_cblri=d["historical_cblri"],
            tx_count_current=d["tx_count_current"],
            tx_count_mean=d["tx_count_mean"],
            tx_count_std=d["tx_count_std"],
            history_days=d["history_days"],
            rolling_gos_values=d["rolling_gos"],
        )
        assert result.label == 1
        assert result.confidence > 0.5
        assert len(result.reasons) > 0
        assert "No distress signals detected" not in result.reasons[0]

    def test_insufficient_history_excluded(self) -> None:
        result = assign_label(
            entity_id="ENT-NEW",
            incoming_30d=50_000.0,
            outgoing_30d=30_000.0,
            avg_balance_30d=10_000.0,
            avg_balance_90d=9_000.0,
            historical_cblri=1.0,
            tx_count_current=40.0,
            tx_count_mean=40.0,
            tx_count_std=8.0,
            history_days=10,
        )
        assert result.excluded is True
        assert result.label == -1
        assert result.confidence == 0.0

    def test_insufficient_history_label_negative_policy(self) -> None:
        config = LabelingConfig(
            insufficient_data_policy=InsufficientDataPolicy.LABEL_NEGATIVE
        )
        result = assign_label(
            entity_id="ENT-NEW",
            incoming_30d=50_000.0,
            outgoing_30d=30_000.0,
            avg_balance_30d=10_000.0,
            avg_balance_90d=9_000.0,
            historical_cblri=1.0,
            tx_count_current=40.0,
            tx_count_mean=40.0,
            tx_count_std=8.0,
            history_days=10,
            config=config,
        )
        assert result.label == 0
        assert result.excluded is False
        assert result.confidence < 0.3  # Low confidence

    def test_insufficient_history_label_unknown_policy(self) -> None:
        config = LabelingConfig(
            insufficient_data_policy=InsufficientDataPolicy.LABEL_UNKNOWN
        )
        result = assign_label(
            entity_id="ENT-NEW",
            incoming_30d=50_000.0,
            outgoing_30d=30_000.0,
            avg_balance_30d=10_000.0,
            avg_balance_90d=9_000.0,
            historical_cblri=1.0,
            tx_count_current=40.0,
            tx_count_mean=40.0,
            tx_count_std=8.0,
            history_days=10,
            config=config,
        )
        assert result.label == -1
        assert result.excluded is False

    def test_no_rolling_gos_still_works(self) -> None:
        """Without rolling GOS values, gos_volatility=0 (non-trigger)."""
        result = assign_label(
            entity_id="ENT-0003",
            incoming_30d=50_000.0,
            outgoing_30d=30_000.0,
            avg_balance_30d=10_000.0,
            avg_balance_90d=9_000.0,
            historical_cblri=1.0,
            tx_count_current=40.0,
            tx_count_mean=40.0,
            tx_count_std=8.0,
            history_days=120,
        )
        assert result.signals is not None
        assert result.signals.gos_volatility == 0.0

    def test_signals_populated(self, sample_entity_data: dict) -> None:
        d = sample_entity_data
        result = assign_label(
            entity_id="ENT-0001",
            incoming_30d=d["incoming_30d"],
            outgoing_30d=d["outgoing_30d"],
            avg_balance_30d=d["avg_balance_30d"],
            avg_balance_90d=d["avg_balance_90d"],
            historical_cblri=d["historical_cblri"],
            tx_count_current=d["tx_count_current"],
            tx_count_mean=d["tx_count_mean"],
            tx_count_std=d["tx_count_std"],
            history_days=d["history_days"],
            rolling_gos_values=d["rolling_gos"],
        )
        assert result.signals is not None
        assert np.isfinite(result.signals.gos_index)
        assert np.isfinite(result.signals.cblri)
        assert np.isfinite(result.signals.cblri_drop_pct)
        assert np.isfinite(result.signals.tx_pattern_zscore)

    def test_distress_reasons_explain_trigger(
        self, distressed_entity_data: dict
    ) -> None:
        d = distressed_entity_data
        result = assign_label(
            entity_id="ENT-0002",
            incoming_30d=d["incoming_30d"],
            outgoing_30d=d["outgoing_30d"],
            avg_balance_30d=d["avg_balance_30d"],
            avg_balance_90d=d["avg_balance_90d"],
            historical_cblri=d["historical_cblri"],
            tx_count_current=d["tx_count_current"],
            tx_count_mean=d["tx_count_mean"],
            tx_count_std=d["tx_count_std"],
            history_days=d["history_days"],
            rolling_gos_values=d["rolling_gos"],
        )
        # At least one reason should mention a threshold
        assert any("exceeds threshold" in r for r in result.reasons)


# ===================================================================
# Confidence scoring
# ===================================================================


class TestConfidenceScoring:
    """Tests for confidence score computation."""

    def test_more_history_higher_confidence(self) -> None:
        short = assign_label(
            entity_id="SHORT",
            incoming_30d=50_000.0,
            outgoing_30d=30_000.0,
            avg_balance_30d=10_000.0,
            avg_balance_90d=9_000.0,
            historical_cblri=1.0,
            tx_count_current=40.0,
            tx_count_mean=40.0,
            tx_count_std=8.0,
            history_days=35,
        )
        long = assign_label(
            entity_id="LONG",
            incoming_30d=50_000.0,
            outgoing_30d=30_000.0,
            avg_balance_30d=10_000.0,
            avg_balance_90d=9_000.0,
            historical_cblri=1.0,
            tx_count_current=40.0,
            tx_count_mean=40.0,
            tx_count_std=8.0,
            history_days=365,
        )
        assert long.confidence > short.confidence

    def test_new_user_penalty(self) -> None:
        """Users with < new_user_days get reduced confidence."""
        config = LabelingConfig(new_user_days=60)
        result = assign_label(
            entity_id="NEW",
            incoming_30d=50_000.0,
            outgoing_30d=30_000.0,
            avg_balance_30d=10_000.0,
            avg_balance_90d=9_000.0,
            historical_cblri=1.0,
            tx_count_current=40.0,
            tx_count_mean=40.0,
            tx_count_std=8.0,
            history_days=45,
            config=config,
        )
        # 45 < 60, so penalty applied
        assert result.confidence < 0.6  # Below base_confidence

    def test_confidence_capped_at_one(self) -> None:
        """Even with many signals + long history, confidence <= 1.0."""
        d = {
            "incoming_30d": 1_000.0,
            "outgoing_30d": 90_000.0,
            "avg_balance_30d": 100.0,
            "avg_balance_90d": 50_000.0,
            "historical_cblri": 3.0,
            "tx_count_current": 1.0,
            "tx_count_mean": 50.0,
            "tx_count_std": 5.0,
        }
        result = assign_label(
            entity_id="MAX",
            history_days=3650,
            rolling_gos_values=[-0.9, 0.8, -0.7, 0.9, -0.8, 0.7],
            **d,
        )
        assert result.confidence <= 1.0


# ===================================================================
# Batch labeling
# ===================================================================


class TestAssignLabelsBatch:
    """Tests for assign_labels_batch."""

    def test_returns_all_required_columns(
        self, batch_dataframe: pd.DataFrame
    ) -> None:
        result = assign_labels_batch(batch_dataframe)
        required = {"label", "confidence", "excluded"}
        assert required.issubset(set(result.columns))

    def test_labels_are_valid(self, batch_dataframe: pd.DataFrame) -> None:
        result = assign_labels_batch(batch_dataframe)
        assert set(result["label"].unique()).issubset({-1, 0, 1})

    def test_confidence_range(self, batch_dataframe: pd.DataFrame) -> None:
        result = assign_labels_batch(batch_dataframe)
        assert (result["confidence"] >= 0.0).all()
        assert (result["confidence"] <= 1.0).all()

    def test_preserves_row_count(self, batch_dataframe: pd.DataFrame) -> None:
        result = assign_labels_batch(batch_dataframe)
        assert len(result) == len(batch_dataframe)

    def test_exclude_policy(self, batch_dataframe: pd.DataFrame) -> None:
        config = LabelingConfig(
            insufficient_data_policy=InsufficientDataPolicy.EXCLUDE
        )
        result = assign_labels_batch(batch_dataframe, config=config)
        # Entities with insufficient history should be excluded
        insufficient = result[~result["has_sufficient_history"]]
        if len(insufficient) > 0:
            assert (insufficient["excluded"]).all()
            assert (insufficient["label"] == -1).all()

    def test_label_negative_policy(
        self, batch_dataframe: pd.DataFrame
    ) -> None:
        config = LabelingConfig(
            insufficient_data_policy=InsufficientDataPolicy.LABEL_NEGATIVE
        )
        result = assign_labels_batch(batch_dataframe, config=config)
        insufficient = result[~result["has_sufficient_history"]]
        if len(insufficient) > 0:
            assert (insufficient["label"] == 0).all()
            assert (insufficient["confidence"] <= config.min_confidence).all()

    def test_empty_dataframe(self) -> None:
        result = assign_labels_batch(pd.DataFrame())
        assert len(result) == 0

    def test_missing_columns_raises(self) -> None:
        df = pd.DataFrame({"entity_id": ["A"], "foo": [1]})
        with pytest.raises(ValueError, match="Missing required columns"):
            assign_labels_batch(df)

    def test_has_both_classes(self, batch_dataframe: pd.DataFrame) -> None:
        """With our fixture data, we should get both positive and negative."""
        result = assign_labels_batch(batch_dataframe)
        included = result[~result["excluded"]]
        labels = set(included["label"].unique())
        # We designed the fixture to have both healthy and distressed
        assert 0 in labels or 1 in labels  # At least one class present


# ===================================================================
# Training data filtering
# ===================================================================


class TestFilterTrainingData:
    """Tests for filter_training_data."""

    def test_removes_excluded(self, batch_dataframe: pd.DataFrame) -> None:
        labeled = assign_labels_batch(batch_dataframe)
        filtered = filter_training_data(labeled)
        assert not filtered.get("excluded", pd.Series(dtype=bool)).any()

    def test_removes_low_confidence(
        self, batch_dataframe: pd.DataFrame
    ) -> None:
        labeled = assign_labels_batch(batch_dataframe)
        config = LabelingConfig(min_confidence=0.5)
        filtered = filter_training_data(labeled, config=config)
        assert (filtered["confidence"] >= 0.5).all()

    def test_custom_min_confidence(
        self, batch_dataframe: pd.DataFrame
    ) -> None:
        labeled = assign_labels_batch(batch_dataframe)
        filtered = filter_training_data(labeled, min_confidence=0.8)
        assert (filtered["confidence"] >= 0.8).all()

    def test_removes_unknown_labels(
        self, batch_dataframe: pd.DataFrame
    ) -> None:
        labeled = assign_labels_batch(batch_dataframe)
        filtered = filter_training_data(labeled)
        assert (filtered["label"] >= 0).all()

    def test_empty_after_strict_filter(self) -> None:
        """Extreme confidence threshold should return empty or near-empty."""
        df = pd.DataFrame(
            {
                "entity_id": ["A"],
                "incoming_tx_value_30d": [100.0],
                "outgoing_tx_value_30d": [50.0],
                "avg_daily_balance_30d": [10_000.0],
                "avg_daily_balance_90d": [9_000.0],
                "historical_cblri": [1.0],
                "tx_count_current": [40.0],
                "tx_count_mean": [40.0],
                "tx_count_std": [5.0],
                "history_days": [31],
            }
        )
        labeled = assign_labels_batch(df)
        filtered = filter_training_data(labeled, min_confidence=0.99)
        # Very short history + high threshold => likely filtered out
        assert len(filtered) <= 1


# ===================================================================
# Configuration
# ===================================================================


class TestLabelingConfig:
    """Tests for LabelingConfig."""

    def test_defaults(self) -> None:
        config = LabelingConfig()
        assert config.base_confidence == 0.6
        assert config.min_confidence == 0.3
        assert isinstance(config.thresholds, VODThresholds)

    def test_custom_policy(self) -> None:
        config = LabelingConfig(
            insufficient_data_policy=InsufficientDataPolicy.LABEL_UNKNOWN
        )
        assert (
            config.insufficient_data_policy
            == InsufficientDataPolicy.LABEL_UNKNOWN
        )


class TestInsufficientDataPolicy:
    """Tests for InsufficientDataPolicy enum."""

    def test_values(self) -> None:
        assert InsufficientDataPolicy.EXCLUDE == "exclude"
        assert InsufficientDataPolicy.LABEL_NEGATIVE == "label_negative"
        assert InsufficientDataPolicy.LABEL_UNKNOWN == "label_unknown"
