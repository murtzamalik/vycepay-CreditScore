"""MLflow experiment tracking for VyceScore model training.

Logs hyperparameters, metrics, and model artifacts to MLflow.
Supports model versioning with staging/production lifecycle management.

Model naming convention: xgb_{YYYY}_{MM}_v{N}
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import mlflow
import mlflow.xgboost
import xgboost as xgb

logger = logging.getLogger(__name__)

MODEL_NAME_PREFIX = "xgb"
REGISTERED_MODEL_NAME = "vycescore-xgboost"


class ModelStage:
    """Model lifecycle stages for the MLflow registry."""

    STAGING = "Staging"
    PRODUCTION = "Production"
    ARCHIVED = "Archived"
    NONE = "None"


@dataclass
class ExperimentConfig:
    """Configuration for MLflow experiment tracking.

    Attributes:
        experiment_name: MLflow experiment name.
        tracking_uri: MLflow tracking server URI. None uses local file store.
        registered_model_name: Name for the model in the MLflow registry.
        auto_register: Whether to automatically register the model.
        tags: Additional tags to attach to the run.
    """

    experiment_name: str = "vycescore-training"
    tracking_uri: str | None = None
    registered_model_name: str = REGISTERED_MODEL_NAME
    auto_register: bool = True
    tags: dict[str, str] = field(default_factory=dict)


def generate_model_version_name(version: int = 1) -> str:
    """Generate a model version name following the naming convention.

    Format: xgb_{YYYY}_{MM}_v{N}

    Args:
        version: Version number.

    Returns:
        Formatted model version name.
    """
    now = datetime.now(timezone.utc)
    return f"{MODEL_NAME_PREFIX}_{now.year}_{now.month:02d}_v{version}"


def log_training_run(
    model: xgb.XGBClassifier,
    metrics: dict[str, float],
    hyperparameters: dict[str, Any],
    feature_columns: list[str],
    config: ExperimentConfig | None = None,
    *,
    run_name: str | None = None,
    extra_params: dict[str, Any] | None = None,
    extra_metrics: dict[str, float] | None = None,
    train_size: int | None = None,
    val_size: int | None = None,
    test_size: int | None = None,
) -> str:
    """Log a training run to MLflow.

    Args:
        model: Trained XGBoost classifier.
        metrics: Evaluation metrics dict.
        hyperparameters: Hyperparameters used for training.
        feature_columns: Feature column names used.
        config: Experiment configuration.
        run_name: Optional name for this run.
        extra_params: Additional parameters to log.
        extra_metrics: Additional metrics to log.
        train_size: Number of training samples.
        val_size: Number of validation samples.
        test_size: Number of test samples.

    Returns:
        MLflow run ID.
    """
    if config is None:
        config = ExperimentConfig()

    if config.tracking_uri:
        mlflow.set_tracking_uri(config.tracking_uri)

    mlflow.set_experiment(config.experiment_name)

    with mlflow.start_run(run_name=run_name) as run:
        # Log hyperparameters
        safe_params = {
            k: v for k, v in hyperparameters.items()
            if isinstance(v, (int, float, str, bool))
        }
        mlflow.log_params(safe_params)

        # Log feature columns as a parameter
        mlflow.log_param("feature_columns", str(feature_columns))
        mlflow.log_param("n_features", len(feature_columns))

        # Log dataset sizes
        if train_size is not None:
            mlflow.log_param("train_size", train_size)
        if val_size is not None:
            mlflow.log_param("val_size", val_size)
        if test_size is not None:
            mlflow.log_param("test_size", test_size)

        # Log extra params
        if extra_params:
            safe_extra = {
                k: v for k, v in extra_params.items()
                if isinstance(v, (int, float, str, bool))
            }
            mlflow.log_params(safe_extra)

        # Log metrics
        mlflow.log_metrics(metrics)
        if extra_metrics:
            mlflow.log_metrics(extra_metrics)

        # Log tags
        for key, value in config.tags.items():
            mlflow.set_tag(key, value)
        mlflow.set_tag("model_type", "xgboost")

        # Log model artifact
        artifact_path = "model"
        if config.auto_register:
            mlflow.xgboost.log_model(
                model,
                artifact_path=artifact_path,
                registered_model_name=config.registered_model_name,
            )
            logger.info(
                "Model logged and registered as '%s'",
                config.registered_model_name,
            )
        else:
            mlflow.xgboost.log_model(model, artifact_path=artifact_path)
            logger.info("Model logged (not registered)")

        run_id = run.info.run_id
        logger.info("MLflow run completed: %s", run_id)
        return run_id


def transition_model_stage(
    model_name: str,
    version: int,
    stage: str,
    *,
    tracking_uri: str | None = None,
    archive_existing: bool = True,
) -> None:
    """Transition a model version to a new stage.

    Args:
        model_name: Registered model name.
        version: Model version number.
        stage: Target stage (Staging, Production, Archived).
        tracking_uri: MLflow tracking URI.
        archive_existing: If True, archive existing models in the target
            stage before transitioning.
    """
    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)

    client = mlflow.tracking.MlflowClient()

    valid_stages = {ModelStage.STAGING, ModelStage.PRODUCTION, ModelStage.ARCHIVED, ModelStage.NONE}
    if stage not in valid_stages:
        raise ValueError(f"Invalid stage '{stage}'. Must be one of {valid_stages}")

    client.transition_model_version_stage(
        name=model_name,
        version=str(version),
        stage=stage,
        archive_existing_versions=archive_existing,
    )

    logger.info(
        "Model '%s' version %d transitioned to stage '%s'",
        model_name,
        version,
        stage,
    )


def get_production_model_uri(
    model_name: str = REGISTERED_MODEL_NAME,
) -> str:
    """Get the MLflow URI for the current production model.

    Args:
        model_name: Registered model name.

    Returns:
        MLflow model URI string.
    """
    return f"models:/{model_name}/Production"


def log_evaluation_report(
    report: dict[str, Any],
    run_id: str,
    *,
    tracking_uri: str | None = None,
) -> None:
    """Log an evaluation report as an artifact to an existing MLflow run.

    Args:
        report: Evaluation report dictionary.
        run_id: MLflow run ID to attach the artifact to.
        tracking_uri: MLflow tracking URI.
    """
    import json
    import tempfile

    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)

    client = mlflow.tracking.MlflowClient()

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as f:
        json.dump(report, f, indent=2, default=str)
        temp_path = f.name

    client.log_artifact(run_id, temp_path, artifact_path="reports")
    logger.info("Evaluation report logged to run %s", run_id)
