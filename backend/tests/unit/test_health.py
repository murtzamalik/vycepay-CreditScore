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
async def test_lite_score_requires_api_key(async_client: AsyncClient) -> None:
    """GET /v1/scores/lite/{id} without API key should return 401."""
    response = await async_client.get("/v1/scores/lite/12345678")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_lite_score_requires_valid_api_key(async_client: AsyncClient) -> None:
    """GET /v1/scores/lite/{id} with invalid API key should return 401."""
    response = await async_client.get(
        "/v1/scores/lite/12345678",
        headers={"X-API-Key": "invalid_key"},
    )
    assert response.status_code == 401
