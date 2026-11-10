"""Authentication endpoints for the admin portal (BRD UC-AUTH-002, UC-AUTH-003).

Routes:
  POST /v1/auth/login           — Login with email/password, return JWT tokens
  POST /v1/auth/refresh         — Refresh access token using refresh token
  POST /v1/auth/password-reset  — Request password reset (accepts email)
  POST /v1/auth/password-reset/confirm — Confirm reset with token + new password
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.database import get_db
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
)
from app.schemas.common import ErrorResponse
from app.services.auth_service import AuthService

logger = get_logger("auth_endpoints")
router = APIRouter(prefix="/auth", tags=["Authentication"])

auth_service = AuthService()


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and obtain JWT tokens",
    responses={
        401: {"model": ErrorResponse, "description": "Invalid credentials"},
        403: {"model": ErrorResponse, "description": "Account locked"},
    },
)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Authenticate an admin portal user with email and password.

    Returns an access token (15-minute TTL) and a refresh token (7-day TTL).
    After 5 consecutive failed attempts the account is locked for 30 minutes.
    """
    return await AuthService.authenticate_user(db, body.email, body.password)


@router.post(
    "/refresh",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh an access token",
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or expired refresh token"},
    },
)
async def refresh_token(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Exchange a valid refresh token for a new access + refresh token pair."""
    from app.config import get_settings

    settings = get_settings()

    # Decode and validate the refresh token
    payload = AuthService.decode_token(body.refresh_token)
    if payload.type != "refresh":
        from app.core.exceptions import UnauthorizedError
        raise UnauthorizedError(message="Expected a refresh token")

    # Verify user still exists and is active
    from sqlalchemy import select
    from app.models.user import User
    import uuid as _uuid

    user_uuid = _uuid.UUID(payload.sub)
    result = await db.execute(select(User).where(User.user_id == user_uuid))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        from app.core.exceptions import UnauthorizedError
        raise UnauthorizedError(message="User not found or inactive")

    access_token = AuthService.create_access_token(
        user_id=str(user.user_id),
        role=user.role.value,
    )
    new_refresh_token = AuthService.create_refresh_token(user_id=str(user.user_id))

    return LoginResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post(
    "/password-reset",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request a password reset",
    response_model=dict[str, str],
)
async def request_password_reset(
    body: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Request a password reset email.

    Always returns 202 Accepted regardless of whether the email exists,
    to prevent email enumeration attacks.
    """
    from sqlalchemy import select
    from app.models.user import User

    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is not None:
        reset_token = AuthService.create_reset_token(body.email)
        # In production, send this token via email.
        # Never log the raw token — only log the event.
        await logger.ainfo(
            "auth.password_reset_requested",
            user_id=str(user.user_id),
        )

    return {"message": "If the email is registered, a reset link has been sent."}


@router.post(
    "/password-reset/confirm",
    status_code=status.HTTP_200_OK,
    summary="Confirm password reset with token",
    response_model=dict[str, str],
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or expired reset token"},
    },
)
async def confirm_password_reset(
    body: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Validate the reset token and set a new password."""
    await AuthService.reset_password(db, body.token, body.new_password)
    return {"message": "Password has been reset successfully."}
