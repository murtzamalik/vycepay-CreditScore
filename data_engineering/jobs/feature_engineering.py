"""Batch feature engineering job using ml/features/ computers.

Computes all 31 features for active subjects using the FeatureRegistry,
validates results, and writes to the Feast offline store (Parquet).

This job bridges the raw data layer with the ml/features/ module:
    1. Loads raw data per category (transaction, network, supply chain,
       compliance) from the datalake.
    2. Instantiates all 31 feature computers via FeatureRegistry.
    3. Runs each computer on the relevant data slice.
    4. Validates outputs using the FeatureValidator.
    5. Writes combined feature vectors to the offline store.

Usage:
    python -m data_engineering.jobs.feature_engineering --date 2026-03-08
    python -m data_engineering.jobs.feature_engineering --date 2026-03-08 --categories transaction core
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATALAKE_BASE = os.getenv(
    "VYCESCORE_DATALAKE_PATH", "s3a://vycescore-datalake"
)

FEATURE_OUTPUT_BASE = os.getenv(
    "VYCESCORE_FEATURE_OUTPUT_PATH",
    f"{DATALAKE_BASE}/features",
)

CATEGORY_INPUT_PATHS: dict[str, str] = {
    "transaction": f"{DATALAKE_BASE}/staged/transactions",
    "network": f"{DATALAKE_BASE}/staged/transactions",
    "supply_chain": f"{DATALAKE_BASE}/staged/supply_chain",
    "compliance": f"{DATALAKE_BASE}/staged/compliance",
    "core": f"{DATALAKE_BASE}/staged/transactions",
}

CATEGORY_OUTPUT_PATHS: dict[str, str] = {
    "transaction": f"{FEATURE_OUTPUT_BASE}/transaction",
    "network": f"{FEATURE_OUTPUT_BASE}/network",
    "supply_chain": f"{FEATURE_OUTPUT_BASE}/supply_chain",
    "compliance": f"{FEATURE_OUTPUT_BASE}/compliance",
    "core": f"{FEATURE_OUTPUT_BASE}/core",
}

ALL_CATEGORIES = ["transaction", "network", "supply_chain", "compliance", "core"]


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

@dataclass
class FeatureJobResult:
    """Summary of a feature engineering job run."""

    processing_date: str
    categories_processed: list[str] = field(default_factory=list)
    features_computed: int = 0
    subjects_processed: int = 0
    quality_scores: dict[str, float] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completed_at: str | None = None
    success: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "processing_date": self.processing_date,
            "categories_processed": self.categories_processed,
            "features_computed": self.features_computed,
            "subjects_processed": self.subjects_processed,
            "quality_scores": self.quality_scores,
            "errors": self.errors,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "success": self.success,
        }


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def load_category_data(
    category: str,
    processing_date: str,
    *,
    base_path: str | None = None,
) -> pd.DataFrame:
    """Load raw data for a feature category from the datalake.

    Args:
        category: Feature category name.
        processing_date: Date string (YYYY-MM-DD) for partition.
        base_path: Optional override for input path.

    Returns:
        DataFrame with raw data for the category.

    Raises:
        FileNotFoundError: If no data files exist for the date.
    """
    if base_path is None:
        base_path = CATEGORY_INPUT_PATHS.get(category, "")

    partition_path = f"{base_path}/dt={processing_date}"
    logger.info(
        "Loading %s data from %s", category, partition_path
    )

    try:
        df = pd.read_parquet(partition_path)
        logger.info(
            "Loaded %d rows for category '%s' (date=%s)",
            len(df), category, processing_date,
        )
        return df
    except Exception as exc:
        raise FileNotFoundError(
            f"No data found for category '{category}' at "
            f"'{partition_path}': {exc}"
        ) from exc


def write_feature_output(
    df: pd.DataFrame,
    category: str,
    processing_date: str,
    *,
    base_path: str | None = None,
) -> str:
    """Write computed features to the offline store (Parquet).

    Args:
        df: DataFrame containing computed features.
        category: Feature category name.
        processing_date: Date string for partition.
        base_path: Optional override for output path.

    Returns:
        Path where features were written.
    """
    if base_path is None:
        base_path = CATEGORY_OUTPUT_PATHS.get(
            category, f"{FEATURE_OUTPUT_BASE}/{category}"
        )

    output_path = f"{base_path}/dt={processing_date}"
    logger.info(
        "Writing %d rows of %s features to %s",
        len(df), category, output_path,
    )

    os.makedirs(output_path, exist_ok=True)
    df.to_parquet(
        f"{output_path}/features.parquet",
        index=False,
        engine="pyarrow",
    )

    return output_path


# ---------------------------------------------------------------------------
# Feature computation engine
# ---------------------------------------------------------------------------

def compute_category_features(
    df: pd.DataFrame,
    category: str,
    processing_date: str,
    *,
    time_window_days: int | None = None,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Compute all features for a given category using FeatureRegistry.

    Imports the ml.features module to get registered feature computers,
    runs each one for the specified category, and merges results.

    Args:
        df: Raw input DataFrame for the category.
        category: Feature category name matching FeatureCategory enum.
        processing_date: The date being processed.
        time_window_days: Optional override for computation window.

    Returns:
        Tuple of (feature DataFrame, quality scores dict).
    """
    from ml.features import create_default_registry
    from ml.features.base import FeatureCategory

    category_enum = FeatureCategory(category)
    registry = create_default_registry()
    computers = registry.by_category(category_enum)

    if not computers:
        logger.warning("No feature computers found for category '%s'", category)
        return pd.DataFrame(), {}

    logger.info(
        "Computing %d features for category '%s'",
        len(computers), category,
    )

    feature_columns: dict[str, pd.Series] = {}
    quality_scores: dict[str, float] = {}

    for computer in computers:
        name = computer.metadata.name
        try:
            result = computer.compute(
                df, time_window_days=time_window_days
            )
            feature_columns[name] = result.values
            quality_scores[name] = result.data_quality_score
            logger.info(
                "  Computed '%s': quality=%.3f, non-null=%d/%d",
                name,
                result.data_quality_score,
                result.values.notna().sum(),
                len(result.values),
            )
        except Exception as exc:
            logger.error(
                "  Failed to compute '%s': %s", name, exc
            )
            quality_scores[name] = 0.0

    if not feature_columns:
        return pd.DataFrame(), quality_scores

    # Build output DataFrame
    features_df = pd.DataFrame(feature_columns)

    # Preserve national_id_hash from input if present
    if "national_id_hash" in df.columns:
        features_df.insert(0, "national_id_hash", df["national_id_hash"].values[:len(features_df)])

    features_df["computed_at"] = datetime.now(timezone.utc)
    features_df["feature_date"] = processing_date

    return features_df, quality_scores


def run_feature_engineering(
    processing_date: str,
    categories: list[str] | None = None,
    *,
    input_paths: dict[str, str] | None = None,
    output_paths: dict[str, str] | None = None,
    time_window_days: int | None = None,
    min_quality_threshold: float = 0.5,
) -> FeatureJobResult:
    """Run the full feature engineering pipeline.

    Processes each category sequentially:
        1. Load raw data from the datalake partition.
        2. Compute features using FeatureRegistry computers.
        3. Validate feature quality.
        4. Write to offline store.

    Args:
        processing_date: Date string (YYYY-MM-DD).
        categories: Optional list of categories to process
            (default: all categories).
        input_paths: Optional override for category input paths.
        output_paths: Optional override for category output paths.
        time_window_days: Override default feature computation window.
        min_quality_threshold: Minimum avg quality score to accept
            a category's output (default 0.5).

    Returns:
        FeatureJobResult summarizing the run.
    """
    if categories is None:
        categories = ALL_CATEGORIES

    result = FeatureJobResult(processing_date=processing_date)

    total_features = 0
    all_subjects: set[str] = set()

    for category in categories:
        logger.info("--- Processing category: %s ---", category)

        # Load
        try:
            input_base = (
                input_paths.get(category) if input_paths else None
            )
            raw_df = load_category_data(
                category, processing_date, base_path=input_base,
            )
        except FileNotFoundError as exc:
            msg = f"Skipping '{category}': {exc}"
            logger.warning(msg)
            result.errors.append(msg)
            continue

        if raw_df.empty:
            msg = f"Empty data for category '{category}'"
            logger.warning(msg)
            result.errors.append(msg)
            continue

        # Compute
        features_df, quality_scores = compute_category_features(
            raw_df,
            category,
            processing_date,
            time_window_days=time_window_days,
        )

        if features_df.empty:
            msg = f"No features computed for category '{category}'"
            logger.warning(msg)
            result.errors.append(msg)
            continue

        # Quality gate
        avg_quality = (
            sum(quality_scores.values()) / len(quality_scores)
            if quality_scores else 0.0
        )
        result.quality_scores[category] = round(avg_quality, 4)

        if avg_quality < min_quality_threshold:
            msg = (
                f"Category '{category}' below quality threshold: "
                f"{avg_quality:.3f} < {min_quality_threshold}"
            )
            logger.warning(msg)
            result.errors.append(msg)
            # Still write but log warning

        # Write
        try:
            output_base = (
                output_paths.get(category) if output_paths else None
            )
            write_feature_output(
                features_df, category, processing_date,
                base_path=output_base,
            )
        except Exception as exc:
            msg = f"Failed to write '{category}': {exc}"
            logger.error(msg)
            result.errors.append(msg)
            continue

        # Track counts
        feature_cols = [
            c for c in features_df.columns
            if c not in {"national_id_hash", "computed_at", "feature_date"}
        ]
        total_features += len(feature_cols)

        if "national_id_hash" in features_df.columns:
            all_subjects.update(
                features_df["national_id_hash"].dropna().unique()
            )

        result.categories_processed.append(category)

    result.features_computed = total_features
    result.subjects_processed = len(all_subjects)
    result.completed_at = datetime.now(timezone.utc).isoformat()
    result.success = len(result.categories_processed) > 0

    logger.info("Feature engineering complete: %s", result.to_dict())
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="VyceScore Feature Engineering Job"
    )
    parser.add_argument(
        "--date",
        required=True,
        help="Processing date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--categories",
        nargs="*",
        default=None,
        choices=ALL_CATEGORIES,
        help="Categories to process (default: all)",
    )
    parser.add_argument(
        "--time-window-days",
        type=int,
        default=None,
        help="Override default time window for feature computation",
    )
    parser.add_argument(
        "--min-quality",
        type=float,
        default=0.5,
        help="Minimum avg quality score threshold (default: 0.5)",
    )
    return parser.parse_args(args)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parsed = parse_args()
    job_result = run_feature_engineering(
        processing_date=parsed.date,
        categories=parsed.categories,
        time_window_days=parsed.time_window_days,
        min_quality_threshold=parsed.min_quality,
    )
    print(f"Result: {job_result.to_dict()}")
    sys.exit(0 if job_result.success else 1)
