"""VOD (Vyce-Observed Distress) signal calculations.

Computes distress signals from transaction and balance data to serve as
proxy labels for credit risk modeling before ground-truth loan outcomes
are available from partner banks.

Key signals:
    - **GOS Index**: Gross Operating Surrogate — net cash flow direction
      normalized by total volume. Negative values indicate net outflows.
    - **CBLRI**: Core Balance Liquidity Ratio Index — short-term balance
      health relative to medium-term average. Values < 1 indicate
      deteriorating liquidity.
    - **GOS Volatility**: Standard deviation of rolling GOS values — high
      volatility signals erratic cash flow management.
    - **CBLRI Drop Percent**: Magnitude of recent balance decline relative
      to historical levels.
    - **Transaction Pattern Z-Score**: Deviation from an entity's
      established transaction behavior.
    - **VOD Flag**: Combined binary distress indicator.

Note: The GOS Index here is a *different* concept from the Geographic
Operational Stability (GOS) Index in ``ml.features.definitions.gos_index``.
This GOS measures cash-flow surplus/deficit; the feature-level GOS
measures spatial transaction consistency.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Union

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VODThresholds:
    """Configurable thresholds for VOD distress signal detection.

    Attributes:
        gos_volatility: Maximum tolerable GOS volatility (std dev).
            Values above this indicate erratic cash flow.
        cblri_drop_pct: Maximum tolerable CBLRI drop (as a fraction,
            e.g. 0.30 = 30% decline). Values above this indicate
            liquidity deterioration.
        tx_pattern_zscore: Maximum tolerable z-score for transaction
            pattern deviation. Values above this indicate anomalous
            behavior (could be distress or fraud).
        min_history_days: Minimum days of transaction history required
            before a VOD signal is considered reliable.
        gos_rolling_window: Number of periods for the rolling GOS
            calculation used to derive volatility.
    """

    gos_volatility: float = 0.35
    cblri_drop_pct: float = 0.30
    tx_pattern_zscore: float = 2.0
    min_history_days: int = 30
    gos_rolling_window: int = 6


# ---------------------------------------------------------------------------
# GOS Index (Gross Operating Surrogate)
# ---------------------------------------------------------------------------

def compute_gos_index(
    incoming: Union[float, np.ndarray, pd.Series],
    outgoing: Union[float, np.ndarray, pd.Series],
) -> Union[float, np.ndarray, pd.Series]:
    """Compute the GOS Index (net cash flow direction).

    Formula::

        gos = (incoming - outgoing) / max(incoming + outgoing, 1)

    Range is [-1, 1].  Positive values indicate net inflows; negative
    values indicate net outflows (potential distress signal).

    Args:
        incoming: Total incoming transaction value over the period.
        outgoing: Total outgoing transaction value over the period.

    Returns:
        GOS Index value(s) in [-1, 1].  Returns 0.0 when both incoming
        and outgoing are zero (no activity).
    """
    incoming_arr = _to_float_array(incoming)
    outgoing_arr = _to_float_array(outgoing)

    # Guard against negative values (data quality issue)
    if np.any(incoming_arr < 0) or np.any(outgoing_arr < 0):
        logger.warning(
            "Negative transaction values detected in GOS calculation; "
            "clipping to zero."
        )
        incoming_arr = np.maximum(incoming_arr, 0.0)
        outgoing_arr = np.maximum(outgoing_arr, 0.0)

    denominator = np.maximum(incoming_arr + outgoing_arr, 1.0)
    gos = (incoming_arr - outgoing_arr) / denominator

    return _restore_type(gos, incoming)


def compute_gos_volatility(
    rolling_gos_values: Union[np.ndarray, pd.Series, list[float]],
) -> float:
    """Compute GOS Index volatility as the standard deviation of rolling values.

    Args:
        rolling_gos_values: Sequence of GOS Index values computed over
            consecutive periods (e.g., weekly or monthly windows).

    Returns:
        Standard deviation of the GOS values.  Returns 0.0 if fewer
        than 2 values are provided.
    """
    arr = np.asarray(rolling_gos_values, dtype=float)
    valid = arr[np.isfinite(arr)]

    if len(valid) < 2:
        logger.warning(
            "Fewer than 2 valid GOS values for volatility calculation; "
            "returning 0.0."
        )
        return 0.0

    return float(np.std(valid, ddof=1))


# ---------------------------------------------------------------------------
# CBLRI (Core Balance Liquidity Ratio Index)
# ---------------------------------------------------------------------------

def compute_cblri(
    avg_balance_30d: Union[float, np.ndarray, pd.Series],
    avg_balance_90d: Union[float, np.ndarray, pd.Series],
) -> Union[float, np.ndarray, pd.Series]:
    """Compute the Core Balance Liquidity Ratio Index.

    Formula::

        cblri = avg_balance_30d / max(avg_balance_90d, 1)

    A ratio > 1 indicates improving liquidity (recent balance exceeds
    the 90-day average).  A ratio < 1 indicates deterioration.

    Args:
        avg_balance_30d: Average daily balance over the last 30 days.
        avg_balance_90d: Average daily balance over the last 90 days.

    Returns:
        CBLRI ratio.  Clamped to [0, 5] to prevent extreme outliers
        from dominating downstream models.
    """
    short = _to_float_array(avg_balance_30d)
    long = _to_float_array(avg_balance_90d)

    if np.any(short < 0) or np.any(long < 0):
        logger.warning(
            "Negative balance values detected in CBLRI calculation; "
            "clipping to zero."
        )
        short = np.maximum(short, 0.0)
        long = np.maximum(long, 0.0)

    denominator = np.maximum(long, 1.0)
    cblri = short / denominator

    # Clamp to avoid extreme outliers
    cblri = np.clip(cblri, 0.0, 5.0)

    return _restore_type(cblri, avg_balance_30d)


def compute_cblri_drop_percent(
    current_cblri: Union[float, np.ndarray, pd.Series],
    historical_cblri: Union[float, np.ndarray, pd.Series],
) -> Union[float, np.ndarray, pd.Series]:
    """Compute the percentage drop in CBLRI from historical to current.

    Formula::

        drop = max(0, (historical - current) / max(historical, 0.001))

    Returns a non-negative fraction: 0.0 means no decline, 0.30 means
    a 30% decline.  Improvements (current > historical) return 0.0.

    Args:
        current_cblri: Current CBLRI value(s).
        historical_cblri: Historical (baseline) CBLRI value(s),
            typically the 6-month or 12-month rolling average.

    Returns:
        Drop percentage as a fraction in [0, 1+].
    """
    current = _to_float_array(current_cblri)
    historical = _to_float_array(historical_cblri)

    denominator = np.maximum(historical, 0.001)
    drop = (historical - current) / denominator
    drop = np.maximum(drop, 0.0)

    return _restore_type(drop, current_cblri)


# ---------------------------------------------------------------------------
# Transaction Pattern Z-Score
# ---------------------------------------------------------------------------

def compute_tx_pattern_zscore(
    current_value: Union[float, np.ndarray, pd.Series],
    historical_mean: Union[float, np.ndarray, pd.Series],
    historical_std: Union[float, np.ndarray, pd.Series],
) -> Union[float, np.ndarray, pd.Series]:
    """Compute z-score of current transaction pattern vs historical baseline.

    Measures how many standard deviations the current transaction
    behavior deviates from the entity's established pattern.  The
    ``current_value`` can represent any behavioral metric (e.g.,
    transaction count, average transaction size, frequency).

    Args:
        current_value: Current-period metric value(s).
        historical_mean: Mean of the metric over the historical baseline
            period.
        historical_std: Standard deviation of the metric over the
            historical baseline period.

    Returns:
        Absolute z-score value(s).  Returns 0.0 when historical_std is
        zero or near-zero (entity has perfectly consistent behavior —
        no deviation is detectable).
    """
    current = _to_float_array(current_value)
    mean = _to_float_array(historical_mean)
    std = _to_float_array(historical_std)

    # When std is effectively zero, the entity has no variation — report
    # z-score as 0 (cannot measure deviation without variance).
    safe_std = np.where(std > 1e-9, std, np.inf)
    zscore = np.abs((current - mean) / safe_std)

    # Cap at 10 to avoid extreme outliers
    zscore = np.minimum(zscore, 10.0)

    return _restore_type(zscore, current_value)


# ---------------------------------------------------------------------------
# Combined VOD Flag
# ---------------------------------------------------------------------------

@dataclass
class VODSignalResult:
    """Result of VOD signal computation for a single entity or batch.

    Attributes:
        gos_index: Computed GOS Index value(s).
        gos_volatility: GOS Index volatility (std dev of rolling values).
        cblri: Computed CBLRI value(s).
        cblri_drop_pct: CBLRI drop percentage from historical baseline.
        tx_pattern_zscore: Transaction pattern z-score.
        vod_flag: Binary distress flag (True = distress detected).
        distress_reasons: List of reasons the VOD flag was triggered.
        has_sufficient_history: Whether the entity had enough data
            history to produce a reliable signal.
    """

    gos_index: Union[float, np.ndarray]
    gos_volatility: Union[float, np.ndarray]
    cblri: Union[float, np.ndarray]
    cblri_drop_pct: Union[float, np.ndarray]
    tx_pattern_zscore: Union[float, np.ndarray]
    vod_flag: Union[bool, np.ndarray]
    distress_reasons: list[str] = field(default_factory=list)
    has_sufficient_history: bool = True


def compute_vod_flag(
    gos_volatility: Union[float, np.ndarray, pd.Series],
    cblri_drop_pct: Union[float, np.ndarray, pd.Series],
    tx_pattern_zscore: Union[float, np.ndarray, pd.Series],
    thresholds: VODThresholds | None = None,
) -> Union[bool, np.ndarray]:
    """Compute the combined VOD (distress) flag.

    An entity is flagged as distressed if ANY of the three signal
    thresholds are breached::

        vod_flag = (
            (gos_volatility > threshold_gos) OR
            (cblri_drop_pct > threshold_cblri) OR
            (tx_pattern_zscore > threshold_pattern)
        )

    Args:
        gos_volatility: GOS Index volatility value(s).
        cblri_drop_pct: CBLRI drop percentage value(s).
        tx_pattern_zscore: Transaction pattern z-score value(s).
        thresholds: Configurable thresholds.  Uses defaults if None.

    Returns:
        Boolean flag(s): True indicates distress detected.
    """
    if thresholds is None:
        thresholds = VODThresholds()

    gos_v = _to_float_array(gos_volatility)
    cblri_d = _to_float_array(cblri_drop_pct)
    tx_z = _to_float_array(tx_pattern_zscore)

    flag = (
        (gos_v > thresholds.gos_volatility)
        | (cblri_d > thresholds.cblri_drop_pct)
        | (tx_z > thresholds.tx_pattern_zscore)
    )

    # Return scalar bool if all inputs were scalar
    if isinstance(gos_volatility, (int, float)):
        return bool(flag.item())

    return flag


def compute_signals_from_dataframe(
    df: pd.DataFrame,
    thresholds: VODThresholds | None = None,
) -> pd.DataFrame:
    """Compute all VOD signals from a structured DataFrame.

    This is the primary batch interface. The input DataFrame must contain
    columns for each signal's raw inputs.

    Required columns:
        - ``incoming_tx_value_30d``: Total incoming transaction value (30d).
        - ``outgoing_tx_value_30d``: Total outgoing transaction value (30d).
        - ``avg_daily_balance_30d``: Average daily balance (30d).
        - ``avg_daily_balance_90d``: Average daily balance (90d).
        - ``historical_cblri``: Historical baseline CBLRI.
        - ``tx_count_current``: Current-period transaction count.
        - ``tx_count_mean``: Historical mean transaction count.
        - ``tx_count_std``: Historical std dev of transaction count.
        - ``history_days``: Number of days of transaction history.

    Optional columns (for GOS volatility, provide at least 2):
        - ``gos_period_1`` through ``gos_period_N``: Rolling GOS values
          for consecutive periods.

    Args:
        df: Input DataFrame with required columns.
        thresholds: Configurable thresholds.  Uses defaults if None.

    Returns:
        DataFrame with computed signal columns appended:
        ``gos_index``, ``cblri``, ``cblri_drop_pct``,
        ``tx_pattern_zscore``, ``gos_volatility``,
        ``vod_flag``, ``has_sufficient_history``.
    """
    if thresholds is None:
        thresholds = VODThresholds()

    result = df.copy()

    # --- GOS Index ---
    result["gos_index"] = compute_gos_index(
        df["incoming_tx_value_30d"],
        df["outgoing_tx_value_30d"],
    )

    # --- CBLRI ---
    result["cblri"] = compute_cblri(
        df["avg_daily_balance_30d"],
        df["avg_daily_balance_90d"],
    )

    # --- CBLRI Drop ---
    result["cblri_drop_pct"] = compute_cblri_drop_percent(
        result["cblri"],
        df["historical_cblri"],
    )

    # --- Transaction Pattern Z-Score ---
    result["tx_pattern_zscore"] = compute_tx_pattern_zscore(
        df["tx_count_current"],
        df["tx_count_mean"],
        df["tx_count_std"],
    )

    # --- GOS Volatility (per-row from period columns) ---
    gos_period_cols = [
        c for c in df.columns if c.startswith("gos_period_")
    ]
    if gos_period_cols:
        gos_periods = df[gos_period_cols].values
        # Compute row-wise std dev
        with np.errstate(invalid="ignore"):
            valid_counts = np.sum(np.isfinite(gos_periods), axis=1)
            means = np.nanmean(gos_periods, axis=1)
            diffs_sq = (gos_periods - means[:, np.newaxis]) ** 2
            variances = np.nansum(diffs_sq, axis=1) / np.maximum(
                valid_counts - 1, 1
            )
            result["gos_volatility"] = np.where(
                valid_counts >= 2, np.sqrt(variances), 0.0
            )
    else:
        logger.warning(
            "No gos_period_* columns found; setting gos_volatility to 0.0. "
            "Provide gos_period_1..N columns for accurate volatility."
        )
        result["gos_volatility"] = 0.0

    # --- Sufficient history check ---
    result["has_sufficient_history"] = (
        df["history_days"] >= thresholds.min_history_days
    )

    # --- Combined VOD flag ---
    result["vod_flag"] = compute_vod_flag(
        result["gos_volatility"].values,
        result["cblri_drop_pct"].values,
        result["tx_pattern_zscore"].values,
        thresholds=thresholds,
    )

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _to_float_array(x: Union[float, int, np.ndarray, pd.Series]) -> np.ndarray:
    """Convert scalar, Series, or array to a float64 numpy array."""
    if isinstance(x, pd.Series):
        return x.values.astype(np.float64)
    return np.atleast_1d(np.asarray(x, dtype=np.float64))


def _restore_type(
    arr: np.ndarray,
    reference: Union[float, int, np.ndarray, pd.Series],
) -> Union[float, np.ndarray, pd.Series]:
    """Return the result in the same type family as the reference input."""
    if isinstance(reference, pd.Series):
        return pd.Series(arr, index=reference.index)
    if isinstance(reference, (int, float)):
        return float(arr.item()) if arr.size == 1 else arr
    return arr
