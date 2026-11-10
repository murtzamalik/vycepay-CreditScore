"""Tests for ml.serving.model_server — model serving layer."""

from __future__ import annotations

import threading
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xgboost as xgb

from ml.scoring.converter import SCORE_MAX, SCORE_MIN
from ml.serving.model_server import (
    BatchPredictionResult,
    ModelServer,
    PredictionResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FEATURES = ["cblri", "utdi", "scfv", "ddc_ratio", "niq_score", "gos_index"]


@pytest.fixture()
def trained_model() -> xgb.XGBClassifier:
    """Train a small XGBoost model on synthetic data."""
    np.random.seed(42)
    n = 200
    X = pd.DataFrame({feat: np.random.uniform(0, 1, n) for feat in FEATURES})
    y = (
        0.3 * X["cblri"]
        + 0.25 * X["utdi"]
        + 0.15 * X["scfv"]
        + 0.15 * X["ddc_ratio"]
        + 0.1 * X["niq_score"]
        + 0.05 * X["gos_index"]
        + np.random.normal(0, 0.1, n)
    )
    y_binary = (y > y.median()).astype(int)

    model = xgb.XGBClassifier(
        n_estimators=20,
        max_depth=3,
        random_state=42,
        use_label_encoder=False,
        eval_metric="logloss",
    )
    model.fit(X, y_binary)
    return model


@pytest.fixture()
def model_server(trained_model: xgb.XGBClassifier) -> ModelServer:
    """Create a model server with a loaded model."""
    server = ModelServer(feature_columns=FEATURES)
    server.load_model_direct(trained_model, version="test-v1")
    return server


@pytest.fixture()
def single_features() -> pd.DataFrame:
    """Single-row feature DataFrame."""
    return pd.DataFrame({
        "cblri": [0.7],
        "utdi": [0.5],
        "scfv": [0.3],
        "ddc_ratio": [0.8],
        "niq_score": [0.6],
        "gos_index": [0.4],
    })


@pytest.fixture()
def batch_features() -> pd.DataFrame:
    """Multi-row feature DataFrame."""
    np.random.seed(42)
    n = 10
    return pd.DataFrame({feat: np.random.uniform(0, 1, n) for feat in FEATURES})


@pytest.fixture()
def saved_model_path(
    trained_model: xgb.XGBClassifier, tmp_path: Path
) -> str:
    """Save model to a temp file and return the path."""
    path = tmp_path / "test_model.json"
    trained_model.save_model(str(path))
    return str(path)


# ---------------------------------------------------------------------------
# Test ModelServer initialization
# ---------------------------------------------------------------------------

class TestModelServerInit:
    def test_unloaded_server(self) -> None:
        server = ModelServer()
        assert server.is_loaded is False
        assert server.model_version is None

    def test_default_features(self) -> None:
        server = ModelServer()
        assert server.feature_columns == FEATURES

    def test_custom_features(self) -> None:
        custom = ["feat_a", "feat_b"]
        server = ModelServer(feature_columns=custom)
        assert server.feature_columns == custom


# ---------------------------------------------------------------------------
# Test model loading
# ---------------------------------------------------------------------------

class TestModelLoading:
    def test_load_direct(
        self, trained_model: xgb.XGBClassifier
    ) -> None:
        server = ModelServer()
        server.load_model_direct(trained_model, version="v1")
        assert server.is_loaded is True
        assert server.model_version == "v1"

    def test_load_from_file(self, saved_model_path: str) -> None:
        server = ModelServer()
        server.load_model_from_file(saved_model_path, version="v2")
        assert server.is_loaded is True
        assert server.model_version == "v2"

    def test_load_from_missing_file(self) -> None:
        server = ModelServer()
        with pytest.raises(FileNotFoundError):
            server.load_model_from_file("/nonexistent/model.json")

    def test_hot_swap(
        self, trained_model: xgb.XGBClassifier
    ) -> None:
        server = ModelServer()
        server.load_model_direct(trained_model, version="v1")
        assert server.model_version == "v1"

        # Hot-swap to "v2" (same model, different version for testing)
        server.load_model_direct(trained_model, version="v2")
        assert server.model_version == "v2"
        assert server.is_loaded is True


# ---------------------------------------------------------------------------
# Test single prediction
# ---------------------------------------------------------------------------

class TestPredict:
    def test_basic_prediction(
        self,
        model_server: ModelServer,
        single_features: pd.DataFrame,
    ) -> None:
        result = model_server.predict(single_features)
        assert isinstance(result, PredictionResult)
        assert SCORE_MIN <= result.score_result.score <= SCORE_MAX
        assert 0.0 <= result.score_result.probability <= 1.0
        assert result.latency_ms >= 0
        assert result.model_version == "test-v1"

    def test_prediction_without_explanation(
        self,
        model_server: ModelServer,
        single_features: pd.DataFrame,
    ) -> None:
        result = model_server.predict(single_features, explain=False)
        assert result.explanation is None

    def test_prediction_with_explanation(
        self,
        model_server: ModelServer,
        single_features: pd.DataFrame,
    ) -> None:
        result = model_server.predict(single_features, explain=True)
        assert result.explanation is not None
        assert len(result.explanation.risk_drivers) == 3

    def test_custom_top_n_drivers(
        self,
        model_server: ModelServer,
        single_features: pd.DataFrame,
    ) -> None:
        result = model_server.predict(
            single_features, explain=True, top_n_drivers=2
        )
        assert len(result.explanation.risk_drivers) == 2

    def test_prediction_with_confidence(
        self,
        model_server: ModelServer,
        single_features: pd.DataFrame,
    ) -> None:
        result = model_server.predict(
            single_features, include_confidence=True
        )
        assert result.score_result.confidence_interval is not None

    def test_no_model_raises(
        self, single_features: pd.DataFrame
    ) -> None:
        server = ModelServer()
        with pytest.raises(RuntimeError, match="No model loaded"):
            server.predict(single_features)

    def test_empty_features_raises(
        self, model_server: ModelServer
    ) -> None:
        empty = pd.DataFrame(columns=FEATURES)
        with pytest.raises(ValueError, match="Empty"):
            model_server.predict(empty)

    def test_multi_row_raises(
        self,
        model_server: ModelServer,
        batch_features: pd.DataFrame,
    ) -> None:
        with pytest.raises(ValueError, match="single row"):
            model_server.predict(batch_features)

    def test_to_dict(
        self,
        model_server: ModelServer,
        single_features: pd.DataFrame,
    ) -> None:
        result = model_server.predict(single_features, explain=True)
        d = result.to_dict()
        assert "score" in d
        assert "probability" in d
        assert "risk_category" in d
        assert "risk_drivers" in d
        assert "latency_ms" in d


# ---------------------------------------------------------------------------
# Test batch prediction
# ---------------------------------------------------------------------------

class TestPredictBatch:
    def test_batch_prediction(
        self,
        model_server: ModelServer,
        batch_features: pd.DataFrame,
    ) -> None:
        result = model_server.predict_batch(batch_features)
        assert isinstance(result, BatchPredictionResult)
        assert len(result.results) == len(batch_features)
        assert result.latency_ms >= 0

    def test_batch_scores_in_range(
        self,
        model_server: ModelServer,
        batch_features: pd.DataFrame,
    ) -> None:
        result = model_server.predict_batch(batch_features)
        for score_result in result.results:
            assert SCORE_MIN <= score_result.score <= SCORE_MAX
            assert 0.0 <= score_result.probability <= 1.0

    def test_empty_batch_raises(
        self, model_server: ModelServer
    ) -> None:
        empty = pd.DataFrame(columns=FEATURES)
        with pytest.raises(ValueError, match="Empty"):
            model_server.predict_batch(empty)

    def test_no_model_raises(
        self, batch_features: pd.DataFrame
    ) -> None:
        server = ModelServer()
        with pytest.raises(RuntimeError, match="No model loaded"):
            server.predict_batch(batch_features)


# ---------------------------------------------------------------------------
# Test thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_predictions(
        self,
        model_server: ModelServer,
    ) -> None:
        """Verify concurrent predictions don't cause errors."""
        results: list[PredictionResult] = []
        errors: list[Exception] = []

        def predict_task(idx: int) -> None:
            try:
                features = pd.DataFrame({
                    feat: [np.random.uniform(0, 1)] for feat in FEATURES
                })
                result = model_server.predict(features)
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=predict_task, args=(i,))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors during concurrent predictions: {errors}"
        assert len(results) == 10


# ---------------------------------------------------------------------------
# Test health check
# ---------------------------------------------------------------------------

class TestHealthCheck:
    def test_health_check_loaded(
        self, model_server: ModelServer
    ) -> None:
        health = model_server.health_check()
        assert health["status"] == "healthy"
        assert health["model_loaded"] is True
        assert health["model_version"] == "test-v1"

    def test_health_check_unloaded(self) -> None:
        server = ModelServer()
        health = server.health_check()
        assert health["status"] == "no_model_loaded"
        assert health["model_loaded"] is False
