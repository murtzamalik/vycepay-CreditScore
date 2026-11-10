"""Automated retraining pipeline for VyceScore active learning.

Assembles training data from all label sources (VOD + ground truth),
trains a new model using the existing pipeline, evaluates against the
current production model, and registers in MLflow if performance improves.

Retraining flow:
    1. Assemble combined training data from VOD and ground truth.
    2. Validate data quality and sufficiency.
    3. Train new candidate model using ``ml.training.pipeline.train_model``.
    4. Evaluate candidate against production model metrics.
    5. If candidate passes all gates and outperforms production, register
       in MLflow as a Staging model.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb

from ml.active_learning.ground_truth import (
    GroundTruthConfig,
    GroundTruthStats,
    convert_loan_outcomes_to_labels,
    merge_labels,
)
from ml.training.pipeline import (
    CORE_FEATURES,
    TARGET_COLUMN,
    TrainingConfig,
    TrainingResult,
    train_model,
)

logger = logging.getLogger(__name__)


class RetrainingOutcome(str, Enum):
    """Outcome of an automated retraining attempt."""

    SUCCESS = "success"
    INSUFFICIENT_DATA = "insufficient_data"
    VALIDATION_FAILED = "validation_failed"
    NO_IMPROVEMENT = "no_improvement"
    GATE_FAILED = "gate_failed"
    ERROR = "error"


@dataclass(frozen=True)
class RetrainingConfig:
    """Configuration for the retraining pipeline.

    Attributes:
        min_total_samples: Minimum samples required to retrain.
        min_ground_truth_samples: Minimum ground truth samples needed.
        min_improvement_auc: AUC-ROC must improve by at least this much
            over the production model to be registered.
        training_config: Base training config to use.
        ground_truth_config: Configuration for ground truth integration.
        feature_columns: Features to train on.
        register_in_mlflow: Whether to register the model in MLflow.
    """

    min_total_samples: int = 500
    min_ground_truth_samples: int = 100
    min_improvement_auc: float = 0.005
    training_config: TrainingConfig = field(default_factory=TrainingConfig)
    ground_truth_config: GroundTruthConfig = field(default_factory=GroundTruthConfig)
    feature_columns: tuple[str, ...] = tuple(CORE_FEATURES)
    register_in_mlflow: bool = True


@dataclass
class RetrainingResult:
    """Result of an automated retraining run.

    Attributes:
        outcome: The retraining outcome.
        training_result: The training result (None if not trained).
        production_metrics: Metrics of the current production model.
        candidate_metrics: Metrics of the candidate model.
        ground_truth_stats: Statistics from ground truth integration.
        message: Human-readable summary.
        mlflow_run_id: MLflow run ID (None if not registered).
        timestamp: UTC timestamp of the retraining attempt.
    """

    outcome: RetrainingOutcome
    training_result: TrainingResult | None = None
    production_metrics: dict[str, float] = field(default_factory=dict)
    candidate_metrics: dict[str, float] = field(default_factory=dict)
    ground_truth_stats: GroundTruthStats | None = None
    message: str = ""
    mlflow_run_id: str | None = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


def assemble_training_data(
    vod_df: pd.DataFrame,
    feedback_df: pd.DataFrame,
    feature_df: pd.DataFrame,
    config: RetrainingConfig | None = None,
) -> tuple[pd.DataFrame, GroundTruthStats]:
    """Assemble combined training data from all label sources.

    Args:
        vod_df: VOD-labeled data (from ``vod.labeling.assign_labels_batch``).
        feedback_df: Raw loan feedback data (from ``loan_feedback`` table).
        feature_df: Feature data with feature columns indexed by ``entity_id``.
        config: Retraining configuration.

    Returns:
        Tuple of (training-ready DataFrame with features + label, stats).
    """
    if config is None:
        config = RetrainingConfig()

    # Convert loan outcomes to labels
    gt_labels = convert_loan_outcomes_to_labels(
        feedback_df, config=config.ground_truth_config
    )

    # Merge VOD + ground truth labels
    merged_labels, stats = merge_labels(
        vod_df, gt_labels, config=config.ground_truth_config
    )

    if merged_labels.empty:
        logger.warning("No labels available after merging.")
        return pd.DataFrame(), stats

    # Join with features
    if "entity_id" in feature_df.columns:
        features = feature_df.set_index("entity_id")
    else:
        features = feature_df.copy()

    if "entity_id" in merged_labels.columns:
        labels = merged_labels.set_index("entity_id")
    else:
        labels = merged_labels.copy()

    # Ensure feature columns exist
    feature_cols = list(config.feature_columns)
    available_features = [c for c in feature_cols if c in features.columns]

    if not available_features:
        logger.warning("No feature columns found in feature data.")
        return pd.DataFrame(), stats

    # Drop feature columns that already exist in labels to avoid overlap
    overlap_cols = [c for c in available_features if c in labels.columns]
    if overlap_cols:
        labels = labels.drop(columns=overlap_cols)

    # Inner join: only subjects with both features and labels
    combined = labels.join(features[available_features], how="inner")

    # Ensure label column is present and named correctly
    if "label" in combined.columns:
        combined = combined.rename(columns={"label": TARGET_COLUMN})
    elif TARGET_COLUMN not in combined.columns:
        logger.warning("No label column found in combined data.")
        return pd.DataFrame(), stats

    # Drop rows with NaN in features or label
    required_cols = available_features + [TARGET_COLUMN]
    combined = combined.dropna(subset=required_cols)

    # Ensure label is binary
    combined = combined[combined[TARGET_COLUMN].isin([0, 1])]

    combined = combined.reset_index()

    logger.info(
        "Assembled %d training samples with %d features. "
        "Positive rate: %.1f%%.",
        len(combined),
        len(available_features),
        combined[TARGET_COLUMN].mean() * 100 if len(combined) > 0 else 0.0,
    )

    return combined, stats


def retrain(
    vod_df: pd.DataFrame,
    feedback_df: pd.DataFrame,
    feature_df: pd.DataFrame,
    production_metrics: dict[str, float] | None = None,
    config: RetrainingConfig | None = None,
) -> RetrainingResult:
    """Execute the full automated retraining pipeline.

    Args:
        vod_df: VOD-labeled data.
        feedback_df: Raw loan feedback data.
        feature_df: Feature data.
        production_metrics: Current production model metrics for comparison.
        config: Retraining configuration.

    Returns:
        RetrainingResult with outcome and details.
    """
    if config is None:
        config = RetrainingConfig()

    logger.info("Starting automated retraining pipeline.")

    # 1. Assemble training data
    try:
        training_data, gt_stats = assemble_training_data(
            vod_df, feedback_df, feature_df, config
        )
    except Exception as e:
        logger.error("Failed to assemble training data: %s", e)
        return RetrainingResult(
            outcome=RetrainingOutcome.ERROR,
            message=f"Data assembly failed: {e}",
        )

    # 2. Check data sufficiency
    if len(training_data) < config.min_total_samples:
        msg = (
            f"Insufficient training data: {len(training_data)} samples "
            f"(minimum {config.min_total_samples})."
        )
        logger.warning(msg)
        return RetrainingResult(
            outcome=RetrainingOutcome.INSUFFICIENT_DATA,
            ground_truth_stats=gt_stats,
            message=msg,
        )

    # Check both classes
    label_counts = training_data[TARGET_COLUMN].value_counts()
    if len(label_counts) < 2:
        msg = "Training data contains only one class."
        logger.warning(msg)
        return RetrainingResult(
            outcome=RetrainingOutcome.VALIDATION_FAILED,
            ground_truth_stats=gt_stats,
            message=msg,
        )

    # 3. Train candidate model
    try:
        training_result = train_model(
            training_data,
            config=config.training_config,
            save_model=True,
        )
    except Exception as e:
        logger.error("Training failed: %s", e)
        return RetrainingResult(
            outcome=RetrainingOutcome.ERROR,
            ground_truth_stats=gt_stats,
            message=f"Training failed: {e}",
        )

    candidate_metrics = training_result.metrics

    # 4. Evaluate against performance gates
    from ml.training.evaluation import PERFORMANCE_TARGETS, check_performance_targets

    gate_results = check_performance_targets(candidate_metrics)
    all_gates_passed = all(r["passed"] for r in gate_results.values())

    if not all_gates_passed:
        failed_gates = [k for k, v in gate_results.items() if not v["passed"]]
        msg = f"Performance gates failed: {failed_gates}"
        logger.warning(msg)
        return RetrainingResult(
            outcome=RetrainingOutcome.GATE_FAILED,
            training_result=training_result,
            candidate_metrics=candidate_metrics,
            production_metrics=production_metrics or {},
            ground_truth_stats=gt_stats,
            message=msg,
        )

    # 5. Compare with production model
    if production_metrics:
        prod_auc = production_metrics.get("auc_roc", 0.0)
        cand_auc = candidate_metrics.get("auc_roc", 0.0)
        improvement = cand_auc - prod_auc

        if improvement < config.min_improvement_auc:
            msg = (
                f"Candidate AUC-ROC ({cand_auc:.4f}) does not improve over "
                f"production ({prod_auc:.4f}) by the minimum threshold "
                f"({config.min_improvement_auc})."
            )
            logger.info(msg)
            return RetrainingResult(
                outcome=RetrainingOutcome.NO_IMPROVEMENT,
                training_result=training_result,
                candidate_metrics=candidate_metrics,
                production_metrics=production_metrics,
                ground_truth_stats=gt_stats,
                message=msg,
            )

    # 6. Register in MLflow if configured
    mlflow_run_id: str | None = None
    if config.register_in_mlflow:
        try:
            from ml.training.experiment import ExperimentConfig, log_training_run

            mlflow_run_id = log_training_run(
                model=training_result.model,
                metrics=candidate_metrics,
                hyperparameters=training_result.hyperparameters,
                feature_columns=training_result.feature_columns,
                config=ExperimentConfig(
                    tags={"trigger": "active_learning_retrain"},
                ),
                train_size=training_result.train_size,
                val_size=training_result.val_size,
                test_size=training_result.test_size,
            )
            logger.info("Candidate model registered in MLflow: %s", mlflow_run_id)
        except Exception as e:
            logger.warning("MLflow registration failed (non-fatal): %s", e)

    msg = (
        f"Retraining successful. AUC-ROC: {candidate_metrics.get('auc_roc', 0):.4f}. "
        f"Trained on {len(training_data)} samples."
    )
    logger.info(msg)

    return RetrainingResult(
        outcome=RetrainingOutcome.SUCCESS,
        training_result=training_result,
        candidate_metrics=candidate_metrics,
        production_metrics=production_metrics or {},
        ground_truth_stats=gt_stats,
        message=msg,
        mlflow_run_id=mlflow_run_id,
    )
