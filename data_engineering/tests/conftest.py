"""Shared fixtures for data_engineering tests."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def sample_transactions() -> pd.DataFrame:
    """Create a sample transaction DataFrame for testing."""
    rng = np.random.default_rng(42)
    n = 100

    return pd.DataFrame({
        "transaction_id": [f"tx_{i:06d}" for i in range(n)],
        "national_id_hash": [
            f"{'a' * 60}{i:04d}" for i in rng.integers(0, 20, size=n)
        ],
        "transaction_type": rng.choice(
            ["FT", "IBFT", "REMIT", "MERCHANT", "BILL_PAY"],
            size=n,
        ),
        "amount": rng.uniform(100, 500_000, size=n).round(2),
        "currency": rng.choice(["KES", "USD"], size=n, p=[0.9, 0.1]),
        "merchant_category_code": rng.choice(
            ["5411", "5541", "5812", None], size=n, p=[0.3, 0.2, 0.3, 0.2],
        ),
        "is_cross_border": rng.integers(0, 2, size=n),
        "counterparty_hash": [
            f"{'b' * 60}{i:04d}" if rng.random() > 0.2 else None
            for i in rng.integers(0, 30, size=n)
        ],
        "latitude": rng.uniform(-1.5, 1.5, size=n),
        "longitude": rng.uniform(36.5, 37.5, size=n),
        "timestamp": pd.date_range(
            "2026-02-01", periods=n, freq="h", tz="UTC"
        ),
    })


@pytest.fixture
def sample_supply_chain() -> pd.DataFrame:
    """Create a sample supply chain DataFrame for testing."""
    rng = np.random.default_rng(42)
    n = 50

    return pd.DataFrame({
        "link_id": [f"link_{i:04d}" for i in range(n)],
        "supplier_hash": [
            f"{'c' * 60}{i:04d}" for i in rng.integers(0, 10, size=n)
        ],
        "buyer_hash": [
            f"{'d' * 60}{i:04d}" for i in rng.integers(0, 15, size=n)
        ],
        "is_digitized": rng.integers(0, 2, size=n),
        "registration_date": pd.date_range(
            "2025-06-01", periods=n, freq="W", tz="UTC"
        ),
        "invoice_count": rng.integers(0, 100, size=n),
        "total_invoice_value": rng.uniform(1000, 1_000_000, size=n).round(2),
    })


@pytest.fixture
def sample_features() -> pd.DataFrame:
    """Create a sample computed features DataFrame."""
    rng = np.random.default_rng(42)
    n = 50

    return pd.DataFrame({
        "national_id_hash": [f"{'a' * 60}{i:04d}" for i in range(n)],
        "cblri": rng.uniform(0, 1, size=n),
        "utdi": rng.uniform(0, 1, size=n),
        "scfv": rng.uniform(0, 1, size=n),
        "ddc_ratio": rng.uniform(0, 1, size=n),
        "niq_score": rng.uniform(0, 100, size=n),
        "gos_index": rng.uniform(0, 1, size=n),
        "tx_volume_30d": rng.uniform(0, 500, size=n),
        "tx_value_30d": rng.uniform(0, 1_000_000, size=n),
        "computed_at": pd.Timestamp.now(tz="UTC"),
        "feature_date": "2026-03-08",
    })


@pytest.fixture
def sample_features_with_timestamps() -> pd.DataFrame:
    """Features with varying computed_at timestamps for freshness tests."""
    rng = np.random.default_rng(42)
    n = 20
    now = pd.Timestamp.now(tz="UTC")

    # Mix of fresh and stale features
    timestamps = [
        now - pd.Timedelta(hours=h)
        for h in rng.choice([1, 6, 12, 24, 36, 50, 72, 96], size=n)
    ]

    return pd.DataFrame({
        "national_id_hash": [f"{'e' * 60}{i:04d}" for i in range(n)],
        "cblri": rng.uniform(0, 1, size=n),
        "utdi": rng.uniform(0, 1, size=n),
        "computed_at": timestamps,
    })
