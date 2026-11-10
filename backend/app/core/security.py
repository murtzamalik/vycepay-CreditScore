"""FastAPI security dependencies for protecting endpoints.

Two authentication schemes:
  1. API Key (X-API-Key header) — for partner / FI API calls
  2. JWT Bearer token — for admin portal users

Security invariants:
  - Raw API keys and passwords are NEVER logged.
  - All auth failures are logged with structured context.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.database import get_db
from app.models.customer import Customer, CustomerStatus
from app.models.user import User

logger = get_logger("security")

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against its bcrypt hash."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ---------------------------------------------------------------------------
# JWT tokens
# ---------------------------------------------------------------------------

def create_access_token(
    subject: str,
    role: str,
    settings: Settings | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create a signed JWT access token."""
    settings = settings or get_settings()
    now = datetime.now(timezone.utc)
    claims: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
    }
    if extra_claims:
        claims.update(extra_claims)
    return jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings | None = None) -> dict[str, Any]:
    """Decode and verify a JWT access token. Raises HTTPException on failure."""
    settings = settings or get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_TOKEN", "message": str(exc), "details": {}}},
        ) from exc


# ---------------------------------------------------------------------------
# API key utilities
# ---------------------------------------------------------------------------
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def generate_api_key() -> str:
    """Generate a cryptographically secure API key prefixed with ``vyc_``."""
    return f"vyc_{secrets.token_urlsafe(32)}"


def hash_api_key(raw_key: str) -> str:
    """Return the SHA-256 hex digest of a raw API key."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


async def require_api_key(
    api_key: str | None = Security(api_key_header),
) -> str:
    """FastAPI dependency that enforces the presence of a valid API key header.

    Actual database validation is delegated to ``get_current_customer``;
    this dependency merely ensures the header is present.
    """
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "MISSING_API_KEY",
                    "message": "X-API-Key header is required",
                    "details": {},
                }
            },
        )
    return api_key


# ---------------------------------------------------------------------------
# National ID hashing (SHA-256)
# ---------------------------------------------------------------------------

def hash_national_id(national_id: str) -> str:
    """Return the SHA-256 hex digest of a national ID for safe storage/logging."""
    return hashlib.sha256(national_id.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# FastAPI dependencies — API Key auth (partner / FI calls)
# ---------------------------------------------------------------------------

async def get_current_customer(
    api_key: str = Security(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> Customer:
    """Validate X-API-Key header and return the associated Customer.

    Raises:
        HTTPException 401: Missing or invalid API key.
        HTTPException 403: Customer account is not active.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "MISSING_API_KEY",
                    "message": "X-API-Key header is required",
                    "details": {},
                }
            },
        )

    key_hash = hash_api_key(api_key)
    result = await db.execute(
        select(Customer).where(Customer.api_key_hash == key_hash)
    )
    customer = result.scalar_one_or_none()

    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "INVALID_API_KEY",
                    "message": "The provided API key is not valid",
                    "details": {},
                }
            },
        )

    if customer.status != CustomerStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "ACCOUNT_INACTIVE",
                    "message": "Customer account is not active",
                    "details": {},
                }
            },
        )

    return customer


# ---------------------------------------------------------------------------
# FastAPI dependencies — JWT auth (admin portal)
# ---------------------------------------------------------------------------

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/login", auto_error=False)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Decode JWT Bearer token and return the associated User.

    Raises:
        HTTPException 401: Missing, invalid, or expired token.
        HTTPException 403: User account is deactivated.
    """
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "MISSING_TOKEN",
                    "message": "Bearer token is required",
                    "details": {},
                }
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "INVALID_TOKEN",
                    "message": "Token is invalid or expired",
                    "details": {},
                }
            },
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    # Ensure it's an access token
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "INVALID_TOKEN_TYPE",
                    "message": "Expected an access token",
                    "details": {},
                }
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "INVALID_TOKEN",
                    "message": "Token payload is missing subject",
                    "details": {},
                }
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "INVALID_TOKEN",
                    "message": "Token contains invalid user ID",
                    "details": {},
                }
            },
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    result = await db.execute(select(User).where(User.user_id == user_uuid))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "USER_NOT_FOUND",
                    "message": "User associated with token no longer exists",
                    "details": {},
                }
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "ACCOUNT_DEACTIVATED",
                    "message": "User account is deactivated",
                    "details": {},
                }
            },
        )

    return user
