"""Tests for the Redis-backed sliding-window rate limiter."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.rate_limiter import RATE_LIMIT_WINDOW, RateLimiter, RateLimitResult
from app.models.customer import LicenseTier


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeRedis:
    """Minimal in-memory fake that mimics the Redis sorted-set commands
    used by :class:`RateLimiter`.
    """

    def __init__(self) -> None:
        self._data: dict[str, list[tuple[str, float]]] = {}
        self._ttls: dict[str, int] = {}

    # -- pipeline support --------------------------------------------------

    def pipeline(self) -> FakePipeline:
        return FakePipeline(self)

    # -- sorted set commands ------------------------------------------------

    async def zremrangebyscore(self, key: str, min_: float, max_: float) -> int:
        entries = self._data.get(key, [])
        before = len(entries)
        self._data[key] = [(m, s) for m, s in entries if not (min_ <= s <= max_)]
        return before - len(self._data[key])

    async def zcard(self, key: str) -> int:
        return len(self._data.get(key, []))

    async def zadd(self, key: str, mapping: dict[str, float]) -> int:
        entries = self._data.setdefault(key, [])
        added = 0
        for member, score in mapping.items():
            entries.append((member, score))
            added += 1
        return added

    async def zrange(self, key: str, start: int, stop: int, withscores: bool = False):
        entries = sorted(self._data.get(key, []), key=lambda x: x[1])
        sliced = entries[start: stop + 1]
        if withscores:
            return sliced
        return [m for m, _ in sliced]

    async def expire(self, key: str, seconds: int) -> bool:
        self._ttls[key] = seconds
        return True

    async def delete(self, key: str) -> int:
        if key in self._data:
            del self._data[key]
            return 1
        return 0


class FakePipeline:
    """Records commands and executes them sequentially."""

    def __init__(self, redis: FakeRedis) -> None:
        self._redis = redis
        self._commands: list[tuple[str, tuple, dict]] = []

    def zremrangebyscore(self, key, min_, max_):
        self._commands.append(("zremrangebyscore", (key, min_, max_), {}))
        return self

    def zcard(self, key):
        self._commands.append(("zcard", (key,), {}))
        return self

    def zadd(self, key, mapping):
        self._commands.append(("zadd", (key, mapping), {}))
        return self

    def expire(self, key, seconds):
        self._commands.append(("expire", (key, seconds), {}))
        return self

    def incrby(self, key, amount):
        self._commands.append(("incrby", (key, amount), {}))
        return self

    async def execute(self):
        results = []
        for cmd, args, kwargs in self._commands:
            method = getattr(self._redis, cmd)
            result = await method(*args, **kwargs)
            results.append(result)
        self._commands.clear()
        return results


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def limiter(fake_redis: FakeRedis) -> RateLimiter:
    return RateLimiter(fake_redis)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_first_request_allowed(limiter: RateLimiter) -> None:
    """The very first request for a customer should be allowed."""
    result = await limiter.check_rate_limit("cust-001", LicenseTier.LITE)

    assert result.allowed is True
    assert result.limit == 1000  # LITE tier default
    assert result.remaining == 999


@pytest.mark.asyncio
async def test_rate_limit_headers_populated(limiter: RateLimiter) -> None:
    """Result should contain all fields needed for response headers."""
    result = await limiter.check_rate_limit("cust-002", LicenseTier.PRO)

    assert result.limit == 500
    assert result.remaining == 499
    assert result.window == RATE_LIMIT_WINDOW
    assert result.reset > 0


@pytest.mark.asyncio
async def test_deep_dive_tier_limit(limiter: RateLimiter) -> None:
    result = await limiter.check_rate_limit("cust-003", LicenseTier.DEEP_DIVE)
    assert result.limit == 200


@pytest.mark.asyncio
async def test_rate_limit_exceeded(fake_redis: FakeRedis, limiter: RateLimiter) -> None:
    """After exhausting the limit, subsequent requests should be denied."""
    customer = "cust-heavy"
    tier = LicenseTier.DEEP_DIVE  # 200/hr

    # Pre-fill 200 entries to simulate exhausted limit
    key = f"rate_limit:{customer}"
    now = time.time()
    for i in range(200):
        fake_redis._data.setdefault(key, []).append((f"{now}:{i}", now))

    result = await limiter.check_rate_limit(customer, tier)

    assert result.allowed is False
    assert result.remaining == 0
    assert result.limit == 200


@pytest.mark.asyncio
async def test_old_entries_pruned(fake_redis: FakeRedis, limiter: RateLimiter) -> None:
    """Entries outside the window should be pruned, freeing capacity."""
    customer = "cust-old"
    key = f"rate_limit:{customer}"
    old_time = time.time() - RATE_LIMIT_WINDOW - 100  # well outside window

    # Pre-fill with stale entries
    for i in range(200):
        fake_redis._data.setdefault(key, []).append((f"{old_time}:{i}", old_time))

    result = await limiter.check_rate_limit(customer, LicenseTier.DEEP_DIVE)

    # Stale entries should be pruned → request allowed
    assert result.allowed is True


@pytest.mark.asyncio
async def test_reset_clears_counter(fake_redis: FakeRedis, limiter: RateLimiter) -> None:
    customer = "cust-reset"
    await limiter.check_rate_limit(customer, LicenseTier.LITE)

    await limiter.reset(customer)

    # Counter should be clean again
    result = await limiter.check_rate_limit(customer, LicenseTier.LITE)
    assert result.allowed is True
    assert result.remaining == 999
