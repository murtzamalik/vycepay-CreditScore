"""Tests for the health-check endpoint."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_200(async_client: AsyncClient) -> None:
    """GET /v1/health should return 200 with status healthy."""
    response = await async_client.get("/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["version"] == "0.1.0"
    assert "timestamp" in body


@pytest.mark.asyncio
async def test_health_response_format(async_client: AsyncClient) -> None:
    """Health response should contain exactly the expected keys."""
    response = await async_client.get("/v1/health")
    body = response.json()
    assert set(body.keys()) == {"status", "version", "timestamp"}
