"""Redis-backed score cache service (BRD §6.2.2).

Caches computed scores with a 24-hour TTL to avoid redundant database
queries and ML inference for repeated lookups of the same subject.

Key patterns:
    score:lite:{id_hash}  — Lite score data
    score:pro:{id_hash}   — Pro score data (includes risk drivers)
"""

from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis

from app.config import get_settings

settings = get_settings()


class ScoreCacheService:
    """Async Redis cache for VyceScore results."""

    TTL: int = settings.redis_score_ttl_seconds  # 24 hours default

    @staticmethod
    def _lite_key(subject_id_hash: str) -> str:
        return f"score:lite:{subject_id_hash}"

    @staticmethod
    def _pro_key(subject_id_hash: str) -> str:
        return f"score:pro:{subject_id_hash}"

    @staticmethod
    async def get_cached_score(
        redis: Redis,
        subject_id_hash: str,
        *,
        pro: bool = False,
    ) -> dict[str, Any] | None:
        """Get a cached score for a subject.

        Args:
            redis: Async Redis client.
            subject_id_hash: SHA-256 hash of the national ID.
            pro: If True, look up the Pro cache key; otherwise Lite.

        Returns:
            Deserialized score dict or None on cache miss.
        """
        key = (
            ScoreCacheService._pro_key(subject_id_hash)
            if pro
            else ScoreCacheService._lite_key(subject_id_hash)
        )
        raw = await redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)  # type: ignore[no-any-return]

    @staticmethod
    async def cache_score(
        redis: Redis,
        subject_id_hash: str,
        score_data: dict[str, Any],
        *,
        pro: bool = False,
    ) -> None:
        """Cache a score with the configured TTL.

        Args:
            redis: Async Redis client.
            subject_id_hash: SHA-256 hash of the national ID.
            score_data: Serializable score payload.
            pro: If True, store under the Pro cache key; otherwise Lite.
        """
        key = (
            ScoreCacheService._pro_key(subject_id_hash)
            if pro
            else ScoreCacheService._lite_key(subject_id_hash)
        )
        await redis.set(key, json.dumps(score_data), ex=ScoreCacheService.TTL)

    @staticmethod
    async def invalidate_cache(redis: Redis, subject_id_hash: str) -> None:
        """Invalidate all cached scores (Lite and Pro) for a subject.

        Args:
            redis: Async Redis client.
            subject_id_hash: SHA-256 hash of the national ID.
        """
        await redis.delete(
            ScoreCacheService._lite_key(subject_id_hash),
            ScoreCacheService._pro_key(subject_id_hash),
        )
