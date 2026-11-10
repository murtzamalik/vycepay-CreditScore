"""XGBoost training pipeline for VyceScore credit scoring model.

Loads feature data, trains an XGBoost binary classifier to predict
probability of serious delinquency (90+ DPD within 12 months),
evaluates against performance targets, and logs everything to MLflow.
"""

from __future__ import annotations

import logging
from typing import Any

import mlflow
import mlflow.xgboost
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split

from ml.evaluation.metrics import auc_roc, calibration_error, precision_at_k
from ml.models.xgboost.hyperparams import (
    CORE_FEATURES,
    DEFAULT_PARAMS,
    PERFORMANCE_TARGETS,
)

logger = logging.getLogger(__name__)

TARGET_COLUMN = "is_delinquent_90dpd"


def train_model(
    df: pd.DataFrame,
    *,
    params: dict[str, Any] | None = None,
    feature_columns: list[str] | None = None,
    test_size: float = 0.2,
    experiment_name: str = "vycescore-xgboost",
    run_name: str | None = None,
) -> tuple[xgb.XGBClassifier, dict[str, float]]:
    """Train an XGBoost model for credit scoring.

    Args:
        df: DataFrame containing feature columns and the binary target
            column ``is_delinquent_90dpd`` (1 = 90+ DPD within 12 months).
        params: XGBoost hyperparameters. Falls back to DEFAULT_PARAMS.
        feature_columns: Features to use. Falls back to CORE_FEATURES.
        test_size: Fraction of data held out for evaluation.
        experiment_name: MLflow experiment name.
        run_name: Optional MLflow run name.

    Returns:
        Tuple of (trained XGBClassifier, dict of evaluation metrics).

    Raises:
        ValueError: If required columns are missing from the DataFrame.
    """
    features = feature_columns or CORE_FEATURES
    hyper = {**DEFAULT_PARAMS, **(params or {})}

    # --- Validate input -------------------------------------------------
    missing = [c for c in [*features, TARGET_COLUMN] if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in DataFrame: {missing}")

    X = df[features].copy()
    y = df[TARGET_COLUMN].copy()

    logger.info(
        "Training data: %d rows, %d features, %.2f%% positive rate",
        len(X),
        len(features),
        y.mean() * 100,
    )

    # --- Train / test split ---------------------------------------------
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=hyper.get("random_state", 42), stratify=y
    )

    # --- Pop params that are not XGBClassifier constructor args ----------
    early_stopping_rounds = hyper.pop("early_stopping_rounds", 50)

    # --- Train -----------------------------------------------------------
    model = xgb.XGBClassifier(**hyper)
    model.fit(
        X_train,
        y_train,
        eval_set=[(X_test, y_test)],
        verbose=False,
    )

    # --- Evaluate --------------------------------------------------------
    y_prob = model.predict_proba(X_test)[:, 1]

    metrics: dict[str, float] = {
        "auc_roc": auc_roc(y_test.values, y_prob),
        "precision_at_1000": precision_at_k(y_test.values, y_prob, k=1000),
        "calibration_error": calibration_error(y_test.values, y_prob),
        "positive_rate": float(y.mean()),
        "train_size": len(X_train),
        "test_size": len(X_test),
    }

    _check_performance_targets(metrics)

    # --- Log to MLflow ---------------------------------------------------
    mlflow.set_experiment(experiment_name)
    with mlflow.start_run(run_name=run_name):
        mlflow.log_params(hyper)
        mlflow.log_metrics(metrics)
        mlflow.xgboost.log_model(model, artifact_path="model")
        mlflow.log_param("features", features)

    logger.info("Training complete. Metrics: %s", metrics)
    return model, metrics


def _check_performance_targets(metrics: dict[str, float]) -> None:
    """Log warnings if any metric falls below acceptance thresholds."""
    for metric_name, threshold in PERFORMANCE_TARGETS.items():
        actual = metrics.get(metric_name)
        if actual is None:
            continue
        if metric_name == "calibration_error":
            # Lower is better
            if actual > threshold:
                logger.warning(
                    "BELOW TARGET: %s = %.4f (target < %.4f)",
                    metric_name, actual, threshold,
                )
        else:
            # Higher is better
            if actual < threshold:
                logger.warning(
                    "BELOW TARGET: %s = %.4f (target > %.4f)",
                    metric_name, actual, threshold,
                )
