"""
Feast DataSource definitions for VyceScore.

Defines the offline (Parquet/FileSource) and online (Redis) data sources
that back the feature views. In production, the offline source would be
replaced with a Redshift/BigQuery source.

Data sources:
    - features_source: Computed feature vectors (output of the feature
      engineering PySpark job)
    - transaction_stats_source: Aggregated transaction statistics
    - raw_transactions_source: Raw transaction data for ad-hoc analysis
"""

from __future__ import annotations

from feast import FileSource

# ---------------------------------------------------------------------------
# Computed Features Source (offline store)
# ---------------------------------------------------------------------------

features_source = FileSource(
    name="scoring_features_source",
    path="s3a://vycescore-datalake/features/",
    timestamp_field="computed_at",
    created_timestamp_column="computed_at",
    description=(
        "Parquet files containing the 6 core scoring features, "
        "partitioned by dt=YYYY-MM-DD. Updated daily by the "
        "feature engineering PySpark job."
    ),
    tags={
        "owner": "vycescore-data-eng",
        "format": "parquet",
        "partitioned_by": "dt",
        "retention_years": "10",
    },
)

# ---------------------------------------------------------------------------
# Transaction Statistics Source (offline store)
# ---------------------------------------------------------------------------

transaction_stats_source = FileSource(
    name="transaction_stats_source",
    path="s3a://vycescore-datalake/aggregated/customer_daily/",
    timestamp_field="last_txn_time",
    created_timestamp_column="last_txn_time",
    description=(
        "Aggregated daily transaction statistics per customer. "
        "Produced by the daily aggregation PySpark job."
    ),
    tags={
        "owner": "vycescore-data-eng",
        "format": "parquet",
        "partitioned_by": "dt",
    },
)

# ---------------------------------------------------------------------------
# Raw Transactions Source (for ad-hoc feature engineering)
# ---------------------------------------------------------------------------

raw_transactions_source = FileSource(
    name="raw_transactions_source",
    path="s3a://vycescore-datalake/raw/vycepay/",
    timestamp_field="timestamp",
    created_timestamp_column="timestamp",
    description=(
        "Raw VycePay transaction data with PII hashed. "
        "Used for ad-hoc feature exploration and backfills."
    ),
    tags={
        "owner": "vycescore-data-eng",
        "format": "parquet",
        "partitioned_by": "dt",
        "pii": "hashed",
        "retention_years": "10",
    },
)
