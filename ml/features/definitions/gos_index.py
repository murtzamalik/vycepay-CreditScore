"""Geographic Operational Stability (GOS) Index.

Measures the spatial consistency of an entity's transaction endpoints.
Low GPS variance indicates a stable, established physical presence
(e.g., consistent shop location, regular supplier routes). High
variance may indicate nomadic operations or fraudulent location spoofing.

Expected range: 0.0 - 1.0 (normalized index, higher = more stable).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute(df: pd.DataFrame) -> pd.Series:
    """Compute the GOS Index for each entity.

    Args:
        df: DataFrame with one row per entity, expected columns:
            - ``gps_variance_km``: standard deviation of GPS coordinates
              (in km) across all transaction endpoints in the last 12 months.
            - ``primary_location_tx_pct``: percentage of transactions
              occurring within 5 km of the entity's registered/primary
              location (0-100).
            - ``unique_transaction_locations``: count of distinct
              transaction endpoint locations.

    Returns:
        pd.Series with GOS Index values in [0, 1], indexed like the input.

    Implementation notes (stub):
        1. Transform GPS variance using an inverse sigmoid — low variance
           yields high stability, but zero variance is slightly suspicious
           (possible single-point spoofing).
        2. Reward high primary-location concentration.
        3. Factor in location count — a few stable locations is fine;
           many scattered locations is risky.
        4. Normalize to [0, 1].
    """
    variance_km = df["gps_variance_km"].values.astype(float)
    primary_pct = df["primary_location_tx_pct"].values.astype(float) / 100.0
    unique_locs = df["unique_transaction_locations"].values.astype(float)

    # Stability from GPS variance: sigmoid centered at 10 km std dev
    # Low variance -> high score, but extremely low (< 0.1 km) gets
    # a slight haircut for potential spoofing.
    variance_score = 1.0 / (1.0 + np.exp(0.5 * (variance_km - 10.0)))
    spoofing_haircut = np.where(variance_km < 0.1, 0.9, 1.0)
    variance_score *= spoofing_haircut

    # Primary location concentration
    concentration = np.clip(primary_pct, 0.0, 1.0)

    # Location count factor: 1-5 locations is normal; penalize > 20
    location_factor = np.where(
        unique_locs <= 5,
        1.0,
        np.clip(1.0 - (unique_locs - 5) / 50.0, 0.5, 1.0),
    )

    # Composite GOS
    gos = (
        0.45 * variance_score
        + 0.35 * concentration
        + 0.20 * location_factor
    )
    gos = np.clip(gos, 0.0, 1.0)

    return pd.Series(gos, index=df.index, name="gos_index")
