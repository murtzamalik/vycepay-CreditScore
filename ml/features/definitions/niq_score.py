"""Network Interdependence and Quality (NIQ) Score.

Measures the creditworthiness of an entity's trading network by
averaging the VyceScores of their top 5 trading partners. The
intuition: entities that trade with financially healthy counterparts
are less likely to experience payment disruptions.

Expected range: 0 - 100 (normalized from partner VyceScores 300-900).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

VYCESCORE_MIN = 300
VYCESCORE_MAX = 900
NIQ_MIN = 0
NIQ_MAX = 100


def compute(df: pd.DataFrame) -> pd.Series:
    """Compute the NIQ Score for each entity.

    Args:
        df: DataFrame with one row per entity, expected columns:
            - ``partner_score_1`` through ``partner_score_5``: VyceScores
              (300-900) of the entity's top 5 trading partners by volume.
              NaN if the entity has fewer than 5 partners.

    Returns:
        pd.Series with NIQ Score values in [0, 100], indexed like the input.

    Implementation notes (stub):
        1. Average the available partner VyceScores (up to 5).
        2. Normalize from 300-900 range to 0-100 range.
        3. Apply a small penalty if fewer than 3 partners are available
           (thin network = higher uncertainty = lower NIQ).
        4. Entities with zero partners get NIQ = 0.
    """
    partner_cols = [f"partner_score_{i}" for i in range(1, 6)]

    scores = df[partner_cols].values.astype(float)

    # Count non-NaN partners per entity
    valid_count = np.sum(~np.isnan(scores), axis=1)

    # Mean of available partner scores
    avg_score = np.nanmean(scores, axis=1)
    avg_score = np.where(valid_count > 0, avg_score, VYCESCORE_MIN)

    # Normalize 300-900 -> 0-100
    normalized = (
        (avg_score - VYCESCORE_MIN)
        / (VYCESCORE_MAX - VYCESCORE_MIN)
        * NIQ_MAX
    )

    # Thin-network penalty: reduce score if fewer than 3 partners
    network_factor = np.where(
        valid_count >= 3,
        1.0,
        np.where(valid_count > 0, valid_count / 3.0, 0.0),
    )

    niq = normalized * network_factor
    niq = np.clip(niq, NIQ_MIN, NIQ_MAX)

    return pd.Series(niq, index=df.index, name="niq_score")
