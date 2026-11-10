"""VOD (Vyce-Observed Distress) label assignment for training data.

Translates raw VOD distress signals into binary classification labels
suitable for model training.  This is the Phase 1 labeling strategy —
before ground-truth loan outcomes are available from partner banks,
we use observed behavioral distress as a proxy for credit risk.

Label semantics:
    - **1 (positive class)**: Entity exhibits distress signals.
      Treated as high-risk / likely to default.
    - **0 (negative class)**: No distress signals detected.
      Treated as low-risk / likely to perform.

Each label is accompanied by a confidence score reflecting data quality
and signal strength.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Union

import numpy as np
import pandas as pd

from ml.vod.signals import (
    VODSignalResult,
    VODThresholds,
    compute_cblri,
    compute_cblri_drop_percent,
    compute_gos_index,
    compute_gos_volatility,
    compute_signals_from_dataframe,
    compute_tx_pattern_zscore,
    compute_vod_flag,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class InsufficientDataPolicy(str, Enum):
    """How to handle entities with insufficient transaction history.

    Attributes:
        EXCLUDE: Drop them from the labeled dataset entirely.
        LABEL_NEGATIVE: Assign label=0 with low confidence.
        LABEL_UNKNOWN: Assign label=-1 (to be filtered downstream).
    """

    EXCLUDE = "exclude"
    LABEL_NEGATIVE = "label_negative"
    LABEL_UNKNOWN = "label_unknown"


@dataclass(frozen=True)
class LabelingConfig:
    """Configuration for VOD label assignment.

    Attributes:
        thresholds: VOD signal thresholds for distress detection.
        insufficient_data_policy: How to handle entities with limited
            history.
        min_confidence: Minimum confidence score to include a label
            in the training set.  Labels below this threshold are
            excluded when ``filter_low_confidence`` is True.
        base_confidence: Starting confidence before adjustments.
            Reduced for edge cases (new users, sparse data).
        confidence_history_bonus: Additional confidence awarded per
            30-day increment of history beyond the minimum threshold.
        confidence_signal_count_bonus: Additional confidence per
            triggered distress signal (for positive labels).
        new_user_days: Entities with fewer than this many days of
            history are considered "new users" and receive reduced
            confidence.
    """

    thresholds: VODThresholds = VODThresholds()
    insufficient_data_policy: InsufficientDataPolicy = (
        InsufficientDataPolicy.EXCLUDE
    )
    min_confidence: float = 0.3
    base_confidence: float = 0.6
    confidence_history_bonus: float = 0.05
    confidence_signal_count_bonus: float = 0.10
    new_user_days: int = 60


# ---------------------------------------------------------------------------
# Single-entity labeling
# ---------------------------------------------------------------------------

@dataclass
class VODLabel:
    """Label result for a single entity.

    Attributes:
        entity_id: Unique identifier for the entity.
        label: Binary label (0=low-risk, 1=high-risk, -1=unknown).
        confidence: Confidence in the label assignment (0.0 to 1.0).
        signals: Underlying VOD signal computation result.
        reasons: Human-readable reasons for the label.
        excluded: Whether this entity should be excluded from training.
    """

    entity_id: str
    label: int
    confidence: float
    signals: VODSignalResult | None
    reasons: list[str]
    excluded: bool = False


def assign_label(
    entity_id: str,
    incoming_30d: float,
    outgoing_30d: float,
    avg_balance_30d: float,
    avg_balance_90d: float,
    historical_cblri: float,
    tx_count_current: float,
    tx_count_mean: float,
    tx_count_std: float,
    history_days: int,
    rolling_gos_values: list[float] | None = None,
    config: LabelingConfig | None = None,
) -> VODLabel:
    """Assign a VOD label to a single entity.

    Computes all distress signals and produces a binary label with
    confidence score.  Handles edge cases (new users, insufficient
    data) according to the configured policy.

    Args:
        entity_id: Unique entity identifier.
        incoming_30d: Total incoming transaction value (last 30 days).
        outgoing_30d: Total outgoing transaction value (last 30 days).
        avg_balance_30d: Average daily balance (last 30 days).
        avg_balance_90d: Average daily balance (last 90 days).
        historical_cblri: Historical baseline CBLRI value.
        tx_count_current: Current-period transaction count.
        tx_count_mean: Historical mean transaction count.
        tx_count_std: Historical std dev of transaction count.
        history_days: Number of days of transaction history available.
        rolling_gos_values: List of GOS values from consecutive
            periods, used for volatility calculation.
        config: Labeling configuration.  Uses defaults if None.

    Returns:
        VODLabel with the assigned label, confidence, and reasoning.
    """
    if config is None:
        config = LabelingConfig()

    thresholds = config.thresholds

    # --- Check data sufficiency ---
    has_sufficient_history = history_days >= thresholds.min_history_days

    if not has_sufficient_history:
        return _handle_insufficient_data(entity_id, history_days, config)

    # --- Compute signals ---
    gos = compute_gos_index(incoming_30d, outgoing_30d)
    cblri = compute_cblri(avg_balance_30d, avg_balance_90d)
    cblri_drop = compute_cblri_drop_percent(cblri, historical_cblri)
    tx_zscore = compute_tx_pattern_zscore(
        tx_count_current, tx_count_mean, tx_count_std
    )

    if rolling_gos_values and len(rolling_gos_values) >= 2:
        gos_vol = compute_gos_volatility(rolling_gos_values)
    else:
        gos_vol = 0.0
        logger.info(
            "Entity %s: insufficient rolling GOS data; "
            "using gos_volatility=0.0.",
            entity_id,
        )

    # --- Determine which thresholds are breached ---
    reasons: list[str] = []
    signal_count = 0

    if gos_vol > thresholds.gos_volatility:
        reasons.append(
            f"GOS volatility ({gos_vol:.3f}) exceeds threshold "
            f"({thresholds.gos_volatility})"
        )
        signal_count += 1

    if cblri_drop > thresholds.cblri_drop_pct:
        reasons.append(
            f"CBLRI drop ({cblri_drop:.1%}) exceeds threshold "
            f"({thresholds.cblri_drop_pct:.0%})"
        )
        signal_count += 1

    if tx_zscore > thresholds.tx_pattern_zscore:
        reasons.append(
            f"Transaction pattern z-score ({tx_zscore:.2f}) exceeds "
            f"threshold ({thresholds.tx_pattern_zscore})"
        )
        signal_count += 1

    # --- Assign label ---
    vod_flag = compute_vod_flag(gos_vol, cblri_drop, tx_zscore, thresholds)
    label = 1 if vod_flag else 0

    if not reasons:
        reasons.append("No distress signals detected.")

    # --- Compute confidence ---
    confidence = _compute_confidence(
        label=label,
        signal_count=signal_count,
        history_days=history_days,
        config=config,
    )

    signals = VODSignalResult(
        gos_index=gos,
        gos_volatility=gos_vol,
        cblri=cblri,
        cblri_drop_pct=cblri_drop,
        tx_pattern_zscore=tx_zscore,
        vod_flag=vod_flag,
        distress_reasons=reasons,
        has_sufficient_history=True,
    )

    return VODLabel(
        entity_id=entity_id,
        label=label,
        confidence=confidence,
        signals=signals,
        reasons=reasons,
    )


# ---------------------------------------------------------------------------
# Batch labeling
# ---------------------------------------------------------------------------

def assign_labels_batch(
    df: pd.DataFrame,
    config: LabelingConfig | None = None,
) -> pd.DataFrame:
    """Assign VOD labels to a batch of entities.

    This is the primary interface for generating training data.  Takes
    a DataFrame of entity features and returns a labeled DataFrame
    ready for model training.

    Required columns (same as ``compute_signals_from_dataframe``):
        - ``entity_id``: Unique entity identifier.
        - ``incoming_tx_value_30d``
        - ``outgoing_tx_value_30d``
        - ``avg_daily_balance_30d``
        - ``avg_daily_balance_90d``
        - ``historical_cblri``
        - ``tx_count_current``
        - ``tx_count_mean``
        - ``tx_count_std``
        - ``history_days``
        - ``gos_period_1`` ... ``gos_period_N`` (optional)

    Args:
        df: Input DataFrame with required columns.
        config: Labeling configuration.  Uses defaults if None.

    Returns:
        DataFrame with additional columns:
        ``label`` (int), ``confidence`` (float),
        ``excluded`` (bool), plus all signal columns from
        ``compute_signals_from_dataframe``.
    """
    if config is None:
        config = LabelingConfig()

    if df.empty:
        logger.warning("Empty DataFrame passed to assign_labels_batch.")
        return _empty_labeled_dataframe()

    # Validate required columns
    required_cols = {
        "entity_id",
        "incoming_tx_value_30d",
        "outgoing_tx_value_30d",
        "avg_daily_balance_30d",
        "avg_daily_balance_90d",
        "historical_cblri",
        "tx_count_current",
        "tx_count_mean",
        "tx_count_std",
        "history_days",
    }
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(
            f"Missing required columns for VOD labeling: {sorted(missing)}"
        )

    # Compute all signals
    signals_df = compute_signals_from_dataframe(df, config.thresholds)

    # --- Assign labels ---
    signals_df["label"] = np.where(signals_df["vod_flag"], 1, 0)

    # --- Handle insufficient history ---
    insufficient_mask = ~signals_df["has_sufficient_history"]
    n_insufficient = insufficient_mask.sum()

    if n_insufficient > 0:
        logger.info(
            "%d entities have insufficient history (<%d days).",
            n_insufficient,
            config.thresholds.min_history_days,
        )

    policy = config.insufficient_data_policy

    if policy == InsufficientDataPolicy.EXCLUDE:
        signals_df.loc[insufficient_mask, "label"] = -1
        signals_df["excluded"] = insufficient_mask
    elif policy == InsufficientDataPolicy.LABEL_NEGATIVE:
        signals_df.loc[insufficient_mask, "label"] = 0
        signals_df["excluded"] = False
    elif policy == InsufficientDataPolicy.LABEL_UNKNOWN:
        signals_df.loc[insufficient_mask, "label"] = -1
        signals_df["excluded"] = False
    else:
        signals_df["excluded"] = False

    # --- Compute confidence scores ---
    signals_df["confidence"] = _compute_confidence_batch(signals_df, config)

    # Reduce confidence for insufficient-history entities
    if policy == InsufficientDataPolicy.LABEL_NEGATIVE:
        signals_df.loc[insufficient_mask, "confidence"] = np.minimum(
            signals_df.loc[insufficient_mask, "confidence"],
            config.min_confidence,
        )

    # --- Summary statistics ---
    if not df.empty:
        included = signals_df[~signals_df["excluded"]]
        n_total = len(signals_df)
        n_included = len(included)
        n_positive = (included["label"] == 1).sum()
        n_negative = (included["label"] == 0).sum()
        logger.info(
            "VOD labeling complete: %d total, %d included "
            "(%d positive, %d negative), %d excluded.",
            n_total,
            n_included,
            n_positive,
            n_negative,
            n_total - n_included,
        )

    return signals_df


def filter_training_data(
    labeled_df: pd.DataFrame,
    min_confidence: float | None = None,
    config: LabelingConfig | None = None,
) -> pd.DataFrame:
    """Filter labeled data to produce a clean training set.

    Removes excluded entities and those below the minimum confidence
    threshold.

    Args:
        labeled_df: Output from ``assign_labels_batch``.
        min_confidence: Override minimum confidence filter.
            Defaults to ``config.min_confidence``.
        config: Labeling configuration for defaults.

    Returns:
        Filtered DataFrame with only usable training samples.
    """
    if config is None:
        config = LabelingConfig()

    threshold = min_confidence if min_confidence is not None else config.min_confidence

    mask = (
        (~labeled_df.get("excluded", pd.Series(False, index=labeled_df.index)))
        & (labeled_df["label"] >= 0)
        & (labeled_df["confidence"] >= threshold)
    )

    result = labeled_df[mask].copy()

    logger.info(
        "Training data filtered: %d -> %d samples (min_confidence=%.2f).",
        len(labeled_df),
        len(result),
        threshold,
    )

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _handle_insufficient_data(
    entity_id: str,
    history_days: int,
    config: LabelingConfig,
) -> VODLabel:
    """Create a label for an entity with insufficient history."""
    policy = config.insufficient_data_policy

    if policy == InsufficientDataPolicy.EXCLUDE:
        logger.info(
            "Entity %s excluded: only %d days of history (minimum %d).",
            entity_id,
            history_days,
            config.thresholds.min_history_days,
        )
        return VODLabel(
            entity_id=entity_id,
            label=-1,
            confidence=0.0,
            signals=None,
            reasons=[
                f"Insufficient history: {history_days} days "
                f"(minimum {config.thresholds.min_history_days})."
            ],
            excluded=True,
        )
    elif policy == InsufficientDataPolicy.LABEL_NEGATIVE:
        logger.info(
            "Entity %s labeled negative (low confidence): "
            "only %d days of history.",
            entity_id,
            history_days,
        )
        return VODLabel(
            entity_id=entity_id,
            label=0,
            confidence=config.min_confidence * 0.5,
            signals=None,
            reasons=[
                f"Insufficient history ({history_days} days); "
                f"defaulting to negative label with low confidence."
            ],
            excluded=False,
        )
    else:  # LABEL_UNKNOWN
        return VODLabel(
            entity_id=entity_id,
            label=-1,
            confidence=0.0,
            signals=None,
            reasons=[
                f"Insufficient history ({history_days} days); "
                f"label set to unknown."
            ],
            excluded=False,
        )


def _compute_confidence(
    label: int,
    signal_count: int,
    history_days: int,
    config: LabelingConfig,
) -> float:
    """Compute confidence score for a single entity label.

    Confidence starts at a base value and is adjusted by:
    - History depth: more history = more confidence.
    - Signal count: more distress signals triggered = higher
      confidence in positive labels.
    - For negative labels, confidence is based on history depth
      alone (absence of signals is less informative with short history).
    """
    confidence = config.base_confidence

    # History bonus: +bonus per 30 days beyond minimum, capped at 0.20
    extra_days = max(0, history_days - config.thresholds.min_history_days)
    history_bonus = min(
        (extra_days / 30) * config.confidence_history_bonus,
        0.20,
    )
    confidence += history_bonus

    # Signal count bonus (positive labels only)
    if label == 1 and signal_count > 0:
        signal_bonus = min(
            signal_count * config.confidence_signal_count_bonus,
            0.20,
        )
        confidence += signal_bonus

    # New user penalty
    if history_days < config.new_user_days:
        confidence *= 0.7

    return min(confidence, 1.0)


def _compute_confidence_batch(
    df: pd.DataFrame,
    config: LabelingConfig,
) -> pd.Series:
    """Compute confidence scores for an entire batch."""
    confidence = np.full(len(df), config.base_confidence)

    # History bonus
    extra_days = np.maximum(
        0, df["history_days"].values - config.thresholds.min_history_days
    )
    history_bonus = np.minimum(
        (extra_days / 30.0) * config.confidence_history_bonus,
        0.20,
    )
    confidence += history_bonus

    # Signal count bonus for positive labels
    signal_count = np.zeros(len(df))
    if "gos_volatility" in df.columns:
        signal_count += (
            df["gos_volatility"].values > config.thresholds.gos_volatility
        ).astype(float)
    if "cblri_drop_pct" in df.columns:
        signal_count += (
            df["cblri_drop_pct"].values > config.thresholds.cblri_drop_pct
        ).astype(float)
    if "tx_pattern_zscore" in df.columns:
        signal_count += (
            df["tx_pattern_zscore"].values > config.thresholds.tx_pattern_zscore
        ).astype(float)

    is_positive = df["label"].values == 1
    signal_bonus = np.minimum(
        signal_count * config.confidence_signal_count_bonus, 0.20
    )
    confidence += np.where(is_positive, signal_bonus, 0.0)

    # New user penalty
    is_new_user = df["history_days"].values < config.new_user_days
    confidence = np.where(is_new_user, confidence * 0.7, confidence)

    return pd.Series(np.minimum(confidence, 1.0), index=df.index)


def _empty_labeled_dataframe() -> pd.DataFrame:
    """Return an empty DataFrame with the expected labeled schema."""
    return pd.DataFrame(
        columns=[
            "entity_id",
            "incoming_tx_value_30d",
            "outgoing_tx_value_30d",
            "avg_daily_balance_30d",
            "avg_daily_balance_90d",
            "historical_cblri",
            "tx_count_current",
            "tx_count_mean",
            "tx_count_std",
            "history_days",
            "gos_index",
            "cblri",
            "cblri_drop_pct",
            "tx_pattern_zscore",
            "gos_volatility",
            "vod_flag",
            "has_sufficient_history",
            "label",
            "confidence",
            "excluded",
        ]
    )
