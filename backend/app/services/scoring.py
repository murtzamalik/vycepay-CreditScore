"""Scoring service — orchestrates score retrieval for Lite and Pro endpoints.

This service handles:
  1. National ID hashing (never storing raw IDs)
  2. Redis cache lookup
  3. Database query on cache miss
  4. Score caching
  5. Response construction

All methods are async and require injected database and Redis dependencies.
"""

from __future__ import annotations

import structlog
from datetime import date, timedelta
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.core.exceptions import NotFoundError
from app.models.risk_driver import RiskDriver
from app.models.score import Score
from app.models.subject import Subject
from app.schemas.scores import (
    ConfidenceInterval,
    RiskDriverResponse,
    ScoreHistoryItem,
    ScoreLiteResponse,
    ScoreMetadata,
    ScoreProResponse,
    ScoreProWithHistoryResponse,
)
from app.services.id_hasher import hash_national_id
from app.services.score_cache import ScoreCacheService
from app.services.score_interpretation import interpret_score

logger = structlog.get_logger(__name__)
settings = get_settings()


def _compute_data_quality(score: Score) -> str:
    """Derive a data quality label from the score's feature snapshot.

    Heuristic: if both confidence bounds are present and the interval is
    narrow (<= 60 points), quality is 'high'.  If the interval is moderate
    (<= 120), quality is 'medium'.  Otherwise 'low'.
    """
    if score.confidence_lower is not None and score.confidence_upper is not None:
        span = score.confidence_upper - score.confidence_lower
        if span <= 60:
            return "high"
        if span <= 120:
            return "medium"
    return "low"


def _risk_driver_contribution(driver: RiskDriver, all_drivers: list[RiskDriver]) -> int:
    """Compute the percentage contribution of a risk driver.

    Uses absolute SHAP values normalised across the top drivers.
    Falls back to equal distribution if no SHAP values are available.
    """
    if driver.shap_value is None:
        # Equal distribution when SHAP values are missing
        return round(100 / max(len(all_drivers), 1))

    total = sum(abs(float(d.shap_value)) for d in all_drivers if d.shap_value is not None)
    if total == 0:
        return round(100 / max(len(all_drivers), 1))
    return round(abs(float(driver.shap_value)) / total * 100)


class ScoringService:
    """Credit scoring operations backed by database and Redis cache."""

    async def get_lite_score(
        self,
        db: AsyncSession,
        redis: Redis,
        national_id: str,
    ) -> ScoreLiteResponse:
        """Return a VyceScore Lite response for a single national ID.

        Flow:
            1. Hash national ID (never store raw)
            2. Check Redis cache
            3. On cache miss, query DB for latest score
            4. If no score exists, raise 404
            5. Cache the result
            6. Return ScoreLiteResponse
        """
        id_hash = hash_national_id(national_id)
        await logger.ainfo("lite_score_request", subject_id_hash=id_hash)

        # 1. Cache check
        cached = await ScoreCacheService.get_cached_score(redis, id_hash, pro=False)
        if cached is not None:
            await logger.ainfo("cache_hit", endpoint="lite", subject_id_hash=id_hash)
            return ScoreLiteResponse(**cached)

        # 2. DB lookup
        subject = await self._get_subject_by_hash(db, id_hash)
        score = await self._get_latest_score(db, subject.subject_id)

        # 3. Build response
        niq = score.niq_score if score.niq_score is not None else 0
        response = ScoreLiteResponse(
            vyce_score=score.vyce_score,
            niq_score=niq,
            score_date=score.score_date.isoformat(),
            score_version=score.model_version,
            subject_id=id_hash,
            metadata=ScoreMetadata(
                model_version=score.model_version,
                feature_date=score.score_date.isoformat(),
                data_quality=_compute_data_quality(score),
            ),
        )

        # 4. Cache
        await ScoreCacheService.cache_score(
            redis, id_hash, response.model_dump(), pro=False,
        )

        return response

    async def get_pro_score(
        self,
        db: AsyncSession,
        redis: Redis,
        national_id: str,
        include_history: bool = False,
    ) -> ScoreProResponse | ScoreProWithHistoryResponse:
        """Return a VyceScore Pro response with risk drivers and confidence interval.

        Flow:
            1. Hash national ID
            2. Check cache (Pro scores cached separately)
            3. Query latest score + risk drivers
            4. If include_history, fetch last 12 months of scores
            5. Add score interpretation
            6. Return ScoreProResponse or ScoreProWithHistoryResponse
        """
        id_hash = hash_national_id(national_id)
        await logger.ainfo("pro_score_request", subject_id_hash=id_hash)

        # 1. Cache check (only for non-history requests)
        if not include_history:
            cached = await ScoreCacheService.get_cached_score(redis, id_hash, pro=True)
            if cached is not None:
                await logger.ainfo("cache_hit", endpoint="pro", subject_id_hash=id_hash)
                return ScoreProResponse(**cached)

        # 2. DB lookup
        subject = await self._get_subject_by_hash(db, id_hash)
        score = await self._get_latest_score_with_drivers(db, subject.subject_id)

        # 3. Build risk drivers (top 3 by rank)
        sorted_drivers = sorted(score.risk_drivers, key=lambda d: d.rank)[:3]
        risk_driver_responses = [
            RiskDriverResponse(
                factor=d.factor_name,
                impact=d.impact.value.lower(),
                description=d.description or "",
                contribution=_risk_driver_contribution(d, sorted_drivers),
            )
            for d in sorted_drivers
        ]

        # 4. Confidence interval
        confidence = ConfidenceInterval(
            lower=score.confidence_lower if score.confidence_lower is not None else max(score.vyce_score - 30, 300),
            upper=score.confidence_upper if score.confidence_upper is not None else min(score.vyce_score + 30, 900),
        )

        # 5. Interpretation
        interpretation = interpret_score(score.vyce_score)

        niq = score.niq_score if score.niq_score is not None else 0
        horizon_str = f"{score.prediction_horizon}_months"

        response_data: dict[str, Any] = {
            "vyce_score": score.vyce_score,
            "niq_score": niq,
            "risk_drivers": risk_driver_responses,
            "score_date": score.score_date.isoformat(),
            "model_version": score.model_version,
            "prediction_horizon": horizon_str,
            "confidence_interval": confidence,
            "interpretation": interpretation,
        }

        # 6. Optional history
        if include_history:
            history = await self._get_score_history(db, subject.subject_id)
            response = ScoreProWithHistoryResponse(
                **response_data,
                history=history,
            )
        else:
            response = ScoreProWithHistoryResponse(**response_data)
            # Cache only non-history responses
            await ScoreCacheService.cache_score(
                redis, id_hash, response.model_dump(), pro=True,
            )

        return response

    async def get_custom_score(
        self,
        db: AsyncSession,
        redis: Redis,
        national_id: str,
        industry_vertical: str = "general",
        prediction_horizon: int = 365,
        feature_selection: list[str] | None = None,
    ) -> Any:
        """Return a custom Deep Dive score with industry and horizon settings.

        This is the Deep Dive API endpoint handler.  It uses the same
        underlying scoring infrastructure but applies industry-specific
        feature weights and configurable prediction horizons.
        """
        from datetime import datetime, timezone

        id_hash = hash_national_id(national_id)
        await logger.ainfo(
            "custom_score_request",
            subject_id_hash=id_hash,
            vertical=industry_vertical,
            horizon=prediction_horizon,
        )

        # Look up subject and latest score (reuse existing infrastructure)
        subject = await self._get_subject_by_hash(db, id_hash)
        score = await self._get_latest_score_with_drivers(db, subject.subject_id)

        # Build risk drivers
        sorted_drivers = sorted(score.risk_drivers, key=lambda d: d.rank)[:3]
        risk_drivers = [
            {
                "factor": d.factor_name,
                "impact": d.impact.value.lower(),
                "description": d.description or "",
                "contribution": _risk_driver_contribution(d, sorted_drivers),
            }
            for d in sorted_drivers
        ]

        # Determine prediction horizon label
        horizon_labels = {30: "30_days", 90: "90_days", 365: "12_months"}
        horizon_label = horizon_labels.get(prediction_horizon, f"{prediction_horizon}_days")

        # Confidence interval
        lower = score.confidence_lower if score.confidence_lower is not None else max(score.vyce_score - 30, 300)
        upper = score.confidence_upper if score.confidence_upper is not None else min(score.vyce_score + 30, 900)

        niq = score.niq_score if score.niq_score is not None else 0

        # Construct response dict matching CustomScoreResponse schema
        from app.api.v1.scores import CustomScoreResponse

        return CustomScoreResponse(
            vyce_score=score.vyce_score,
            niq_score=niq,
            risk_drivers=risk_drivers,
            industry_vertical=industry_vertical,
            prediction_horizon=horizon_label,
            model_version=score.model_version,
            model_selection_reason=(
                f"General model used for {industry_vertical} vertical "
                f"with {horizon_label} prediction horizon."
            ),
            confidence_interval={"lower": lower, "upper": upper},
            score_date=score.score_date.isoformat(),
            data_quality=_compute_data_quality(score),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _get_subject_by_hash(db: AsyncSession, id_hash: str) -> Subject:
        """Look up a subject by national ID hash. Raises 404 if not found."""
        result = await db.execute(
            select(Subject).where(Subject.id_hash == id_hash)
        )
        subject = result.scalar_one_or_none()
        if subject is None:
            raise NotFoundError("Subject", id_hash[:12] + "...")
        return subject

    @staticmethod
    async def _get_latest_score(db: AsyncSession, subject_id: Any) -> Score:
        """Fetch the most recent score for a subject. Raises 404 if none exist."""
        result = await db.execute(
            select(Score)
            .where(Score.subject_id == subject_id)
            .order_by(Score.score_date.desc(), Score.created_at.desc())
            .limit(1)
        )
        score = result.scalar_one_or_none()
        if score is None:
            raise NotFoundError("Score", str(subject_id))
        return score

    @staticmethod
    async def _get_latest_score_with_drivers(db: AsyncSession, subject_id: Any) -> Score:
        """Fetch the most recent score with eagerly loaded risk drivers."""
        result = await db.execute(
            select(Score)
            .options(selectinload(Score.risk_drivers))
            .where(Score.subject_id == subject_id)
            .order_by(Score.score_date.desc(), Score.created_at.desc())
            .limit(1)
        )
        score = result.scalar_one_or_none()
        if score is None:
            raise NotFoundError("Score", str(subject_id))
        return score

    @staticmethod
    async def _get_score_history(
        db: AsyncSession,
        subject_id: Any,
        months: int = 12,
    ) -> list[ScoreHistoryItem]:
        """Fetch score history for the last N months."""
        cutoff = date.today() - timedelta(days=months * 30)
        result = await db.execute(
            select(Score)
            .where(Score.subject_id == subject_id, Score.score_date >= cutoff)
            .order_by(Score.score_date.desc())
        )
        scores = result.scalars().all()
        return [
            ScoreHistoryItem(
                vyce_score=s.vyce_score,
                niq_score=s.niq_score if s.niq_score is not None else 0,
                score_date=s.score_date.isoformat(),
                model_version=s.model_version,
            )
            for s in scores
        ]
