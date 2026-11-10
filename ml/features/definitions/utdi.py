"""Utility-Based Transactional Diversity Index (UTDI).

Measures the diversity of merchant categories an entity transacts with
per quarter. A high UTDI suggests a well-rounded operational profile
(e.g., paying suppliers, utilities, salaries, logistics across many
categories) rather than dependency on a single revenue/cost channel.

Expected range: 0.0 - 1.0 (normalized index).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute(df: pd.DataFrame) -> pd.Series:
    """Compute the UTDI for each entity.

    Args:
        df: DataFrame with one row per entity, expected columns:
            - ``merchant_categories_q1`` through ``_q4``: number of
              distinct merchant category codes (MCCs) transacted in each
              quarter over the last 12 months.
            - ``total_merchant_categories``: total distinct MCCs seen
              across the full 12-month window.

    Returns:
        pd.Series with UTDI values in [0, 1], indexed like the input.

    Implementation notes (stub):
        1. Compute average quarterly MCC count.
        2. Reward consistency across quarters (low variance in counts).
        3. Apply a diversity ceiling — after ~15 categories, marginal
           benefit flattens (log transform).
        4. Normalize to [0, 1].
    """
    quarter_cols = [f"merchant_categories_q{q}" for q in range(1, 5)]

    categories = df[quarter_cols].values.astype(float)

    # Average quarterly category count
    avg_categories = np.nanmean(categories, axis=1)

    # Log-scaled diversity (diminishing returns after ~15 categories)
    diversity = np.log1p(avg_categories) / np.log1p(15.0)
    diversity = np.clip(diversity, 0.0, 1.0)

    # Quarter-over-quarter consistency (penalize large swings)
    stds = np.nanstd(categories, axis=1)
    means = np.where(avg_categories > 0, avg_categories, 1.0)
    consistency = 1.0 / (1.0 + stds / means)

    # Composite UTDI
    utdi = 0.7 * diversity + 0.3 * consistency
    utdi = np.clip(utdi, 0.0, 1.0)

    return pd.Series(utdi, index=df.index, name="utdi")
