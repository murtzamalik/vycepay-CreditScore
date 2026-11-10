"""Cross-Border Liquidity Resilience Index (CBLRI).

Measures the consistency and stability of international cash flows
(remittances, FX transactions, cross-border trade payments) over time.
A high CBLRI indicates diversified, stable international revenue streams
that are less likely to dry up during economic stress.

Expected range: 0.0 - 1.0 (normalized index).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute(df: pd.DataFrame) -> pd.Series:
    """Compute the CBLRI for each entity.

    Args:
        df: DataFrame with one row per entity, expected columns:
            - ``cross_border_tx_count_q1`` through ``_q4``: number of
              international transactions per quarter (last 4 quarters).
            - ``cross_border_volume_q1`` through ``_q4``: total KES value
              of international transactions per quarter.
            - ``unique_corridors``: number of distinct country corridors
              used in the last 12 months.

    Returns:
        pd.Series with CBLRI values in [0, 1], indexed like the input.

    Implementation notes (stub):
        1. Compute coefficient of variation (CV) of quarterly volumes
           -> lower CV = more consistent = higher score.
        2. Weight by corridor diversity (more corridors = more resilient).
        3. Apply a floor/ceiling based on minimum transaction count
           thresholds to avoid rewarding sparse but stable flows.
        4. Normalize to [0, 1] using a sigmoid-like transform calibrated
           on the training population.
    """
    # --- Stub implementation with realistic logic structure ---------------
    quarter_volume_cols = [
        f"cross_border_volume_q{q}" for q in range(1, 5)
    ]
    quarter_count_cols = [
        f"cross_border_tx_count_q{q}" for q in range(1, 5)
    ]

    # Coefficient of variation of quarterly volumes (lower = more stable)
    volumes = df[quarter_volume_cols].values.astype(float)
    means = np.nanmean(volumes, axis=1)
    stds = np.nanstd(volumes, axis=1)
    cv = np.where(means > 0, stds / means, 1.0)

    # Consistency score: transform CV to [0, 1] where low CV -> high score
    consistency = 1.0 / (1.0 + cv)

    # Corridor diversity bonus (capped at 10 corridors)
    corridors = df["unique_corridors"].clip(upper=10).values / 10.0

    # Minimum activity gate: at least 4 transactions total across quarters
    total_tx = df[quarter_count_cols].sum(axis=1).values
    activity_gate = np.where(total_tx >= 4, 1.0, total_tx / 4.0)

    # Composite CBLRI
    cblri = (0.6 * consistency + 0.3 * corridors + 0.1 * activity_gate)
    cblri = np.clip(cblri, 0.0, 1.0)

    return pd.Series(cblri, index=df.index, name="cblri")
