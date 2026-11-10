"""
PySpark job for daily transaction aggregation.

Aggregates raw VycePay and VyceTrade transactions into daily summary
tables used by the feature engineering pipeline and the Admin UI
dashboards.

Aggregations produced:
    - Customer daily transaction summary (count, volume, avg amount)
    - Merchant category daily breakdown
    - Cross-border transaction summary
    - Supply chain activity summary

All outputs are written as Parquet files partitioned by date.
This job is idempotent: re-running for the same date overwrites the partition.

Usage:
    spark-submit daily_aggregation.py --date 2024-01-15 --input-path s3a://...
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F


def aggregate_customer_daily(transactions: DataFrame) -> DataFrame:
    """Produce daily per-customer transaction summaries.

    Columns produced:
        - national_id_hash: customer identifier
        - txn_date: aggregation date
        - total_txn_count: number of transactions
        - total_volume: sum of transaction amounts (KES)
        - avg_amount: average transaction amount
        - distinct_counterparties: unique counterparties transacted with
        - distinct_categories: unique merchant categories
        - cross_border_count: number of cross-border transactions
        - cross_border_volume: total cross-border amount

    Args:
        transactions: Raw transaction DataFrame.

    Returns:
        Aggregated DataFrame with one row per customer per day.
    """
    return (
        transactions
        .withColumn("txn_date", F.to_date(F.col("timestamp")))
        .groupBy("national_id_hash", "txn_date")
        .agg(
            F.count("*").alias("total_txn_count"),
            F.sum("amount").alias("total_volume"),
            F.avg("amount").alias("avg_amount"),
            F.countDistinct("counterparty_hash").alias("distinct_counterparties"),
            F.countDistinct("merchant_category_code").alias("distinct_categories"),
            F.sum(
                F.when(F.col("is_cross_border") == 1, 1).otherwise(0)
            ).alias("cross_border_count"),
            F.sum(
                F.when(F.col("is_cross_border") == 1, F.col("amount")).otherwise(0)
            ).alias("cross_border_volume"),
            F.min("timestamp").alias("first_txn_time"),
            F.max("timestamp").alias("last_txn_time"),
        )
    )


def aggregate_category_daily(transactions: DataFrame) -> DataFrame:
    """Produce daily merchant category breakdown.

    Used as input for the UTDI (Utility-Based Transactional Diversity
    Index) feature computation.

    Args:
        transactions: Raw transaction DataFrame.

    Returns:
        Aggregated DataFrame with one row per customer per category per day.
    """
    return (
        transactions
        .filter(F.col("merchant_category_code").isNotNull())
        .withColumn("txn_date", F.to_date(F.col("timestamp")))
        .groupBy("national_id_hash", "txn_date", "merchant_category_code")
        .agg(
            F.count("*").alias("category_txn_count"),
            F.sum("amount").alias("category_volume"),
        )
    )


def aggregate_geographic_daily(transactions: DataFrame) -> DataFrame:
    """Produce daily geographic transaction summaries.

    Used as input for the GOS (Geographic Operational Stability) Index.

    Args:
        transactions: Raw transaction DataFrame with lat/lon columns.

    Returns:
        Aggregated DataFrame with geographic statistics per customer per day.
    """
    return (
        transactions
        .filter(
            F.col("latitude").isNotNull() & F.col("longitude").isNotNull()
        )
        .withColumn("txn_date", F.to_date(F.col("timestamp")))
        .groupBy("national_id_hash", "txn_date")
        .agg(
            F.count("*").alias("geo_txn_count"),
            F.avg("latitude").alias("mean_latitude"),
            F.avg("longitude").alias("mean_longitude"),
            F.stddev("latitude").alias("std_latitude"),
            F.stddev("longitude").alias("std_longitude"),
            F.min("latitude").alias("min_latitude"),
            F.max("latitude").alias("max_latitude"),
            F.min("longitude").alias("min_longitude"),
            F.max("longitude").alias("max_longitude"),
        )
    )


def aggregate_supply_chain_daily(supply_chain: DataFrame) -> DataFrame:
    """Produce daily supply chain activity summaries.

    Used as input for the SCFV (Supply Chain Formalization Velocity) feature.

    Args:
        supply_chain: Supply chain link DataFrame.

    Returns:
        Aggregated DataFrame with supply chain stats per supplier per day.
    """
    return (
        supply_chain
        .withColumn("reg_date", F.to_date(F.col("registration_date")))
        .groupBy("supplier_hash", "reg_date")
        .agg(
            F.countDistinct("link_id").alias("new_links"),
            F.sum(F.col("is_digitized")).alias("digitized_links"),
            F.countDistinct("buyer_hash").alias("distinct_buyers"),
            F.sum("invoice_count").alias("total_invoices"),
            F.sum("total_invoice_value").alias("total_invoice_value"),
        )
    )


def run_daily_aggregation(
    spark: SparkSession,
    date: str,
    input_path: str,
    output_path: Optional[str] = None,
) -> dict[str, int]:
    """Execute all daily aggregations for the given date.

    Args:
        spark: Active SparkSession.
        date: Processing date in YYYY-MM-DD format.
        input_path: Base path to the raw data for this date.
        output_path: Optional base output path override.

    Returns:
        Dictionary of aggregation name to row count.
    """
    if output_path is None:
        output_path = f"s3a://vycescore-datalake/aggregated/dt={date}"

    # Read raw data
    transactions = spark.read.parquet(f"{input_path}/transactions/")
    supply_chain = spark.read.parquet(f"{input_path}/supply_chain/")

    aggregations: dict[str, DataFrame] = {
        "customer_daily": aggregate_customer_daily(transactions),
        "category_daily": aggregate_category_daily(transactions),
        "geographic_daily": aggregate_geographic_daily(transactions),
        "supply_chain_daily": aggregate_supply_chain_daily(supply_chain),
    }

    row_counts: dict[str, int] = {}

    for name, df in aggregations.items():
        agg_output_path = f"{output_path}/{name}/"
        df.repartition(10).write.mode("overwrite").parquet(agg_output_path)
        count = df.count()
        row_counts[name] = count
        print(f"Aggregation '{name}': {count} rows written to {agg_output_path}")

    return row_counts


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        args: Optional list of arguments (defaults to sys.argv).

    Returns:
        Parsed namespace with date and input_path.
    """
    parser = argparse.ArgumentParser(description="VyceScore Daily Aggregation Job")
    parser.add_argument("--date", required=True, help="Processing date (YYYY-MM-DD)")
    parser.add_argument("--input-path", required=True, help="Base path to raw data")
    parser.add_argument("--output-path", default=None, help="Optional output path override")
    return parser.parse_args(args)


if __name__ == "__main__":
    args = parse_args()

    spark = (
        SparkSession.builder
        .appName(f"vycescore_daily_aggregation_{args.date}")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.shuffle.partitions", "200")
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
        .config("spark.sql.parquet.compression.codec", "snappy")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    try:
        row_counts = run_daily_aggregation(
            spark=spark,
            date=args.date,
            input_path=args.input_path,
            output_path=args.output_path,
        )
        print(f"Daily aggregation complete: {row_counts}")
    finally:
        spark.stop()
