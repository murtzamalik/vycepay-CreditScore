"""XGBoost training pipeline for VyceScore credit scoring model.

Trains a binary classifier to predict probability of Serious Delinquency
(90+ DPD within 12 months).  Supports both VOD proxy labels (Phase 1) and
ground-truth loan outcomes (Phase 2).

Training flow:
    1. Validate input data and feature columns.
    2. Split into train / validation / test (60/20/20).
    3. Train XGBoost with BRD-specified hyperparameters.
    4. Evaluate on held-out test set.
    5. Save model artifact to disk.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split

logger = logging.getLogger(__name__)

# Default feature columns — the six core VyceScore features.
CORE_FEATURES: list[str] = [
    "cblri",
    "utdi",
    "scfv",
    "ddc_ratio",
    "niq_score",
    "gos_index",
]

TARGET_COLUMN = "label"

# BRD-specified hyperparameters (Section 5.2).
BRD_HYPERPARAMETERS: dict[str, Any] = {
    "objective": "binary:logistic",
    "eval_metric": "auc",
    "max_depth": 6,
    "learning_rate": 0.05,
    "n_estimators": 500,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 3,
    "gamma": 0.1,
    "scale_pos_weight": 3,
    "random_state": 42,
    "n_jobs": -1,
    "tree_method": "hist",
    "use_label_encoder": False,
}


@dataclass(frozen=True)
class TrainingConfig:
    """Configuration for the training pipeline.

    Attributes:
        feature_columns: Feature column names to use for training.
        target_column: Name of the binary target column.
        hyperparameters: XGBoost hyperparameters.
        train_ratio: Fraction of data for training.
        val_ratio: Fraction of data for validation.
        test_ratio: Fraction of data for testing.
        early_stopping_rounds: Patience for early stopping on validation set.
        random_seed: Seed for reproducibility.
        model_output_dir: Directory to save trained model artifacts.
    """

    feature_columns: tuple[str, ...] = tuple(CORE_FEATURES)
    target_column: str = TARGET_COLUMN
    hyperparameters: dict[str, Any] = field(default_factory=lambda: dict(BRD_HYPERPARAMETERS))
    train_ratio: float = 0.60
    val_ratio: float = 0.20
    test_ratio: float = 0.20
    early_stopping_rounds: int = 50
    random_seed: int = 42
    model_output_dir: str = "artifacts/models"

    def __post_init__(self) -> None:
        total = self.train_ratio + self.val_ratio + self.test_ratio
        if not (0.99 <= total <= 1.01):
            raise ValueError(
                f"Split ratios must sum to 1.0, got {total:.2f}"
            )


@dataclass
class TrainingResult:
    """Result of a training run.

    Attributes:
        model: Trained XGBoost classifier.
        metrics: Evaluation metrics on the test set.
        feature_columns: Features used during training.
        hyperparameters: Hyperparameters used.
        model_path: Path where the model was saved (None if not saved).
        train_size: Number of training samples.
        val_size: Number of validation samples.
        test_size: Number of test samples.
        positive_rate: Fraction of positive labels in training data.
        training_timestamp: UTC timestamp of training completion.
    """

    model: xgb.XGBClassifier
    metrics: dict[str, float]
    feature_columns: list[str]
    hyperparameters: dict[str, Any]
    model_path: str | None
    train_size: int
    val_size: int
    test_size: int
    positive_rate: float
    training_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


def validate_training_data(
    df: pd.DataFrame,
    config: TrainingConfig,
) -> list[str]:
    """Validate that the DataFrame has the required columns and data quality.

    Args:
        df: Input DataFrame.
        config: Training configuration.

    Returns:
        List of validation error messages (empty if valid).
    """
    errors: list[str] = []

    # Check required columns
    required = list(config.feature_columns) + [config.target_column]
    missing = [c for c in required if c not in df.columns]
    if missing:
        errors.append(f"Missing columns: {missing}")

    if errors:
        return errors

    # Check for sufficient data
    if len(df) < 10:
        errors.append(f"Insufficient data: {len(df)} rows (minimum 10)")

    # Check target column values
    unique_labels = df[config.target_column].dropna().unique()
    valid_labels = {0, 1}
    invalid = set(unique_labels) - valid_labels
    if invalid:
        errors.append(
            f"Invalid labels in target column: {invalid}. "
            f"Expected only {valid_labels}."
        )

    # Check both classes exist
    if len(set(unique_labels) & valid_labels) < 2:
        errors.append(
            "Target column must contain both positive (1) and "
            "negative (0) samples."
        )

    # Check for NaN in features
    feature_nans = df[list(config.feature_columns)].isna().sum()
    nan_cols = feature_nans[feature_nans > 0]
    if len(nan_cols) > 0:
        errors.append(
            f"NaN values in feature columns: "
            f"{dict(nan_cols)}"
        )

    return errors


def split_data(
    df: pd.DataFrame,
    config: TrainingConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split data into train, validation, and test sets.

    Uses stratified splitting to preserve class distribution.

    Args:
        df: Input DataFrame.
        config: Training configuration.

    Returns:
        Tuple of (train_df, val_df, test_df).
    """
    # First split: separate test set
    test_fraction = config.test_ratio
    train_val_fraction = 1.0 - test_fraction

    train_val_df, test_df = train_test_split(
        df,
        test_size=test_fraction,
        random_state=config.random_seed,
        stratify=df[config.target_column],
    )

    # Second split: separate validation from training
    # val_ratio relative to train_val = val_ratio / (train_ratio + val_ratio)
    val_relative = config.val_ratio / train_val_fraction
    train_df, val_df = train_test_split(
        train_val_df,
        test_size=val_relative,
        random_state=config.random_seed,
        stratify=train_val_df[config.target_column],
    )

    logger.info(
        "Data split: train=%d, val=%d, test=%d (total=%d)",
        len(train_df),
        len(val_df),
        len(test_df),
        len(df),
    )

    return train_df, val_df, test_df


def train_model(
    df: pd.DataFrame,
    config: TrainingConfig | None = None,
    *,
    save_model: bool = True,
) -> TrainingResult:
    """Train an XGBoost classifier for credit scoring.

    Args:
        df: DataFrame containing feature columns and binary target.
        config: Training configuration. Uses defaults if None.
        save_model: Whether to save the model artifact to disk.

    Returns:
        TrainingResult with model, metrics, and metadata.

    Raises:
        ValueError: If input data validation fails.
    """
    if config is None:
        config = TrainingConfig()

    # Validate
    errors = validate_training_data(df, config)
    if errors:
        raise ValueError(
            f"Training data validation failed: {'; '.join(errors)}"
        )

    feature_cols = list(config.feature_columns)
    target_col = config.target_column

    logger.info(
        "Starting training: %d rows, %d features, %.2f%% positive rate",
        len(df),
        len(feature_cols),
        df[target_col].mean() * 100,
    )

    # Split data
    train_df, val_df, test_df = split_data(df, config)

    X_train = train_df[feature_cols]
    y_train = train_df[target_col]
    X_val = val_df[feature_cols]
    y_val = val_df[target_col]
    X_test = test_df[feature_cols]
    y_test = test_df[target_col]

    # Build hyperparameters — exclude non-constructor params
    hyper = dict(config.hyperparameters)
    early_stopping = config.early_stopping_rounds

    # Train
    model = xgb.XGBClassifier(**hyper)
    model.fit(
        X_train,
        y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )

    # Evaluate on test set
    y_prob = model.predict_proba(X_test)[:, 1]
    metrics = _compute_metrics(y_test.values, y_prob)

    logger.info("Training complete. Metrics: %s", metrics)

    # Save model
    model_path: str | None = None
    if save_model:
        model_path = _save_model_artifact(model, feature_cols, metrics, config)

    return TrainingResult(
        model=model,
        metrics=metrics,
        feature_columns=feature_cols,
        hyperparameters=hyper,
        model_path=model_path,
        train_size=len(train_df),
        val_size=len(val_df),
        test_size=len(test_df),
        positive_rate=float(df[target_col].mean()),
    )


def _compute_metrics(
    y_true: np.ndarray,
    y_prob: np.ndarray,
) -> dict[str, float]:
    """Compute evaluation metrics for the trained model.

    Imports from ml.evaluation.metrics to reuse existing implementations.
    """
    from ml.evaluation.metrics import (
        auc_roc,
        calibration_error,
        ks_statistic,
        precision_at_k,
    )

    return {
        "auc_roc": auc_roc(y_true, y_prob),
        "precision_at_1000": precision_at_k(y_true, y_prob, k=1000),
        "calibration_error": calibration_error(y_true, y_prob),
        "ks_statistic": ks_statistic(y_true, y_prob),
        "positive_rate_test": float(np.mean(y_true)),
        "n_test_samples": int(len(y_true)),
    }


def _save_model_artifact(
    model: xgb.XGBClassifier,
    feature_columns: list[str],
    metrics: dict[str, float],
    config: TrainingConfig,
) -> str:
    """Save trained model and metadata to disk.

    Returns:
        Path to the saved model file.
    """
    output_dir = Path(config.model_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    model_filename = f"xgboost_vycescore_{timestamp}.json"
    model_path = output_dir / model_filename

    # Save XGBoost model
    model.save_model(str(model_path))

    # Save metadata alongside
    metadata = {
        "model_file": model_filename,
        "feature_columns": feature_columns,
        "metrics": metrics,
        "hyperparameters": {
            k: v for k, v in config.hyperparameters.items()
            if isinstance(v, (int, float, str, bool))
        },
        "training_timestamp": datetime.now(timezone.utc).isoformat(),
    }
    meta_path = output_dir / f"metadata_{timestamp}.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info("Model saved to %s", model_path)
    return str(model_path)
