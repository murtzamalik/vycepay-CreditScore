"""Score endpoints: Lite, Pro, Batch, and Custom (BRD §9.2.1, §9.3.1).

All endpoints enforce API key authentication, license tier validation,
and rate limiting. Raw national IDs are never logged or stored.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, RateLimitedError
from app.core.rate_limiter import RateLimiter
from app.core.security import get_current_customer
from app.dependencies import get_db, get_redis
from app.models.customer import Customer, LicenseTier
from app.schemas.scores import (
    ScoreBatchRequest,
    ScoreBatchResponse,
    ScoreLiteResponse,
    ScoreProResponse,
    ScoreProWithHistoryResponse,
)
from app.services.audit_service import AuditService
from app.services.id_hasher import hash_national_id
from app.services.scoring import ScoringService

router = APIRouter(prefix="/scores", tags=["scores"])


# ---------------------------------------------------------------------------
# License tier dependency
# ---------------------------------------------------------------------------


def require_tier(*allowed_tiers: str):
    """FastAPI dependency factory that validates customer license tier.

    Usage::

        @router.get("/pro/{national_id}")
        async def get_pro(customer=Depends(require_tier("PRO", "DEEP_DIVE"))):
            ...
    """

    async def checker(
        customer: Customer = Depends(get_current_customer),
    ) -> Customer:
        if customer.license_tier.value not in allowed_tiers:
            raise ForbiddenError(
                "License tier insufficient for this endpoint. "
                f"Required: {', '.join(allowed_tiers)}; "
                f"current: {customer.license_tier.value}"
            )
        return customer

    return checker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_scoring_service() -> ScoringService:
    """Provide a ScoringService instance for dependency injection."""
    return ScoringService()


async def _enforce_rate_limit(redis: Redis, customer: Customer) -> None:
    """Check rate limit and raise 429 if exceeded."""
    limiter = RateLimiter(redis)
    result = await limiter.check_rate_limit(
        str(customer.customer_id),
        customer.license_tier,
    )
    if not result.allowed:
        raise RateLimitedError()


# ---------------------------------------------------------------------------
# Lite endpoint — BRD §9.2.1, UC-SCORE-001
# ---------------------------------------------------------------------------


@router.get("/lite/{national_id}", response_model=ScoreLiteResponse)
async def get_lite_score(
    national_id: str,
    request: Request,
    customer: Customer = Depends(
        require_tier(LicenseTier.LITE.value, LicenseTier.PRO.value, LicenseTier.DEEP_DIVE.value)
    ),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    scoring: ScoringService = Depends(_get_scoring_service),
) -> ScoreLiteResponse:
    """VyceScore Lite -- rapid pre-screening returning VyceScore + NIQ Score.

    Available to: Lite, Pro, Deep Dive tiers.
    Rate limit: 1000/hr (tier-dependent).
    Target latency: <500ms.
    """
    start = time.monotonic()

    # 1. Rate limit
    await _enforce_rate_limit(redis, customer)

    # 2. Score retrieval
    response = await scoring.get_lite_score(db, redis, national_id)

    # 3. Audit trail (non-blocking best-effort)
    elapsed_ms = int((time.monotonic() - start) * 1000)
    id_hash = hash_national_id(national_id)
    try:
        await AuditService.log_api_request(
            db=db,
            customer_id=str(customer.customer_id),
            endpoint=f"GET /v1/scores/lite/{id_hash[:12]}...",
            subject_id=None,
            response_status=200,
            response_time_ms=elapsed_ms,
            ip_address=request.client.host if request.client else None,
        )
    except Exception:
        pass  # Audit failure must not break the score response

    return response


# ---------------------------------------------------------------------------
# Pro endpoint — BRD §9.3.1, UC-SCORE-002
# ---------------------------------------------------------------------------


@router.get("/pro/{national_id}", response_model=ScoreProWithHistoryResponse)
async def get_pro_score(
    national_id: str,
    request: Request,
    include_history: bool = Query(
        False,
        alias="includeHistory",
        description="Include score history for the last 12 months",
    ),
    customer: Customer = Depends(
        require_tier(LicenseTier.PRO.value, LicenseTier.DEEP_DIVE.value)
    ),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    scoring: ScoringService = Depends(_get_scoring_service),
) -> ScoreProResponse | ScoreProWithHistoryResponse:
    """VyceScore Pro -- full underwriting with SHAP-explained risk drivers.

    Available to: Pro, Deep Dive tiers only (403 for Lite).
    Rate limit: 500/hr (tier-dependent).
    Target latency: <2s.
    """
    start = time.monotonic()

    # 1. Rate limit
    await _enforce_rate_limit(redis, customer)

    # 2. Score retrieval
    response = await scoring.get_pro_score(
        db, redis, national_id, include_history=include_history,
    )

    # 3. Audit trail
    elapsed_ms = int((time.monotonic() - start) * 1000)
    id_hash = hash_national_id(national_id)
    try:
        await AuditService.log_api_request(
            db=db,
            customer_id=str(customer.customer_id),
            endpoint=f"GET /v1/scores/pro/{id_hash[:12]}...",
            subject_id=None,
            response_status=200,
            response_time_ms=elapsed_ms,
            ip_address=request.client.host if request.client else None,
        )
    except Exception:
        pass

    return response


# ---------------------------------------------------------------------------
# Batch endpoint
# ---------------------------------------------------------------------------


@router.post("/batch", response_model=ScoreBatchResponse)
async def batch_score(
    body: ScoreBatchRequest,
    request: Request,
    customer: Customer = Depends(
        require_tier(LicenseTier.LITE.value, LicenseTier.PRO.value, LicenseTier.DEEP_DIVE.value)
    ),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    scoring: ScoringService = Depends(_get_scoring_service),
) -> ScoreBatchResponse:
    """Score a batch of national IDs (max 100)."""
    await _enforce_rate_limit(redis, customer)

    results: list[ScoreLiteResponse] = []
    failed = 0
    for nid in body.national_ids:
        try:
            result = await scoring.get_lite_score(db, redis, nid)
            results.append(result)
        except Exception:
            failed += 1

    return ScoreBatchResponse(
        results=results,
        total=len(results),
        failed=failed,
    )


# ---------------------------------------------------------------------------
# Custom scoring endpoint — Deep Dive API (Phase 11)
# ---------------------------------------------------------------------------


class CustomScoreRequest(BaseModel):
    """Request body for custom model scoring (Deep Dive API).

    Attributes:
        national_id: Subject's national ID.
        industry_vertical: Industry vertical for model selection.
        prediction_horizon: Prediction window in days (30, 90, 365).
        feature_selection: Optional list of features to include.
            Defaults to all six core features.
    """

    national_id: str = Field(
        ...,
        min_length=5,
        max_length=20,
        description="Subject's national ID",
    )
    industry_vertical: str = Field(
        "general",
        description="Industry vertical: general, retail, manufacturing, services, agriculture",
    )
    prediction_horizon: int = Field(
        365,
        description="Prediction window in days (30, 90, or 365)",
    )
    feature_selection: list[str] | None = Field(
        None,
        description="Optional subset of features to use. Defaults to all core features.",
    )


class CustomScoreResponse(BaseModel):
    """Response from the custom scoring endpoint."""

    vyce_score: int = Field(..., ge=300, le=900, description="VyceScore credit score")
    niq_score: int = Field(..., ge=0, le=100, description="NIQ Score")
    risk_drivers: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Top risk drivers with SHAP explainability",
    )
    industry_vertical: str = Field(..., description="Industry vertical used")
    prediction_horizon: str = Field(..., description="Prediction horizon label")
    model_version: str = Field(..., description="Model version used")
    model_selection_reason: str = Field(
        ..., description="Why this model was selected"
    )
    confidence_interval: dict[str, int] = Field(
        default_factory=dict,
        description="Score confidence interval (lower, upper)",
    )
    score_date: str = Field(..., description="ISO 8601 date of scoring")
    data_quality: str = Field(
        ..., description="Data quality assessment: high, medium, low"
    )


# Deep Dive rate limit: 200/hr
DEEP_DIVE_RATE_LIMIT = 200


@router.post("/custom", response_model=CustomScoreResponse)
async def custom_score(
    body: CustomScoreRequest,
    request: Request,
    customer: Customer = Depends(
        require_tier(LicenseTier.DEEP_DIVE.value)
    ),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    scoring: ScoringService = Depends(_get_scoring_service),
) -> CustomScoreResponse:
    """Custom scoring endpoint for Deep Dive API (Phase 11).

    Accepts custom model configuration including industry vertical,
    prediction horizon, and feature selection.  Returns a custom score
    with SHAP explanation and model selection reasoning.

    Available to: **Deep Dive** tier only (403 for Lite/Pro).
    Rate limit: 200/hr.
    """
    start = time.monotonic()

    # 1. Rate limit (enforced at Deep Dive tier rate)
    await _enforce_rate_limit(redis, customer)

    # 2. Validate prediction horizon
    valid_horizons = (30, 90, 365)
    if body.prediction_horizon not in valid_horizons:
        from app.core.exceptions import VyceScoreError

        raise VyceScoreError(
            code="INVALID_HORIZON",
            message=(
                f"Prediction horizon must be one of {valid_horizons}. "
                f"Got: {body.prediction_horizon}"
            ),
            status_code=400,
        )

    # 3. Validate industry vertical
    valid_verticals = ("general", "retail", "manufacturing", "services", "agriculture")
    if body.industry_vertical.lower() not in valid_verticals:
        from app.core.exceptions import VyceScoreError

        raise VyceScoreError(
            code="INVALID_VERTICAL",
            message=(
                f"Industry vertical must be one of {valid_verticals}. "
                f"Got: {body.industry_vertical}"
            ),
            status_code=400,
        )

    # 4. Score retrieval — delegate to scoring service for custom scoring
    #    The scoring service will use model selector and industry weights
    response = await scoring.get_custom_score(
        db=db,
        redis=redis,
        national_id=body.national_id,
        industry_vertical=body.industry_vertical,
        prediction_horizon=body.prediction_horizon,
        feature_selection=body.feature_selection,
    )

    # 5. Audit trail
    elapsed_ms = int((time.monotonic() - start) * 1000)
    id_hash = hash_national_id(body.national_id)
    try:
        await AuditService.log_api_request(
            db=db,
            customer_id=str(customer.customer_id),
            endpoint=f"POST /v1/scores/custom/{id_hash[:12]}...",
            subject_id=None,
            response_status=200,
            response_time_ms=elapsed_ms,
            ip_address=request.client.host if request.client else None,
        )
    except Exception:
        pass

    return response
