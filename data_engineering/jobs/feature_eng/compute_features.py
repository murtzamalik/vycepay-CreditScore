"""
PySpark job to compute all 6 core VyceScore features from raw transaction data.

Features computed:
    1. CBLRI - Cross-Border Liquidity Resilience Index
    2. UTDI  - Utility-Based Transactional Diversity Index
    3. SCFV  - Supply Chain Formalization Velocity
    4. DDC Ratio - Digital Documentation Compliance Ratio
    5. NIQ Score - Network Interdependence and Quality Score
    6. GOS Index - Geographic Operational Stability Index

Usage:
    spark-submit compute_features.py --date 2024-01-15 --input-path s3a://...

This job is idempotent: re-running for the same date produces identical output
by overwriting the feature partition.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from typing import Optional

from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType,
    FloatType,
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

# ---------------------------------------------------------------------------
# Schema definitions
# ---------------------------------------------------------------------------

TRANSACTION_SCHEMA = StructType([
    StructField("transaction_id", StringType(), nullable=False),
    StructField("national_id_hash", StringType(), nullable=False),
    StructField("transaction_type", StringType(), nullable=False),
    StructField("amount", DoubleType(), nullable=False),
    StructField("currency", StringType(), nullable=False),
    StructField("merchant_category_code", StringType(), nullable=True),
    StructField("is_cross_border", IntegerType(), nullable=False),
    StructField("counterparty_hash", StringType(), nullable=True),
    StructField("latitude", DoubleType(), nullable=True),
    StructField("longitude", DoubleType(), nullable=True),
    StructField("timestamp", TimestampType(), nullable=False),
])

SUPPLY_CHAIN_SCHEMA = StructType([
    StructField("link_id", StringType(), nullable=False),
    StructField("supplier_hash", StringType(), nullable=False),
    StructField("buyer_hash", StringType(), nullable=False),
    StructField("is_digitized", IntegerType(), nullable=False),
    StructField("registration_date", TimestampType(), nullable=False),
    StructField("invoice_count", IntegerType(), nullable=True),
    StructField("total_invoice_value", DoubleType(), nullable=True),
])


# ---------------------------------------------------------------------------
# Feature computation functions
# ---------------------------------------------------------------------------

def compute_cblri(transactions: DataFrame) -> DataFrame:
    """Compute Cross-Border Liquidity Resilience Index (CBLRI).

    Measures the consistency of international cash flows over a rolling
    90-day window. A higher CBLRI indicates more stable cross-border
    liquidity, suggesting resilience to forex and remittance volatility.

    Formula:
        CBLRI = 1 - CV(monthly_cross_border_volume) over trailing 3 months

    Where CV is the coefficient of variation (std_dev / mean).
    Clamped to [0.0, 1.0].

    Args:
        transactions: DataFrame with transaction records including
            is_cross_border flag.

    Returns:
        DataFrame with columns [national_id_hash, cblri].
    """
    cross_border = transactions.filter(F.col("is_cross_border") == 1)

    monthly_volumes = (
        cross_border
        .withColumn("month", F.date_trunc("month", F.col("timestamp")))
        .groupBy("national_id_hash", "month")
        .agg(F.sum("amount").alias("monthly_volume"))
    )

    cblri = (
        monthly_volumes
        .groupBy("national_id_hash")
        .agg(
            F.mean("monthly_volume").alias("mean_vol"),
            F.stddev("monthly_volume").alias("std_vol"),
        )
        .withColumn(
            "cblri",
            F.when(
                (F.col("mean_vol") > 0) & F.col("std_vol").isNotNull(),
                F.greatest(
                    F.lit(0.0),
                    F.least(F.lit(1.0), 1.0 - (F.col("std_vol") / F.col("mean_vol"))),
                ),
            ).otherwise(F.lit(0.0)),
        )
        .select("national_id_hash", "cblri")
    )

    return cblri


def compute_utdi(transactions: DataFrame) -> DataFrame:
    """Compute Utility-Based Transactional Diversity Index (UTDI).

    Measures merchant category diversity per quarter using a normalized
    Shannon entropy metric. Higher UTDI indicates a more diversified
    spending pattern, suggesting a healthier business operation.

    Formula:
        UTDI = -SUM(p_i * log2(p_i)) / log2(N)

    Where p_i is the proportion of spend in category i, and N is the
    total number of distinct categories observed.
    Clamped to [0.0, 1.0].

    Args:
        transactions: DataFrame with merchant_category_code column.

    Returns:
        DataFrame with columns [national_id_hash, utdi].
    """
    categorized = transactions.filter(F.col("merchant_category_code").isNotNull())

    category_spend = (
        categorized
        .withColumn("quarter", F.date_trunc("quarter", F.col("timestamp")))
        .groupBy("national_id_hash", "quarter", "merchant_category_code")
        .agg(F.sum("amount").alias("category_amount"))
    )

    total_spend = (
        category_spend
        .groupBy("national_id_hash", "quarter")
        .agg(F.sum("category_amount").alias("total_amount"))
    )

    proportions = (
        category_spend
        .join(total_spend, on=["national_id_hash", "quarter"])
        .withColumn("p", F.col("category_amount") / F.col("total_amount"))
        .withColumn("entropy_term", -F.col("p") * F.log2(F.col("p")))
    )

    entropy = (
        proportions
        .groupBy("national_id_hash", "quarter")
        .agg(
            F.sum("entropy_term").alias("entropy"),
            F.countDistinct("merchant_category_code").alias("n_categories"),
        )
        .withColumn(
            "utdi",
            F.when(
                F.col("n_categories") > 1,
                F.col("entropy") / F.log2(F.col("n_categories")),
            ).otherwise(F.lit(0.0)),
        )
    )

    # Take the most recent quarter's UTDI per customer
    window = Window.partitionBy("national_id_hash").orderBy(F.col("quarter").desc())
    utdi = (
        entropy
        .withColumn("rn", F.row_number().over(window))
        .filter(F.col("rn") == 1)
        .select(
            "national_id_hash",
            F.greatest(F.lit(0.0), F.least(F.lit(1.0), F.col("utdi"))).alias("utdi"),
        )
    )

    return utdi


def compute_scfv(supply_chain_links: DataFrame) -> DataFrame:
    """Compute Supply Chain Formalization Velocity (SCFV).

    Measures the growth rate of digitized supplier-buyer links over time
    via VyceTrade. Higher SCFV indicates rapid adoption of formal digital
    supply chain practices.

    Formula:
        SCFV = (digitized_links_current_quarter - digitized_links_prev_quarter)
               / max(digitized_links_prev_quarter, 1) * 100

    Clamped to [0.0, 100.0].

    Args:
        supply_chain_links: DataFrame with supply chain link records.

    Returns:
        DataFrame with columns [supplier_hash, scfv] (supplier_hash acts
        as the entity for supply-chain-centric scoring).
    """
    digitized = supply_chain_links.filter(F.col("is_digitized") == 1)

    quarterly_links = (
        digitized
        .withColumn("quarter", F.date_trunc("quarter", F.col("registration_date")))
        .groupBy("supplier_hash", "quarter")
        .agg(F.countDistinct("link_id").alias("link_count"))
    )

    window = Window.partitionBy("supplier_hash").orderBy("quarter")
    growth = (
        quarterly_links
        .withColumn("prev_count", F.lag("link_count", 1).over(window))
        .withColumn(
            "scfv",
            F.when(
                F.col("prev_count").isNotNull(),
                (F.col("link_count") - F.col("prev_count"))
                / F.greatest(F.col("prev_count"), F.lit(1))
                * 100,
            ).otherwise(F.lit(0.0)),
        )
    )

    # Take the most recent quarter
    rn_window = Window.partitionBy("supplier_hash").orderBy(F.col("quarter").desc())
    scfv = (
        growth
        .withColumn("rn", F.row_number().over(rn_window))
        .filter(F.col("rn") == 1)
        .select(
            F.col("supplier_hash").alias("national_id_hash"),
            F.greatest(F.lit(0.0), F.least(F.lit(100.0), F.col("scfv"))).alias("scfv"),
        )
    )

    return scfv


def compute_ddc_ratio(transactions: DataFrame) -> DataFrame:
    """Compute Digital Documentation Compliance (DDC) Ratio.

    Measures the operational task completion rate -- the proportion of
    transactions that have complete digital documentation (receipt,
    invoice, or confirmation attached).

    Formula:
        DDC = documented_transactions / total_transactions

    Clamped to [0.0, 1.0].

    Args:
        transactions: DataFrame with transaction records. Transactions with
            a non-null merchant_category_code are considered documented.

    Returns:
        DataFrame with columns [national_id_hash, ddc_ratio].
    """
    ddc = (
        transactions
        .groupBy("national_id_hash")
        .agg(
            F.count("*").alias("total_txn"),
            F.count(F.col("merchant_category_code")).alias("documented_txn"),
        )
        .withColumn(
            "ddc_ratio",
            F.when(
                F.col("total_txn") > 0,
                F.col("documented_txn") / F.col("total_txn"),
            ).otherwise(F.lit(0.0)),
        )
        .select(
            "national_id_hash",
            F.greatest(F.lit(0.0), F.least(F.lit(1.0), F.col("ddc_ratio"))).alias("ddc_ratio"),
        )
    )

    return ddc


def compute_niq_score(transactions: DataFrame) -> DataFrame:
    """Compute Network Interdependence and Quality (NIQ) Score.

    Calculates the average VyceScore of a customer's top 5 trading
    partners. This creates a network effect where having well-scored
    counterparties improves one's own score.

    For the initial computation (before scores exist), NIQ is based on
    the transaction volume and regularity of the top 5 counterparties.

    Formula (bootstrap):
        NIQ = normalized_mean(top_5_counterparty_volume_regularity)
        Scaled to [300, 900] to match VyceScore range.

    Args:
        transactions: DataFrame with counterparty_hash column.

    Returns:
        DataFrame with columns [national_id_hash, niq_score].
    """
    counterparty_stats = (
        transactions
        .filter(F.col("counterparty_hash").isNotNull())
        .groupBy("national_id_hash", "counterparty_hash")
        .agg(
            F.count("*").alias("txn_count"),
            F.sum("amount").alias("total_volume"),
            F.countDistinct(F.date_trunc("month", F.col("timestamp"))).alias("active_months"),
        )
        .withColumn(
            "regularity_score",
            F.col("active_months") * F.log1p(F.col("total_volume")),
        )
    )

    # Rank counterparties per customer and take top 5
    window = Window.partitionBy("national_id_hash").orderBy(F.col("regularity_score").desc())
    top5 = (
        counterparty_stats
        .withColumn("rank", F.row_number().over(window))
        .filter(F.col("rank") <= 5)
    )

    niq = (
        top5
        .groupBy("national_id_hash")
        .agg(F.mean("regularity_score").alias("mean_regularity"))
    )

    # Normalize to [300, 900] range using min-max scaling across the cohort
    stats = niq.agg(
        F.min("mean_regularity").alias("min_reg"),
        F.max("mean_regularity").alias("max_reg"),
    ).collect()[0]

    min_reg = float(stats["min_reg"]) if stats["min_reg"] is not None else 0.0
    max_reg = float(stats["max_reg"]) if stats["max_reg"] is not None else 1.0
    range_reg = max_reg - min_reg if max_reg != min_reg else 1.0

    niq_scored = (
        niq
        .withColumn(
            "niq_score",
            F.lit(300.0) + (F.col("mean_regularity") - F.lit(min_reg)) / F.lit(range_reg) * F.lit(600.0),
        )
        .select(
            "national_id_hash",
            F.greatest(F.lit(300.0), F.least(F.lit(900.0), F.col("niq_score"))).alias("niq_score"),
        )
    )

    return niq_scored


def compute_gos_index(transactions: DataFrame) -> DataFrame:
    """Compute Geographic Operational Stability (GOS) Index.

    Measures the GPS variance of transaction endpoints. Lower variance
    indicates a stable geographic operating pattern (e.g., a business
    with a fixed location), which correlates with lower credit risk.

    Formula:
        GOS = 1 - min(1, normalized_geo_variance)

    Where normalized_geo_variance is the mean of lat/lon standard
    deviations divided by a reference threshold.
    Clamped to [0.0, 1.0].

    Args:
        transactions: DataFrame with latitude and longitude columns.

    Returns:
        DataFrame with columns [national_id_hash, gos_index].
    """
    GEO_VARIANCE_THRESHOLD = 0.5  # ~55km at the equator

    geo_transactions = transactions.filter(
        F.col("latitude").isNotNull() & F.col("longitude").isNotNull()
    )

    geo_stats = (
        geo_transactions
        .groupBy("national_id_hash")
        .agg(
            F.stddev("latitude").alias("lat_std"),
            F.stddev("longitude").alias("lon_std"),
            F.count("*").alias("geo_txn_count"),
        )
        .filter(F.col("geo_txn_count") >= 3)  # Need at least 3 points for meaningful stddev
        .withColumn(
            "mean_std",
            (F.coalesce(F.col("lat_std"), F.lit(0.0)) + F.coalesce(F.col("lon_std"), F.lit(0.0))) / 2,
        )
        .withColumn(
            "normalized_variance",
            F.least(F.lit(1.0), F.col("mean_std") / F.lit(GEO_VARIANCE_THRESHOLD)),
        )
        .withColumn("gos_index", 1.0 - F.col("normalized_variance"))
        .select(
            "national_id_hash",
            F.greatest(F.lit(0.0), F.least(F.lit(1.0), F.col("gos_index"))).alias("gos_index"),
        )
    )

    return geo_stats


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def create_spark_session(app_name: str = "vycescore_feature_engineering") -> SparkSession:
    """Create and configure a SparkSession for feature engineering.

    Args:
        app_name: Name of the Spark application.

    Returns:
        Configured SparkSession.
    """
    spark = (
        SparkSession.builder
        .appName(app_name)
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.shuffle.partitions", "200")
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
        .config("spark.sql.parquet.compression.codec", "snappy")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    return spark


def run_feature_pipeline(
    spark: SparkSession,
    date: str,
    input_path: str,
    output_path: Optional[str] = None,
) -> DataFrame:
    """Execute the full feature engineering pipeline for a given date.

    Reads raw transaction and supply chain data, computes all 6 core
    features, joins them into a single feature vector per customer,
    and writes the result to the feature store.

    Args:
        spark: Active SparkSession.
        date: Processing date in YYYY-MM-DD format.
        input_path: Base path to the staged input data.
        output_path: Optional override for feature output path.

    Returns:
        DataFrame containing the computed feature vectors.
    """
    if output_path is None:
        output_path = f"s3a://vycescore-datalake/features/dt={date}/"

    # Read input data
    transactions = spark.read.schema(TRANSACTION_SCHEMA).parquet(f"{input_path}/transactions/")
    supply_chain = spark.read.schema(SUPPLY_CHAIN_SCHEMA).parquet(f"{input_path}/supply_chain/")

    # Compute all 6 features
    cblri_df = compute_cblri(transactions)
    utdi_df = compute_utdi(transactions)
    scfv_df = compute_scfv(supply_chain)
    ddc_df = compute_ddc_ratio(transactions)
    niq_df = compute_niq_score(transactions)
    gos_df = compute_gos_index(transactions)

    # Join all features on national_id_hash
    features = (
        cblri_df
        .join(utdi_df, on="national_id_hash", how="outer")
        .join(scfv_df, on="national_id_hash", how="outer")
        .join(ddc_df, on="national_id_hash", how="outer")
        .join(niq_df, on="national_id_hash", how="outer")
        .join(gos_df, on="national_id_hash", how="outer")
        .withColumn("feature_date", F.lit(date))
        .withColumn("computed_at", F.current_timestamp())
    )

    # Fill nulls with default values for customers missing certain features
    features = features.fillna({
        "cblri": 0.0,
        "utdi": 0.0,
        "scfv": 0.0,
        "ddc_ratio": 0.0,
        "niq_score": 300.0,
        "gos_index": 0.0,
    })

    # Write to feature store (Parquet, overwrite for idempotency)
    (
        features
        .repartition(10)
        .write
        .mode("overwrite")
        .parquet(output_path)
    )

    row_count = features.count()
    print(f"Computed features for {row_count} customers for date {date}")

    return features


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        args: Optional list of arguments (defaults to sys.argv).

    Returns:
        Parsed namespace with date and input_path.
    """
    parser = argparse.ArgumentParser(description="VyceScore Feature Engineering Job")
    parser.add_argument("--date", required=True, help="Processing date (YYYY-MM-DD)")
    parser.add_argument("--input-path", required=True, help="Base path to staged input data")
    parser.add_argument("--output-path", default=None, help="Optional output path override")
    return parser.parse_args(args)


if __name__ == "__main__":
    args = parse_args()

    spark = create_spark_session()
    try:
        run_feature_pipeline(
            spark=spark,
            date=args.date,
            input_path=args.input_path,
            output_path=args.output_path,
        )
    finally:
        spark.stop()
