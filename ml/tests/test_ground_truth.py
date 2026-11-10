"""Tests for ml.active_learning.ground_truth module."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.active_learning.ground_truth import (
    GroundTruthConfig,
    GroundTruthStats,
    LabelSource,
    convert_loan_outcomes_to_labels,
    merge_labels,
)


@pytest.fixture()
def feedback_df() -> pd.DataFrame:
    """Sample loan feedback data."""
    return pd.DataFrame(
        {
            "national_id_hash": [
                "hash_aaa",
                "hash_bbb",
                "hash_ccc",
                "hash_ddd",
                "hash_eee",
            ],
            "dpd": [0, 30, 90, 120, 0],
            "is_default": [False, False, True, True, False],
            "loan_outcome": [
                "performing",
                "performing",
                "default",
                "default",
                "performing",
            ],
            "disbursement_date": pd.to_datetime(
                [
                    "2025-01-01",
                    "2025-02-01",
                    "2025-03-01",
                    "2025-01-15",
                    "2025-04-01",
                ]
            ),
            "outcome_date": pd.to_datetime(
                [
                    "2025-07-01",
                    "2025-08-01",
                    "2025-09-01",
                    "2025-09-15",
                    "2025-10-01",
                ]
            ),
            "partner_id": ["bank_a"] * 5,
        }
    )


@pytest.fixture()
def vod_df() -> pd.DataFrame:
    """Sample VOD labeled data."""
    return pd.DataFrame(
        {
            "entity_id": [
                "hash_aaa",
                "hash_bbb",
                "hash_fff",
                "hash_ggg",
            ],
            "label": [0, 1, 1, 0],
            "confidence": [0.7, 0.6, 0.8, 0.7],
            "label_source": ["vod"] * 4,
        }
    )


class TestConvertLoanOutcomesToLabels:
    """Tests for convert_loan_outcomes_to_labels."""

    def test_converts_feedback_to_binary_labels(self, feedback_df: pd.DataFrame) -> None:
        result = convert_loan_outcomes_to_labels(feedback_df)

        assert len(result) > 0
        assert "entity_id" in result.columns
        assert "label" in result.columns
        assert "label_source" in result.columns
        assert set(result["label"].unique()).issubset({0, 1})

    def test_default_threshold_90_dpd(self, feedback_df: pd.DataFrame) -> None:
        result = convert_loan_outcomes_to_labels(feedback_df)

        # DPD >= 90 should be label=1
        defaults = result[result["label"] == 1]
        assert len(defaults) >= 2  # hash_ccc and hash_ddd

        # DPD < 90 should be label=0
        performing = result[result["label"] == 0]
        assert len(performing) >= 2

    def test_filters_immature_observations(self) -> None:
        """Observations with too short a window should be filtered out."""
        df = pd.DataFrame(
            {
                "national_id_hash": ["hash_x"],
                "dpd": [0],
                "is_default": [False],
                "disbursement_date": pd.to_datetime(["2025-09-01"]),
                "outcome_date": pd.to_datetime(["2025-09-15"]),  # Only 14 days
                "partner_id": ["bank_a"],
            }
        )
        config = GroundTruthConfig(min_observation_days=60)
        result = convert_loan_outcomes_to_labels(df, config)
        assert len(result) == 0

    def test_empty_feedback_returns_empty(self) -> None:
        result = convert_loan_outcomes_to_labels(pd.DataFrame())
        assert len(result) == 0
        assert "entity_id" in result.columns

    def test_label_source_is_ground_truth(self, feedback_df: pd.DataFrame) -> None:
        result = convert_loan_outcomes_to_labels(feedback_df)
        assert (result["label_source"] == LabelSource.GROUND_TRUTH.value).all()

    def test_deduplicates_by_entity(self) -> None:
        """Multiple outcomes for the same entity should keep only the latest."""
        df = pd.DataFrame(
            {
                "national_id_hash": ["hash_x", "hash_x"],
                "dpd": [0, 120],
                "is_default": [False, True],
                "disbursement_date": pd.to_datetime(["2025-01-01", "2025-01-01"]),
                "outcome_date": pd.to_datetime(["2025-07-01", "2025-09-01"]),
                "partner_id": ["bank_a", "bank_a"],
            }
        )
        result = convert_loan_outcomes_to_labels(df)
        assert len(result) == 1


class TestMergeLabels:
    """Tests for merge_labels."""

    def test_merges_vod_and_ground_truth(
        self, vod_df: pd.DataFrame, feedback_df: pd.DataFrame
    ) -> None:
        gt_df = convert_loan_outcomes_to_labels(feedback_df)
        merged, stats = merge_labels(vod_df, gt_df)

        assert len(merged) > 0
        assert isinstance(stats, GroundTruthStats)

    def test_ground_truth_takes_precedence_on_overlap(
        self, vod_df: pd.DataFrame
    ) -> None:
        """When an entity has both VOD and GT labels, GT should win."""
        gt_df = pd.DataFrame(
            {
                "entity_id": ["hash_aaa", "hash_bbb"],
                "label": [1, 0],  # Different from VOD
                "confidence": [0.95, 0.95],
                "label_source": ["ground_truth", "ground_truth"],
            }
        )
        config = GroundTruthConfig(prefer_ground_truth=True)
        merged, stats = merge_labels(vod_df, gt_df, config)

        # Ground truth should override VOD for hash_aaa and hash_bbb
        aaa_row = merged[merged["entity_id"] == "hash_aaa"]
        assert len(aaa_row) == 1
        assert aaa_row.iloc[0]["label"] == 1  # GT label

    def test_stats_track_overlap(self, vod_df: pd.DataFrame) -> None:
        gt_df = pd.DataFrame(
            {
                "entity_id": ["hash_aaa"],
                "label": [1],
                "confidence": [0.95],
                "label_source": ["ground_truth"],
            }
        )
        _, stats = merge_labels(vod_df, gt_df)

        assert stats.total_vod == len(vod_df)
        assert stats.total_ground_truth == 1
        assert stats.total_merged > 0

    def test_empty_gt_returns_vod_only(self, vod_df: pd.DataFrame) -> None:
        gt_df = pd.DataFrame(
            columns=["entity_id", "label", "confidence", "label_source"]
        )
        merged, stats = merge_labels(vod_df, gt_df)
        assert len(merged) == len(vod_df)
        assert stats.total_ground_truth == 0

    def test_empty_vod_returns_gt_only(self) -> None:
        vod_df = pd.DataFrame(
            columns=["entity_id", "label", "confidence", "label_source"]
        )
        gt_df = pd.DataFrame(
            {
                "entity_id": ["hash_x"],
                "label": [1],
                "confidence": [0.9],
                "label_source": ["ground_truth"],
            }
        )
        merged, stats = merge_labels(vod_df, gt_df)
        assert len(merged) == 1
        assert stats.total_vod == 0
