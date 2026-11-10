"""Tests for RBAC permission checking."""

from __future__ import annotations

import pytest

from app.core.exceptions import ForbiddenError
from app.core.rbac import (
    ROLE_PERMISSIONS,
    get_role_permissions,
    has_permission,
    require_permissions,
)
from app.models.user import UserRole


# ---------------------------------------------------------------------------
# get_role_permissions / has_permission
# ---------------------------------------------------------------------------


class TestGetRolePermissions:
    def test_admin_has_wildcard(self) -> None:
        perms = get_role_permissions(UserRole.ADMIN)
        assert "*" in perms

    def test_operator_permissions(self) -> None:
        perms = get_role_permissions(UserRole.OPERATOR)
        assert "scores:read" in perms
        assert "scores:write" in perms
        assert "customers:read" in perms
        assert "customers:write" in perms
        assert "users:read" in perms
        assert "audit:read" in perms
        assert "kpi:read" in perms
        assert "*" not in perms

    def test_partner_permissions(self) -> None:
        perms = get_role_permissions(UserRole.PARTNER)
        assert "scores:read" in perms
        assert "batch:write" in perms
        assert "feedback:write" in perms
        # Partners cannot access admin features
        assert "users:read" not in perms
        assert "customers:write" not in perms

    def test_read_only_permissions(self) -> None:
        perms = get_role_permissions(UserRole.READ_ONLY)
        assert "scores:read" in perms
        assert "kpi:read" in perms
        assert "audit:read" in perms
        assert "scores:write" not in perms


class TestHasPermission:
    def test_admin_has_any_permission(self) -> None:
        assert has_permission(UserRole.ADMIN, "scores:read") is True
        assert has_permission(UserRole.ADMIN, "arbitrary:anything") is True

    def test_partner_has_scores_read(self) -> None:
        assert has_permission(UserRole.PARTNER, "scores:read") is True

    def test_partner_lacks_users_read(self) -> None:
        assert has_permission(UserRole.PARTNER, "users:read") is False

    def test_read_only_cannot_write(self) -> None:
        assert has_permission(UserRole.READ_ONLY, "scores:write") is False
        assert has_permission(UserRole.READ_ONLY, "customers:write") is False

    def test_operator_can_write_scores(self) -> None:
        assert has_permission(UserRole.OPERATOR, "scores:write") is True


# ---------------------------------------------------------------------------
# require_permissions dependency
# ---------------------------------------------------------------------------


class TestRequirePermissions:
    @pytest.mark.asyncio
    async def test_admin_passes_any_check(self) -> None:
        checker = require_permissions("scores:read", "users:read", "kpi:read")
        user = {"role": UserRole.ADMIN, "user_id": "u1"}
        # Override the stub dependency with direct call
        result = await checker(current_user=user)
        assert result == user

    @pytest.mark.asyncio
    async def test_operator_passes_permitted_check(self) -> None:
        checker = require_permissions("scores:read")
        user = {"role": UserRole.OPERATOR, "user_id": "u2"}
        result = await checker(current_user=user)
        assert result["user_id"] == "u2"

    @pytest.mark.asyncio
    async def test_partner_fails_admin_check(self) -> None:
        checker = require_permissions("users:read")
        user = {"role": UserRole.PARTNER, "user_id": "u3"}
        with pytest.raises(ForbiddenError, match="Insufficient permissions"):
            await checker(current_user=user)

    @pytest.mark.asyncio
    async def test_read_only_fails_write(self) -> None:
        checker = require_permissions("scores:write")
        user = {"role": UserRole.READ_ONLY, "user_id": "u4"}
        with pytest.raises(ForbiddenError):
            await checker(current_user=user)

    @pytest.mark.asyncio
    async def test_string_role_resolved(self) -> None:
        """Roles passed as plain strings should be normalised."""
        checker = require_permissions("scores:read")
        user = {"role": "Partner", "user_id": "u5"}
        result = await checker(current_user=user)
        assert result["user_id"] == "u5"

    @pytest.mark.asyncio
    async def test_unknown_role_rejected(self) -> None:
        checker = require_permissions("scores:read")
        user = {"role": "SuperUser", "user_id": "u6"}
        with pytest.raises(ForbiddenError, match="Unknown role"):
            await checker(current_user=user)

    @pytest.mark.asyncio
    async def test_missing_role_rejected(self) -> None:
        checker = require_permissions("scores:read")
        user = {"user_id": "u7"}
        with pytest.raises(ForbiddenError, match="No role assigned"):
            await checker(current_user=user)
