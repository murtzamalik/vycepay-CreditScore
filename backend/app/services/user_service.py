"""User management business logic (Phase 7 — Tasks 7.6–7.7)."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, VyceScoreError
from app.core.logging import get_logger
from app.models.user import User, UserRole
from app.schemas.admin import (
    UserCreateRequest,
    UserCreateResponse,
    UserResponse,
    UserUpdateRequest,
)
from app.services.auth_service import AuthService

logger = get_logger("user_service")


def _generate_temporary_password() -> str:
    """Generate a secure temporary password (16 chars, URL-safe)."""
    return secrets.token_urlsafe(16)


class UserService:
    """Service layer for admin user lifecycle management."""

    # ------------------------------------------------------------------
    # Task 7.6 — Create admin user
    # ------------------------------------------------------------------

    @staticmethod
    async def create_user(
        db: AsyncSession,
        payload: UserCreateRequest,
    ) -> UserCreateResponse:
        """Create a new admin portal user with a temporary password.

        Raises:
            VyceScoreError: If the email already exists.
        """
        # Check for duplicate email
        existing = await db.execute(
            select(User).where(User.email == payload.email)
        )
        if existing.scalar_one_or_none() is not None:
            raise VyceScoreError(
                code="DUPLICATE_EMAIL",
                message=f"A user with email '{payload.email}' already exists",
                status_code=409,
            )

        temp_password = _generate_temporary_password()
        password_hash = AuthService.hash_password(temp_password)

        now = datetime.now(timezone.utc)
        user = User(
            user_id=uuid.uuid4(),
            email=payload.email,
            full_name=payload.full_name,
            password_hash=password_hash,
            role=payload.role,
            is_active=True,
            must_change_password=True,
            created_at=now,
            updated_at=now,
        )
        db.add(user)
        await db.flush()

        await logger.ainfo(
            "user.created",
            user_id=str(user.user_id),
            email_hash=AuthService.hash_api_key(payload.email)[:12],
            role=user.role.value,
        )

        user_resp = UserResponse(
            user_id=user.user_id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            must_change_password=user.must_change_password,
            created_at=user.created_at,
            last_login=user.last_login,
        )

        return UserCreateResponse(user=user_resp, temporary_password=temp_password)

    # ------------------------------------------------------------------
    # Task 7.7 — Update / deactivate user
    # ------------------------------------------------------------------

    @staticmethod
    async def update_user(
        db: AsyncSession,
        user_id: uuid.UUID,
        payload: UserUpdateRequest,
    ) -> UserResponse:
        """Update a user's role and/or active status.

        When deactivating, sets ``is_active=False`` so that JWT validation
        rejects future requests from this user.

        Raises:
            NotFoundError: User does not exist.
        """
        result = await db.execute(
            select(User).where(User.user_id == user_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise NotFoundError("User", str(user_id))

        if payload.role is not None:
            user.role = payload.role
        if payload.is_active is not None:
            user.is_active = payload.is_active

        await db.flush()

        action = "updated"
        if payload.is_active is False:
            action = "deactivated"
        elif payload.is_active is True:
            action = "reactivated"

        await logger.ainfo(
            f"user.{action}",
            user_id=str(user_id),
            role=user.role.value,
            is_active=user.is_active,
        )

        return UserResponse(
            user_id=user.user_id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            must_change_password=user.must_change_password,
            created_at=user.created_at,
            last_login=user.last_login,
        )
