"""Tests for model management admin endpoints (Phase 10.8)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.v1.endpoints.models import (
    ModelListResponse,
    ModelMetricsResponse,
    ModelVersionResponse,
    PromoteRequest,
    PromoteResponse,
    RetrainRequest,
    RetrainResponse,
    _MODEL_REGISTRY,
    _find_model,
)


class TestFindModel:
    """Tests for the _find_model helper."""

    def test_finds_existing_model(self) -> None:
        model = _find_model("vycescore-xgboost-v1")
        assert model["model_id"] == "vycescore-xgboost-v1"

    def test_raises_not_found_for_missing(self) -> None:
        from app.core.exceptions import NotFoundError

        with pytest.raises(NotFoundError):
            _find_model("nonexistent-model")


class TestModelSchemas:
    """Tests for model management Pydantic schemas."""

    def test_model_version_response(self) -> None:
        response = ModelVersionResponse(
            model_id="test-v1",
            version="xgb_2026_01_v1",
            status="staging",
            auc_roc=0.78,
            precision_at_1000=0.35,
            calibration_error=0.03,
            training_samples=15000,
            created_at="2026-01-15T00:00:00Z",
            label_sources="vod+ground_truth",
        )
        assert response.model_id == "test-v1"
        assert response.status == "staging"

    def test_retrain_request_defaults(self) -> None:
        req = RetrainRequest()
        assert req.reason == "manual_trigger"

    def test_retrain_response(self) -> None:
        resp = RetrainResponse(
            status="triggered",
            message="Retraining started",
            job_id="abc-123",
        )
        assert resp.status == "triggered"

    def test_promote_request_requires_confirm(self) -> None:
        req = PromoteRequest(confirm=True)
        assert req.confirm is True

    def test_model_metrics_response(self) -> None:
        resp = ModelMetricsResponse(
            model_id="test-v1",
            version="xgb_2026_01_v1",
            metrics={"auc_roc": 0.78},
            gate_results={},
            all_gates_passed=True,
            training_info={},
        )
        assert resp.all_gates_passed is True


class TestModelListResponse:
    """Tests for the list response schema."""

    def test_list_response(self) -> None:
        models = [
            ModelVersionResponse(
                model_id="v1",
                version="xgb_2026_01_v1",
                status="production",
                created_at="2026-01-01T00:00:00Z",
            ),
        ]
        resp = ModelListResponse(
            models=models,
            total=1,
            page=1,
            page_size=50,
        )
        assert resp.total == 1
        assert len(resp.models) == 1
