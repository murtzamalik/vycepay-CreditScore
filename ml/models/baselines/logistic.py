"""Logistic regression baseline for VyceScore.

A simple L2-regularized logistic regression model used as a performance
floor. If the XGBoost model cannot meaningfully beat this baseline, the
added complexity is not justified.
"""

from __future__ import annotations

import logging
from typing import Any

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from ml.evaluation.metrics import auc_roc, calibration_error, precision_at_k
from ml.models.xgboost.hyperparams import CORE_FEATURES

logger = logging.getLogger(__name__)

TARGET_COLUMN = "is_delinquent_90dpd"


def train_baseline(
    df: pd.DataFrame,
    *,
    feature_columns: list[str] | None = None,
    test_size: float = 0.2,
    C: float = 1.0,
    experiment_name: str = "vycescore-baseline-logistic",
) -> tuple[LogisticRegression, StandardScaler, dict[str, float]]:
    """Train a logistic regression baseline model.

    Args:
        df: DataFrame with feature columns and ``is_delinquent_90dpd`` target.
        feature_columns: Feature names. Falls back to CORE_FEATURES.
        test_size: Fraction held out for evaluation.
        C: Inverse regularization strength.
        experiment_name: MLflow experiment name.

    Returns:
        Tuple of (fitted LogisticRegression, fitted StandardScaler, metrics dict).
    """
    features = feature_columns or CORE_FEATURES

    X = df[features].copy()
    y = df[TARGET_COLUMN].copy()

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=42, stratify=y
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    model = LogisticRegression(
        C=C,
        class_weight="balanced",
        max_iter=1000,
        random_state=42,
        solver="lbfgs",
    )
    model.fit(X_train_scaled, y_train)

    y_prob = model.predict_proba(X_test_scaled)[:, 1]

    metrics: dict[str, float] = {
        "auc_roc": auc_roc(y_test.values, y_prob),
        "precision_at_1000": precision_at_k(y_test.values, y_prob, k=1000),
        "calibration_error": calibration_error(y_test.values, y_prob),
    }

    mlflow.set_experiment(experiment_name)
    with mlflow.start_run(run_name="logistic-baseline"):
        mlflow.log_params({"C": C, "features": features})
        mlflow.log_metrics(metrics)
        mlflow.sklearn.log_model(model, artifact_path="model")

    logger.info("Baseline logistic regression metrics: %s", metrics)
    return model, scaler, metrics
