"""Shared test fixtures for ml/ tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.vod.signals import VODThresholds


@pytest.fixture()
def default_thresholds() -> VODThresholds:
    """Default VOD thresholds."""
    return VODThresholds()


@pytest.fixture()
def sample_entity_data() -> dict[str, float | int]:
    """A single healthy entity's data."""
    return {
        "incoming_30d": 50_000.0,
        "outgoing_30d": 30_000.0,
        "avg_balance_30d": 10_000.0,
        "avg_balance_90d": 9_000.0,
        "historical_cblri": 1.1,
        "tx_count_current": 45.0,
        "tx_count_mean": 40.0,
        "tx_count_std": 8.0,
        "history_days": 180,
        "rolling_gos": [0.20, 0.22, 0.18, 0.25, 0.19, 0.21],
    }


@pytest.fixture()
def distressed_entity_data() -> dict[str, float | int]:
    """A single distressed entity's data."""
    return {
        "incoming_30d": 5_000.0,
        "outgoing_30d": 45_000.0,
        "avg_balance_30d": 2_000.0,
        "avg_balance_90d": 20_000.0,
        "historical_cblri": 1.5,
        "tx_count_current": 5.0,
        "tx_count_mean": 40.0,
        "tx_count_std": 8.0,
        "history_days": 365,
        "rolling_gos": [0.30, -0.40, 0.10, -0.60, 0.50, -0.80],
    }


@pytest.fixture()
def batch_dataframe() -> pd.DataFrame:
    """A batch DataFrame with a mix of healthy and distressed entities."""
    np.random.seed(42)
    n_healthy = 8
    n_distressed = 4
    n_new = 2
    n = n_healthy + n_distressed + n_new

    data = {
        "entity_id": [f"ENT-{i:04d}" for i in range(n)],
        "incoming_tx_value_30d": np.concatenate([
            np.random.uniform(30_000, 80_000, n_healthy),
            np.random.uniform(1_000, 10_000, n_distressed),
            np.random.uniform(5_000, 15_000, n_new),
        ]),
        "outgoing_tx_value_30d": np.concatenate([
            np.random.uniform(20_000, 50_000, n_healthy),
            np.random.uniform(30_000, 60_000, n_distressed),
            np.random.uniform(3_000, 8_000, n_new),
        ]),
        "avg_daily_balance_30d": np.concatenate([
            np.random.uniform(8_000, 20_000, n_healthy),
            np.random.uniform(500, 3_000, n_distressed),
            np.random.uniform(2_000, 5_000, n_new),
        ]),
        "avg_daily_balance_90d": np.concatenate([
            np.random.uniform(7_000, 18_000, n_healthy),
            np.random.uniform(15_000, 30_000, n_distressed),
            np.random.uniform(3_000, 6_000, n_new),
        ]),
        "historical_cblri": np.concatenate([
            np.random.uniform(0.9, 1.3, n_healthy),
            np.random.uniform(1.2, 2.0, n_distressed),
            np.random.uniform(0.8, 1.2, n_new),
        ]),
        "tx_count_current": np.concatenate([
            np.random.uniform(30, 60, n_healthy),
            np.random.uniform(2, 10, n_distressed),
            np.random.uniform(5, 15, n_new),
        ]),
        "tx_count_mean": np.concatenate([
            np.random.uniform(35, 55, n_healthy),
            np.random.uniform(35, 55, n_distressed),
            np.random.uniform(10, 20, n_new),
        ]),
        "tx_count_std": np.concatenate([
            np.random.uniform(5, 12, n_healthy),
            np.random.uniform(5, 12, n_distressed),
            np.random.uniform(3, 8, n_new),
        ]),
        "history_days": np.concatenate([
            np.random.randint(90, 730, n_healthy),
            np.random.randint(60, 365, n_distressed),
            np.random.randint(5, 25, n_new),
        ]).astype(int),
    }

    # Add rolling GOS period columns
    for i in range(1, 7):
        healthy_gos = np.random.uniform(0.1, 0.3, n_healthy)
        distressed_gos = np.random.uniform(-0.8, 0.5, n_distressed)
        new_gos = np.random.uniform(-0.1, 0.2, n_new)
        data[f"gos_period_{i}"] = np.concatenate([
            healthy_gos, distressed_gos, new_gos
        ])

    return pd.DataFrame(data)
