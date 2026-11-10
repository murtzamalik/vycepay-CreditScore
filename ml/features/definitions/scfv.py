"""Supply Chain Formalization Velocity (SCFV).

Measures the rate at which an entity is formalizing its supply chain
relationships through digitized, traceable supplier-buyer links on
VyceTrade. A rising SCFV indicates growing operational maturity and
audit-readiness — both strong credit-positive signals.

Expected range: 0.0 - 1.0 (normalized velocity).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute(df: pd.DataFrame) -> pd.Series:
    """Compute the SCFV for each entity.

    Args:
        df: DataFrame with one row per entity, expected columns:
            - ``digitized_links_current``: number of supplier/buyer
              relationships currently formalized on VyceTrade.
            - ``digitized_links_6m_ago``: same count 6 months prior.
            - ``total_trade_relationships``: total known trade
              relationships (digitized + informal).
            - ``invoices_digitized_pct``: percentage of invoices
              processed through VyceTrade (0-100).

    Returns:
        pd.Series with SCFV values in [0, 1], indexed like the input.

    Implementation notes (stub):
        1. Compute growth rate of digitized links over 6 months.
        2. Weight by current formalization ratio (digitized / total).
        3. Factor in invoice digitization percentage.
        4. Apply sigmoid normalization to handle outlier growth rates.
    """
    current = df["digitized_links_current"].values.astype(float)
    previous = df["digitized_links_6m_ago"].values.astype(float)
    total = df["total_trade_relationships"].values.astype(float)
    invoice_pct = df["invoices_digitized_pct"].values.astype(float) / 100.0

    # Growth rate of digitized links (capped to avoid outlier influence)
    denominator = np.where(previous > 0, previous, 1.0)
    growth = (current - previous) / denominator
    growth = np.clip(growth, -1.0, 5.0)

    # Sigmoid transform to [0, 1] — center at 0.5 growth = 50% increase
    growth_score = 1.0 / (1.0 + np.exp(-2.0 * growth))

    # Current formalization ratio
    total_safe = np.where(total > 0, total, 1.0)
    formalization_ratio = np.clip(current / total_safe, 0.0, 1.0)

    # Composite SCFV
    scfv = (
        0.4 * growth_score
        + 0.35 * formalization_ratio
        + 0.25 * invoice_pct
    )
    scfv = np.clip(scfv, 0.0, 1.0)

    return pd.Series(scfv, index=df.index, name="scfv")
