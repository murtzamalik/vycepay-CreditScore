"""Ground truth integration for Phase 2 active learning.

Merges partner bank loan outcomes (from the ``loan_feedback`` table) with
VOD proxy labels to produce combined training data.  Each sample is tagged
with its label source so the pipeline can track the transition from
VOD-only to ground-truth-enriched training.

Label semantics:
    - ``label_source = "vod"``: Proxy label derived from Vyce-Observed Distress.
    - ``label_source = "ground_truth"``: Actual loan outcome from partner bank.
    - ``label_source = "merged"``: Sample has both; ground truth takes precedence.

Binary target:
    - 1 = Serious Delinquency (DPD >= 90 within 12 months)
    - 0 = Performing
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class LabelSource(str, Enum):
    """Origin of a training label."""

    VOD = "vod"
    GROUND_TRUTH = "ground_truth"
    MERGED = "merged"


@dataclass(frozen=True)
class GroundTruthConfig:
    """Configuration for ground truth integration.

    Attributes:
        dpd_threshold: Days-past-due threshold for default classification.
        min_observation_days: Minimum days between disbursement and outcome
            to consider the observation mature enough.
        prefer_ground_truth: When both VOD and ground truth exist for the
            same subject, prefer ground truth.
        confidence_ground_truth: Default confidence for ground truth labels.
        confidence_vod: Default confidence for VOD labels (when merging).
    """

    dpd_threshold: int = 90
    min_observation_days: int = 60
    prefer_ground_truth: bool = True
    confidence_ground_truth: float = 0.95
    confidence_vod: float = 0.70


@dataclass
class GroundTruthStats:
    """Statistics from a ground truth integration run."""

    total_ground_truth: int = 0
    total_vod: int = 0
    total_merged: int = 0
    ground_truth_positive_rate: float = 0.0
    vod_positive_rate: float = 0.0
    merged_positive_rate: float = 0.0
    agreement_rate: float = 0.0
    conflicts_resolved: int = 0


def convert_loan_outcomes_to_labels(
    feedback_df: pd.DataFrame,
    config: GroundTruthConfig | None = None,
) -> pd.DataFrame:
    """Convert partner bank loan outcomes to binary training labels.

    Expected columns in ``feedback_df``:
        - ``national_id_hash``: Hashed subject identifier.
        - ``dpd`` (or ``days_past_due``): Days past due.
        - ``is_default``: Boolean default flag.
        - ``disbursement_date``: Date of loan disbursement.
        - ``outcome_date``: Date of outcome observation.
        - ``loan_outcome``: Outcome string (performing, default, etc.).

    Returns:
        DataFrame with columns: ``entity_id``, ``label``, ``confidence``,
        ``label_source``, ``dpd``, ``loan_outcome``.
    """
    if config is None:
        config = GroundTruthConfig()

    if feedback_df.empty:
        return _empty_ground_truth_df()

    df = feedback_df.copy()

    # Normalise column names
    if "days_past_due" in df.columns and "dpd" not in df.columns:
        df = df.rename(columns={"days_past_due": "dpd"})

    # Filter for mature observations
    if "disbursement_date" in df.columns and "outcome_date" in df.columns:
        df["disbursement_date"] = pd.to_datetime(df["disbursement_date"])
        df["outcome_date"] = pd.to_datetime(df["outcome_date"])
        observation_days = (df["outcome_date"] - df["disbursement_date"]).dt.days
        mature_mask = observation_days >= config.min_observation_days
        n_immature = (~mature_mask).sum()
        if n_immature > 0:
            logger.info(
                "Filtered %d immature observations (< %d days).",
                n_immature,
                config.min_observation_days,
            )
        df = df[mature_mask].copy()

    if df.empty:
        return _empty_ground_truth_df()

    # Assign binary label: 1 if DPD >= threshold OR is_default, else 0
    df["label"] = np.where(
        (df["dpd"] >= config.dpd_threshold)
        | (df.get("is_default", pd.Series(False, index=df.index)).astype(bool)),
        1,
        0,
    )
    df["confidence"] = config.confidence_ground_truth
    df["label_source"] = LabelSource.GROUND_TRUTH.value

    # Use national_id_hash as entity_id
    if "national_id_hash" in df.columns:
        df = df.rename(columns={"national_id_hash": "entity_id"})

    # Deduplicate: keep the latest outcome per entity
    if "outcome_date" in df.columns:
        df = df.sort_values("outcome_date", ascending=False)
    df = df.drop_duplicates(subset=["entity_id"], keep="first")

    result_cols = [
        "entity_id", "label", "confidence", "label_source", "dpd",
    ]
    if "loan_outcome" in df.columns:
        result_cols.append("loan_outcome")

    available = [c for c in result_cols if c in df.columns]
    result = df[available].reset_index(drop=True)

    logger.info(
        "Converted %d loan outcomes to labels: %.1f%% positive.",
        len(result),
        result["label"].mean() * 100 if len(result) > 0 else 0.0,
    )

    return result


def merge_labels(
    vod_df: pd.DataFrame,
    ground_truth_df: pd.DataFrame,
    config: GroundTruthConfig | None = None,
) -> tuple[pd.DataFrame, GroundTruthStats]:
    """Merge VOD proxy labels with ground truth loan outcome labels.

    When a subject has both VOD and ground truth labels, the ground truth
    label takes precedence (if ``config.prefer_ground_truth`` is True).

    Args:
        vod_df: VOD-labeled data with at least ``entity_id`` and ``label``.
        ground_truth_df: Ground truth labeled data from
            ``convert_loan_outcomes_to_labels``.
        config: Ground truth configuration.

    Returns:
        Tuple of (merged DataFrame, statistics).
    """
    if config is None:
        config = GroundTruthConfig()

    stats = GroundTruthStats()

    # Prepare VOD labels
    vod = vod_df.copy()
    if "label_source" not in vod.columns:
        vod["label_source"] = LabelSource.VOD.value
    if "confidence" not in vod.columns:
        vod["confidence"] = config.confidence_vod

    # Prepare ground truth labels
    gt = ground_truth_df.copy()
    if "label_source" not in gt.columns:
        gt["label_source"] = LabelSource.GROUND_TRUTH.value

    stats.total_vod = len(vod)
    stats.total_ground_truth = len(gt)

    if len(vod) > 0:
        stats.vod_positive_rate = float(vod["label"].mean())
    if len(gt) > 0:
        stats.ground_truth_positive_rate = float(gt["label"].mean())

    # Identify overlapping entities
    vod_entities = set(vod["entity_id"].unique())
    gt_entities = set(gt["entity_id"].unique())
    overlap = vod_entities & gt_entities

    if overlap:
        # Check agreement on overlapping entities
        vod_overlap = vod[vod["entity_id"].isin(overlap)].set_index("entity_id")
        gt_overlap = gt[gt["entity_id"].isin(overlap)].set_index("entity_id")

        common_ids = vod_overlap.index.intersection(gt_overlap.index)
        if len(common_ids) > 0:
            agreements = (
                vod_overlap.loc[common_ids, "label"].values
                == gt_overlap.loc[common_ids, "label"].values
            )
            stats.agreement_rate = float(np.mean(agreements))
            stats.conflicts_resolved = int(np.sum(~agreements))

        logger.info(
            "Label overlap: %d entities. Agreement rate: %.1f%%. "
            "Conflicts resolved (ground truth preferred): %d.",
            len(overlap),
            stats.agreement_rate * 100,
            stats.conflicts_resolved,
        )

    if config.prefer_ground_truth:
        # Ground truth entities override VOD
        vod_only = vod[~vod["entity_id"].isin(gt_entities)].copy()
        gt_all = gt.copy()

        # Mark overlapping ground truth entries as "merged"
        gt_all.loc[gt_all["entity_id"].isin(overlap), "label_source"] = (
            LabelSource.MERGED.value
        )

        merged = pd.concat([vod_only, gt_all], ignore_index=True)
    else:
        # Keep all, with VOD taking precedence
        gt_only = gt[~gt["entity_id"].isin(vod_entities)].copy()
        vod_all = vod.copy()
        vod_all.loc[vod_all["entity_id"].isin(overlap), "label_source"] = (
            LabelSource.MERGED.value
        )
        merged = pd.concat([vod_all, gt_only], ignore_index=True)

    stats.total_merged = len(merged)
    if len(merged) > 0:
        stats.merged_positive_rate = float(merged["label"].mean())

    logger.info(
        "Merge complete: %d VOD + %d ground truth -> %d merged samples. "
        "Positive rate: %.1f%%.",
        stats.total_vod,
        stats.total_ground_truth,
        stats.total_merged,
        stats.merged_positive_rate * 100,
    )

    return merged, stats


def _empty_ground_truth_df() -> pd.DataFrame:
    """Return an empty DataFrame with the ground truth schema."""
    return pd.DataFrame(
        columns=["entity_id", "label", "confidence", "label_source", "dpd"]
    )
