"""FastAPI dependency injection providers."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db

# Re-export for convenience so endpoints import from one place
SettingsDep = Annotated[Settings, Depends(get_settings)]
DbSessionDep = Annotated[AsyncSession, Depends(get_db)]

# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------

_redis_pool: Redis | None = None


async def get_redis() -> AsyncGenerator[Redis, None]:
    """Yield a shared async Redis client.

    The client is lazily initialised on first call and reuses a single
    connection pool for the lifetime of the process.  The pool is closed
    gracefully via :func:`close_redis`.
    """
    global _redis_pool  # noqa: PLW0603
    if _redis_pool is None:
        settings = get_settings()
        _redis_pool = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
    try:
        yield _redis_pool
    except Exception:
        raise


async def close_redis() -> None:
    """Close the shared Redis connection pool (call on app shutdown)."""
    global _redis_pool  # noqa: PLW0603
    if _redis_pool is not None:
        await _redis_pool.close()
        _redis_pool = None


RedisDep = Annotated[Redis, Depends(get_redis)]

__all__ = [
    "DbSessionDep",
    "RedisDep",
    "SettingsDep",
    "close_redis",
    "get_db",
    "get_redis",
    "get_settings",
]
