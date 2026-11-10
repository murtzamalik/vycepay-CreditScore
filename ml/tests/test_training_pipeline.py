"""Tests for ml.training.pipeline — XGBoost training pipeline."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xgboost as xgb

from ml.training.pipeline import (
    BRD_HYPERPARAMETERS,
    CORE_FEATURES,
    TARGET_COLUMN,
    TrainingConfig,
    TrainingResult,
    split_data,
    train_model,
    validate_training_data,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def synthetic_training_data() -> pd.DataFrame:
    """Generate synthetic training data with the six core features."""
    np.random.seed(42)
    n = 500

    # Generate features
    data: dict[str, np.ndarray] = {}
    for feat in CORE_FEATURES:
        data[feat] = np.random.uniform(0, 1, n)

    # Generate labels with ~20% positive rate
    probabilities = (
        0.3 * data["cblri"]
        + 0.2 * data["utdi"]
        + 0.15 * data["scfv"]
        + 0.15 * data["ddc_ratio"]
        + 0.1 * data["niq_score"]
        + 0.1 * data["gos_index"]
    )
    noise = np.random.normal(0, 0.1, n)
    labels = (probabilities + noise > 0.6).astype(int)

    data[TARGET_COLUMN] = labels
    df = pd.DataFrame(data)
    return df


@pytest.fixture()
def training_config(tmp_path: Path) -> TrainingConfig:
    """Training config pointing to a temp directory."""
    return TrainingConfig(
        model_output_dir=str(tmp_path / "models"),
        hyperparameters={
            **BRD_HYPERPARAMETERS,
            "n_estimators": 10,  # Speed up tests
        },
    )


# ---------------------------------------------------------------------------
# Test TrainingConfig
# ---------------------------------------------------------------------------

class TestTrainingConfig:
    def test_default_config(self) -> None:
        config = TrainingConfig()
        assert config.train_ratio == 0.60
        assert config.val_ratio == 0.20
        assert config.test_ratio == 0.20
        assert config.random_seed == 42
        assert config.target_column == TARGET_COLUMN
        assert len(config.feature_columns) == 6

    def test_invalid_split_ratios(self) -> None:
        with pytest.raises(ValueError, match="sum to 1.0"):
            TrainingConfig(train_ratio=0.5, val_ratio=0.5, test_ratio=0.5)

    def test_custom_config(self, tmp_path: Path) -> None:
        config = TrainingConfig(
            train_ratio=0.7,
            val_ratio=0.15,
            test_ratio=0.15,
            random_seed=123,
            model_output_dir=str(tmp_path),
        )
        assert config.train_ratio == 0.7
        assert config.random_seed == 123


# ---------------------------------------------------------------------------
# Test validate_training_data
# ---------------------------------------------------------------------------

class TestValidateTrainingData:
    def test_valid_data(
        self, synthetic_training_data: pd.DataFrame
    ) -> None:
        config = TrainingConfig()
        errors = validate_training_data(synthetic_training_data, config)
        assert errors == []

    def test_missing_columns(self) -> None:
        df = pd.DataFrame({"x": [1, 2, 3]})
        config = TrainingConfig()
        errors = validate_training_data(df, config)
        assert any("Missing columns" in e for e in errors)

    def test_insufficient_data(self) -> None:
        df = pd.DataFrame({
            **{feat: [0.5, 0.6] for feat in CORE_FEATURES},
            TARGET_COLUMN: [0, 1],
        })
        config = TrainingConfig()
        errors = validate_training_data(df, config)
        assert any("Insufficient data" in e for e in errors)

    def test_single_class(self) -> None:
        n = 20
        df = pd.DataFrame({
            **{feat: np.random.uniform(0, 1, n) for feat in CORE_FEATURES},
            TARGET_COLUMN: np.zeros(n, dtype=int),
        })
        config = TrainingConfig()
        errors = validate_training_data(df, config)
        assert any("both positive" in e for e in errors)

    def test_nan_features(self) -> None:
        n = 20
        data = {feat: np.random.uniform(0, 1, n) for feat in CORE_FEATURES}
        data["cblri"][0] = np.nan
        data[TARGET_COLUMN] = np.concatenate([np.ones(5), np.zeros(n - 5)]).astype(int)
        df = pd.DataFrame(data)
        config = TrainingConfig()
        errors = validate_training_data(df, config)
        assert any("NaN" in e for e in errors)


# ---------------------------------------------------------------------------
# Test split_data
# ---------------------------------------------------------------------------

class TestSplitData:
    def test_split_ratios(
        self, synthetic_training_data: pd.DataFrame
    ) -> None:
        config = TrainingConfig()
        train_df, val_df, test_df = split_data(
            synthetic_training_data, config
        )
        total = len(synthetic_training_data)
        assert len(train_df) + len(val_df) + len(test_df) == total
        # Approximate ratios (won't be exact due to rounding)
        assert abs(len(train_df) / total - 0.60) < 0.05
        assert abs(len(val_df) / total - 0.20) < 0.05
        assert abs(len(test_df) / total - 0.20) < 0.05

    def test_stratified_split(
        self, synthetic_training_data: pd.DataFrame
    ) -> None:
        config = TrainingConfig()
        train_df, val_df, test_df = split_data(
            synthetic_training_data, config
        )
        # All splits should have both classes
        for split_df in [train_df, val_df, test_df]:
            assert set(split_df[TARGET_COLUMN].unique()) == {0, 1}


# ---------------------------------------------------------------------------
# Test train_model
# ---------------------------------------------------------------------------

class TestTrainModel:
    def test_train_model_success(
        self,
        synthetic_training_data: pd.DataFrame,
        training_config: TrainingConfig,
    ) -> None:
        result = train_model(
            synthetic_training_data,
            training_config,
            save_model=False,
        )
        assert isinstance(result, TrainingResult)
        assert isinstance(result.model, xgb.XGBClassifier)
        assert "auc_roc" in result.metrics
        assert "calibration_error" in result.metrics
        assert "ks_statistic" in result.metrics
        assert result.train_size > 0
        assert result.val_size > 0
        assert result.test_size > 0
        assert 0.0 <= result.positive_rate <= 1.0

    def test_train_model_saves_artifact(
        self,
        synthetic_training_data: pd.DataFrame,
        training_config: TrainingConfig,
    ) -> None:
        result = train_model(
            synthetic_training_data,
            training_config,
            save_model=True,
        )
        assert result.model_path is not None
        assert Path(result.model_path).exists()

        # Check metadata file
        model_dir = Path(training_config.model_output_dir)
        meta_files = list(model_dir.glob("metadata_*.json"))
        assert len(meta_files) == 1
        with open(meta_files[0]) as f:
            metadata = json.load(f)
        assert "feature_columns" in metadata
        assert "metrics" in metadata

    def test_train_model_invalid_data(
        self, training_config: TrainingConfig
    ) -> None:
        df = pd.DataFrame({"x": [1, 2, 3]})
        with pytest.raises(ValueError, match="validation failed"):
            train_model(df, training_config)

    def test_default_config(
        self, synthetic_training_data: pd.DataFrame, tmp_path: Path
    ) -> None:
        config = TrainingConfig(
            model_output_dir=str(tmp_path / "models"),
            hyperparameters={
                **BRD_HYPERPARAMETERS,
                "n_estimators": 10,
            },
        )
        result = train_model(synthetic_training_data, config, save_model=False)
        assert result.feature_columns == list(CORE_FEATURES)

    def test_model_predictions(
        self,
        synthetic_training_data: pd.DataFrame,
        training_config: TrainingConfig,
    ) -> None:
        result = train_model(
            synthetic_training_data, training_config, save_model=False
        )
        # Model should produce predictions
        X = synthetic_training_data[list(CORE_FEATURES)].head(5)
        probs = result.model.predict_proba(X)[:, 1]
        assert len(probs) == 5
        assert all(0.0 <= p <= 1.0 for p in probs)

    def test_brd_hyperparameters_used(
        self,
        synthetic_training_data: pd.DataFrame,
        training_config: TrainingConfig,
    ) -> None:
        result = train_model(
            synthetic_training_data, training_config, save_model=False
        )
        assert result.hyperparameters["max_depth"] == 6
        assert result.hyperparameters["learning_rate"] == 0.05
        assert result.hyperparameters["subsample"] == 0.8
        assert result.hyperparameters["gamma"] == 0.1
        assert result.hyperparameters["scale_pos_weight"] == 3
