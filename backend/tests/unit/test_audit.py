"""Tests for the audit logging service."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.audit_service import AuditService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeSession:
    """Minimal async session stub that captures ``.add()`` calls."""

    def __init__(self) -> None:
        self.added: list = []

    def add(self, obj) -> None:  # noqa: ANN001
        self.added.append(obj)


# ---------------------------------------------------------------------------
# Tests: log_api_request
# ---------------------------------------------------------------------------


class TestLogApiRequest:
    @pytest.mark.asyncio
    async def test_creates_log_entry(self) -> None:
        session = FakeSession()
        customer_id = str(uuid.uuid4())

        entry = await AuditService.log_api_request(
            db=session,  # type: ignore[arg-type]
            customer_id=customer_id,
            endpoint="GET /v1/scores/lite/12345",
            subject_id=None,
            response_status=200,
            response_time_ms=42,
            query_cost=1,
            ip_address="abcdef1234567890",
        )

        assert len(session.added) == 1
        assert session.added[0] is entry
        assert entry.endpoint == "GET /v1/scores/lite/12345"
        assert entry.response_status == 200
        assert entry.response_time_ms == 42
        assert entry.query_cost == 1

    @pytest.mark.asyncio
    async def test_customer_id_is_uuid(self) -> None:
        session = FakeSession()
        cid = str(uuid.uuid4())

        entry = await AuditService.log_api_request(
            db=session,  # type: ignore[arg-type]
            customer_id=cid,
            endpoint="POST /v1/scores/batch",
            subject_id=None,
            response_status=202,
            response_time_ms=100,
        )

        assert isinstance(entry.customer_id, uuid.UUID)
        assert str(entry.customer_id) == cid

    @pytest.mark.asyncio
    async def test_subject_id_optional(self) -> None:
        session = FakeSession()
        entry = await AuditService.log_api_request(
            db=session,  # type: ignore[arg-type]
            customer_id=str(uuid.uuid4()),
            endpoint="GET /v1/scores/lite/999",
            subject_id=None,
            response_status=404,
            response_time_ms=5,
        )
        assert entry.subject_id is None

    @pytest.mark.asyncio
    async def test_subject_id_converted_to_uuid(self) -> None:
        session = FakeSession()
        sid = str(uuid.uuid4())
        entry = await AuditService.log_api_request(
            db=session,  # type: ignore[arg-type]
            customer_id=str(uuid.uuid4()),
            endpoint="GET /v1/scores/pro/12345",
            subject_id=sid,
            response_status=200,
            response_time_ms=500,
        )
        assert isinstance(entry.subject_id, uuid.UUID)
        assert str(entry.subject_id) == sid

    @pytest.mark.asyncio
    async def test_hashed_ip_stored(self) -> None:
        session = FakeSession()
        hashed = "a1b2c3d4e5f6"

        entry = await AuditService.log_api_request(
            db=session,  # type: ignore[arg-type]
            customer_id=str(uuid.uuid4()),
            endpoint="GET /v1/scores/lite/111",
            subject_id=None,
            response_status=200,
            response_time_ms=10,
            ip_address=hashed,
        )
        assert entry.ip_address == hashed


# ---------------------------------------------------------------------------
# Tests: log_auth_event
# ---------------------------------------------------------------------------


class TestLogAuthEvent:
    @pytest.mark.asyncio
    async def test_auth_event_logs_without_error(self) -> None:
        """Auth events should complete without raising."""
        session = FakeSession()
        await AuditService.log_auth_event(
            db=session,  # type: ignore[arg-type]
            event_type="login",
            user_id=str(uuid.uuid4()),
            customer_id=None,
            ip_address="hashed_ip",
            success=True,
            details={"method": "password"},
        )

    @pytest.mark.asyncio
    async def test_failed_login_event(self) -> None:
        session = FakeSession()
        await AuditService.log_auth_event(
            db=session,  # type: ignore[arg-type]
            event_type="login_failed",
            user_id=None,
            customer_id=None,
            ip_address="hashed_ip",
            success=False,
            details={"reason": "invalid_password"},
        )
