"""MFA (Multi-Factor Authentication) endpoints (BRD §13, Phase 12.7).

Routes:
  POST /v1/auth/mfa/setup    — Initiate MFA setup (generate secret + backup codes)
  POST /v1/auth/mfa/verify   — Verify TOTP code (confirm setup or login challenge)
  POST /v1/auth/mfa/disable  — Disable MFA for the authenticated user
  GET  /v1/auth/mfa/status   — Check MFA status for the authenticated user
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.common import ErrorResponse
from app.schemas.mfa import (
    MFADisableRequest,
    MFASetupResponse,
    MFAStatusResponse,
    MFAVerifyRequest,
    MFAVerifyResponse,
)
from app.services.auth_service import AuthService
from app.services.mfa_service import MFAService

logger = get_logger("mfa_endpoints")
router = APIRouter(prefix="/auth/mfa", tags=["Multi-Factor Authentication"])


@router.post(
    "/setup",
    response_model=MFASetupResponse,
    status_code=status.HTTP_200_OK,
    summary="Initiate MFA setup",
    responses={
        400: {"model": ErrorResponse, "description": "MFA already enabled"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
    },
)
async def setup_mfa(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MFASetupResponse:
    """Generate a new TOTP secret and backup codes for the authenticated user.

    The user must verify with a valid TOTP code to activate MFA.
    The secret and backup codes are shown only once.
    """
    if MFAService.is_mfa_enabled(current_user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "MFA_ALREADY_ENABLED",
                    "message": "MFA is already enabled. Disable it first to re-setup.",
                    "details": {},
                }
            },
        )

    result = await MFAService.setup_mfa(db, current_user)

    return MFASetupResponse(
        secret=result["secret"],
        totp_uri=result["totp_uri"],
        backup_codes=result["backup_codes"],
    )


@router.post(
    "/verify",
    response_model=MFAVerifyResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify a TOTP code",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid TOTP code"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
    },
)
async def verify_mfa(
    body: MFAVerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MFAVerifyResponse:
    """Verify a TOTP code to confirm MFA setup or as a login challenge.

    If MFA is not yet enabled (setup pending), this confirms the setup
    and activates MFA. If MFA is already enabled, this verifies the code.
    """
    if not MFAService.is_mfa_enabled(current_user):
        # MFA setup confirmation flow
        try:
            await MFAService.confirm_mfa_setup(db, current_user, body.code)
            return MFAVerifyResponse(
                verified=True,
                message="MFA has been successfully enabled for your account.",
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "INVALID_CODE",
                        "message": str(exc),
                        "details": {},
                    }
                },
            ) from exc
    else:
        # MFA verification flow
        is_valid = await MFAService.verify_mfa(db, current_user, body.code)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "INVALID_CODE",
                        "message": "Invalid TOTP or backup code",
                        "details": {},
                    }
                },
            )

        return MFAVerifyResponse(
            verified=True,
            message="MFA verification successful.",
        )


@router.post(
    "/disable",
    response_model=MFAVerifyResponse,
    status_code=status.HTTP_200_OK,
    summary="Disable MFA for the authenticated user",
    responses={
        400: {"model": ErrorResponse, "description": "MFA not enabled or invalid password"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
    },
)
async def disable_mfa(
    body: MFADisableRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MFAVerifyResponse:
    """Disable MFA for the authenticated user.

    Requires the user's current password to confirm identity.
    """
    if not MFAService.is_mfa_enabled(current_user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "MFA_NOT_ENABLED",
                    "message": "MFA is not currently enabled for your account",
                    "details": {},
                }
            },
        )

    # Verify password
    if not AuthService.verify_password(body.password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_PASSWORD",
                    "message": "Password is incorrect",
                    "details": {},
                }
            },
        )

    await MFAService.disable_mfa(db, current_user)

    return MFAVerifyResponse(
        verified=True,
        message="MFA has been disabled for your account.",
    )


@router.get(
    "/status",
    response_model=MFAStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Check MFA status",
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required"},
    },
)
async def mfa_status(
    current_user: User = Depends(get_current_user),
) -> MFAStatusResponse:
    """Return the current MFA status for the authenticated user."""
    mfa_enabled = MFAService.is_mfa_enabled(current_user)
    mfa_required = MFAService.is_mfa_required(current_user.role)

    backup_codes_remaining: int | None = None
    if mfa_enabled:
        codes = getattr(current_user, "mfa_backup_codes", None)
        backup_codes_remaining = len(codes) if codes else 0

    return MFAStatusResponse(
        mfa_enabled=mfa_enabled,
        mfa_required=mfa_required,
        backup_codes_remaining=backup_codes_remaining,
    )
