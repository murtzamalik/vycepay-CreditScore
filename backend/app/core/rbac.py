"""Role-based access control (BRD UC-USER-003, §7.2.2)."""

from __future__ import annotations

from typing import Any

from fastapi import Depends

from app.core.exceptions import ForbiddenError
from app.models.user import UserRole

# ---------------------------------------------------------------------------
# Permission matrix — each role maps to a set of permission strings.
# The wildcard "*" grants access to every permission.
# ---------------------------------------------------------------------------
ROLE_PERMISSIONS: dict[UserRole, set[str]] = {
    UserRole.ADMIN: {"*"},
    UserRole.OPERATOR: {
        "scores:read",
        "scores:write",
        "customers:read",
        "customers:write",
        "users:read",
        "audit:read",
        "kpi:read",
    },
    UserRole.PARTNER: {
        "scores:read",
        "batch:write",
        "feedback:write",
        "partner:usage",
        "partner:api_keys",
    },
    UserRole.READ_ONLY: {
        "scores:read",
        "kpi:read",
        "audit:read",
    },
}


def get_role_permissions(role: UserRole) -> set[str]:
    """Return the set of permissions granted to *role*."""
    return ROLE_PERMISSIONS.get(role, set())


def has_permission(role: UserRole, permission: str) -> bool:
    """Return ``True`` if *role* is granted *permission*."""
    perms = get_role_permissions(role)
    return "*" in perms or permission in perms


# ---------------------------------------------------------------------------
# FastAPI dependency factory
# ---------------------------------------------------------------------------


def require_permissions(*permissions: str) -> Any:
    """Return a FastAPI dependency that enforces the listed permissions.

    Usage::

        @router.get("/admin/users", dependencies=[Depends(require_permissions("users:read"))])
        async def list_users(): ...

    Or inject the resolved user::

        @router.get("/admin/users")
        async def list_users(user = Depends(require_permissions("users:read"))):
            ...
    """

    async def _checker(current_user: dict = Depends(_get_current_user_stub)) -> dict:  # noqa: B008
        role = current_user.get("role")
        if role is None:
            raise ForbiddenError("No role assigned to user")

        # Normalise: accept both UserRole enum and raw string values
        if isinstance(role, str):
            try:
                role = UserRole(role)
            except ValueError:
                raise ForbiddenError(f"Unknown role: {role}")

        user_perms = get_role_permissions(role)
        if "*" not in user_perms:
            for perm in permissions:
                if perm not in user_perms:
                    raise ForbiddenError(
                        f"Insufficient permissions. Required: {perm}"
                    )
        return current_user

    return _checker


# ---------------------------------------------------------------------------
# Stub: current-user resolver
#
# In production this is replaced by a real dependency that decodes the JWT
# and fetches the user from the database. For now it extracts the ``role``
# claim from a decoded JWT payload set on ``request.state`` by auth
# middleware.
# ---------------------------------------------------------------------------

async def _get_current_user_stub() -> dict:
    """Placeholder — overridden at app startup with real dependency."""
    raise NotImplementedError(
        "_get_current_user_stub must be replaced via app dependency_overrides"
    )
