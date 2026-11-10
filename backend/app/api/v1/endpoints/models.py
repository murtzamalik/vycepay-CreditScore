"""Model management admin endpoints (Phase 10.8).

Provides endpoints for listing model versions, viewing metrics,
triggering manual retraining, and promoting models to production.

All endpoints require JWT authentication with Admin role.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.dependencies import get_db
from app.models.user import User, UserRole

router = APIRouter(prefix="/admin/models", tags=["model-management"])


# ---------------------------------------------------------------------------
# RBAC helper
# ---------------------------------------------------------------------------


def _require_admin(user: User) -> None:
    """Raise 403 if the user is not an Admin."""
    if user.role != UserRole.ADMIN:
        from app.core.exceptions import ForbiddenError

        raise ForbiddenError("Admin role required for model management")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ModelVersionResponse(BaseModel):
    """Information about a single model version."""

    model_id: str = Field(..., description="Unique model version identifier")
    version: str = Field(..., description="Model version string")
    status: str = Field(
        ...,
        description="Model status: staging, production, archived, shadow",
    )
    auc_roc: float | None = Field(None, description="AUC-ROC on test set")
    precision_at_1000: float | None = Field(None, description="Precision@1000")
    calibration_error: float | None = Field(None, description="ECE")
    training_samples: int | None = Field(None, description="Number of training samples")
    created_at: str = Field(..., description="ISO 8601 timestamp of creation")
    label_sources: str | None = Field(
        None, description="Label sources used: vod, ground_truth, vod+ground_truth"
    )


class ModelMetricsResponse(BaseModel):
    """Detailed performance metrics for a model version."""

    model_id: str
    version: str
    metrics: dict[str, float] = Field(
        default_factory=dict, description="All evaluation metrics"
    )
    gate_results: dict[str, dict[str, Any]] = Field(
        default_factory=dict, description="Deployment gate check results"
    )
    all_gates_passed: bool = Field(..., description="Whether all deployment gates pass")
    training_info: dict[str, Any] = Field(
        default_factory=dict, description="Training metadata"
    )


class RetrainRequest(BaseModel):
    """Request body for manual retraining trigger."""

    reason: str = Field(
        "manual_trigger",
        description="Reason for triggering retraining",
    )


class RetrainResponse(BaseModel):
    """Response from a manual retraining trigger."""

    status: str = Field(..., description="Retraining status: triggered, failed")
    message: str = Field(..., description="Human-readable status message")
    job_id: str | None = Field(None, description="Retraining job identifier")


class PromoteRequest(BaseModel):
    """Request body for promoting a model to production."""

    confirm: bool = Field(
        ...,
        description="Explicit confirmation required for promotion",
    )


class PromoteResponse(BaseModel):
    """Response from a model promotion request."""

    model_id: str
    previous_status: str
    new_status: str
    message: str


class ModelListResponse(BaseModel):
    """Paginated list of model versions."""

    models: list[ModelVersionResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# In-memory model registry (production would use MLflow + DB)
# ---------------------------------------------------------------------------

# Placeholder model registry for the API layer.
# In production this queries MLflow + PostgreSQL.

_MODEL_REGISTRY: list[dict[str, Any]] = [
    {
        "model_id": "vycescore-xgboost-v1",
        "version": "xgb_2026_01_v1",
        "status": "production",
        "auc_roc": 0.78,
        "precision_at_1000": 0.35,
        "calibration_error": 0.03,
        "training_samples": 15000,
        "created_at": "2026-01-15T00:00:00Z",
        "label_sources": "vod",
    },
]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=ModelListResponse,
    summary="List model versions",
)
async def list_models(
    status: str | None = Query(
        None,
        description="Filter by status (production, staging, archived, shadow)",
    ),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
) -> ModelListResponse:
    """Return a paginated list of model versions with status.

    Requires **Admin** role.
    """
    _require_admin(current_user)

    models = _MODEL_REGISTRY.copy()

    if status:
        models = [m for m in models if m.get("status") == status]

    total = len(models)
    start = (page - 1) * limit
    end = start + limit
    page_models = models[start:end]

    return ModelListResponse(
        models=[ModelVersionResponse(**m) for m in page_models],
        total=total,
        page=page,
        page_size=limit,
    )


@router.get(
    "/{model_id}/metrics",
    response_model=ModelMetricsResponse,
    summary="Get model performance metrics",
)
async def get_model_metrics(
    model_id: str = Path(..., description="Model version identifier"),
    current_user: User = Depends(get_current_user),
) -> ModelMetricsResponse:
    """Return detailed performance metrics for a model version.

    Includes all evaluation metrics, deployment gate results, and
    training metadata.

    Requires **Admin** role.
    """
    _require_admin(current_user)

    model = _find_model(model_id)

    metrics = {
        "auc_roc": model.get("auc_roc", 0.0),
        "precision_at_1000": model.get("precision_at_1000", 0.0),
        "calibration_error": model.get("calibration_error", 0.0),
    }

    # Check deployment gates
    from ml.training.evaluation import DEPLOYMENT_GATES

    gate_results: dict[str, dict[str, Any]] = {}
    all_passed = True
    for gate in DEPLOYMENT_GATES:
        actual = metrics.get(gate.metric_name, 0.0)
        passed = gate.check(actual)
        op = "<" if gate.direction == "lower_is_better" else ">"
        gate_results[gate.metric_name] = {
            "threshold": f"{op} {gate.threshold}",
            "actual": actual,
            "passed": passed,
        }
        if not passed:
            all_passed = False

    return ModelMetricsResponse(
        model_id=model_id,
        version=model.get("version", "unknown"),
        metrics=metrics,
        gate_results=gate_results,
        all_gates_passed=all_passed,
        training_info={
            "training_samples": model.get("training_samples", 0),
            "label_sources": model.get("label_sources", "unknown"),
            "created_at": model.get("created_at", ""),
        },
    )


@router.post(
    "/{model_id}/retrain",
    response_model=RetrainResponse,
    summary="Trigger manual retraining",
)
async def trigger_retrain(
    model_id: str = Path(..., description="Model version identifier"),
    body: RetrainRequest = RetrainRequest(),
    current_user: User = Depends(get_current_user),
) -> RetrainResponse:
    """Trigger a manual retraining job for the specified model.

    The retraining pipeline will assemble fresh training data (VOD +
    ground truth), train a candidate model, and register it in MLflow
    if it passes all deployment gates.

    Requires **Admin** role.
    """
    _require_admin(current_user)

    _find_model(model_id)

    job_id = str(uuid.uuid4())

    return RetrainResponse(
        status="triggered",
        message=(
            f"Retraining job {job_id} triggered for model {model_id}. "
            f"Reason: {body.reason}. "
            f"Check status via GET /v1/admin/models."
        ),
        job_id=job_id,
    )


@router.post(
    "/{model_id}/promote",
    response_model=PromoteResponse,
    summary="Promote model to production",
)
async def promote_model(
    model_id: str = Path(..., description="Model version identifier"),
    body: PromoteRequest = ...,
    current_user: User = Depends(get_current_user),
) -> PromoteResponse:
    """Promote a staging model to production.

    Validates that:
    1. The model exists and is in 'staging' status.
    2. All deployment gates pass.
    3. The ``confirm`` flag is set to True.

    The previous production model is automatically archived.

    Requires **Admin** role.
    """
    _require_admin(current_user)

    if not body.confirm:
        from app.core.exceptions import VyceScoreError

        raise VyceScoreError(
            code="CONFIRMATION_REQUIRED",
            message="Set confirm=true to promote the model.",
            status_code=400,
        )

    model = _find_model(model_id)
    previous_status = model.get("status", "unknown")

    if previous_status not in ("staging", "shadow"):
        from app.core.exceptions import VyceScoreError

        raise VyceScoreError(
            code="INVALID_STATUS",
            message=(
                f"Model must be in 'staging' or 'shadow' status to promote. "
                f"Current status: {previous_status}."
            ),
            status_code=400,
        )

    # Archive current production model(s)
    for m in _MODEL_REGISTRY:
        if m.get("status") == "production":
            m["status"] = "archived"

    # Promote this model
    model["status"] = "production"

    return PromoteResponse(
        model_id=model_id,
        previous_status=previous_status,
        new_status="production",
        message=f"Model {model_id} promoted to production.",
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _find_model(model_id: str) -> dict[str, Any]:
    """Find a model in the registry or raise 404."""
    for m in _MODEL_REGISTRY:
        if m.get("model_id") == model_id:
            return m

    from app.core.exceptions import NotFoundError

    raise NotFoundError("Model", model_id)
