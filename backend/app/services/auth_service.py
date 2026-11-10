"""Core authentication service — password, API key, JWT, and login management.

Security invariants:
  - Passwords and raw API keys are NEVER logged.
  - All auth events are logged with structured fields (email hash, user_id, event).
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.logging import get_logger
from app.models.customer import Customer, CustomerStatus
from app.models.user import User
from app.schemas.auth import LoginResponse, TokenPayload

logger = get_logger("auth_service")
settings = get_settings()

# Maximum consecutive failed login attempts before account lockout
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 30


class AuthService:
    """Authentication and authorisation logic for VyceScore."""

    # ------------------------------------------------------------------
    # Password management
    # ------------------------------------------------------------------

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a plaintext password with bcrypt."""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    @staticmethod
    def verify_password(plain: str, hashed: str) -> bool:
        """Verify a plaintext password against its bcrypt hash."""
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))

    # ------------------------------------------------------------------
    # API key management (for Customer / FI auth — BRD UC-AUTH-001)
    # ------------------------------------------------------------------

    @staticmethod
    def generate_api_key() -> tuple[str, str]:
        """Generate a cryptographically secure API key.

        Returns:
            Tuple of (raw_key, sha256_hash).
        """
        raw_key = f"vyc_{secrets.token_urlsafe(32)}"
        key_hash = AuthService.hash_api_key(raw_key)
        return raw_key, key_hash

    @staticmethod
    def hash_api_key(raw_key: str) -> str:
        """Return the SHA-256 hex digest of a raw API key."""
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    @staticmethod
    async def validate_api_key(db: AsyncSession, api_key: str) -> Customer | None:
        """Look up an active customer by their API key hash.

        Returns the Customer row or ``None`` if not found / inactive.
        """
        key_hash = AuthService.hash_api_key(api_key)
        result = await db.execute(
            select(Customer).where(
                Customer.api_key_hash == key_hash,
                Customer.status == CustomerStatus.ACTIVE,
            )
        )
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # JWT management (BRD UC-AUTH-002, UC-AUTH-004)
    # ------------------------------------------------------------------

    @staticmethod
    def create_access_token(user_id: str, role: str) -> str:
        """Create a signed JWT access token (15-minute expiry)."""
        now = datetime.now(timezone.utc)
        claims = {
            "sub": user_id,
            "role": role,
            "type": "access",
            "iat": now,
            "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
        }
        return jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    @staticmethod
    def create_refresh_token(user_id: str) -> str:
        """Create a signed JWT refresh token (7-day expiry)."""
        now = datetime.now(timezone.utc)
        claims = {
            "sub": user_id,
            "type": "refresh",
            "iat": now,
            "exp": now + timedelta(days=settings.jwt_refresh_token_expire_days),
        }
        return jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    @staticmethod
    def decode_token(token: str) -> TokenPayload:
        """Decode and validate a JWT token.

        Raises:
            UnauthorizedError: If the token is invalid or expired.
        """
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )
            return TokenPayload(
                sub=payload["sub"],
                role=payload.get("role", ""),
                exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
                type=payload.get("type", "access"),
            )
        except JWTError as exc:
            raise UnauthorizedError(message="Invalid or expired token") from exc

    # ------------------------------------------------------------------
    # Login (BRD UC-AUTH-002)
    # ------------------------------------------------------------------

    @staticmethod
    async def authenticate_user(db: AsyncSession, email: str, password: str) -> LoginResponse:
        """Authenticate admin portal user and return JWT tokens.

        Handles failed-attempt counting and account lockout (5 attempts,
        30-minute lockout window).

        Raises:
            UnauthorizedError: Bad credentials or inactive account.
            ForbiddenError: Account locked due to too many failed attempts.
        """
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is None:
            # Constant-time: hash the password anyway to prevent timing attacks
            bcrypt.hashpw(b"dummy-password-to-prevent-timing-leak", bcrypt.gensalt())
            await logger.awarning("auth.login_failed", reason="unknown_email")
            raise UnauthorizedError(message="Invalid email or password")

        # Check lockout
        now = datetime.now(timezone.utc)
        if user.locked_until is not None and user.locked_until > now:
            await logger.awarning(
                "auth.login_locked",
                user_id=str(user.user_id),
                locked_until=user.locked_until.isoformat(),
            )
            raise ForbiddenError(
                message="Account is temporarily locked due to too many failed login attempts"
            )

        # Verify password
        if not AuthService.verify_password(password, user.password_hash):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
                user.locked_until = now + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
                await logger.awarning(
                    "auth.account_locked",
                    user_id=str(user.user_id),
                    failed_attempts=user.failed_login_attempts,
                )
            await db.flush()
            await logger.awarning(
                "auth.login_failed",
                user_id=str(user.user_id),
                reason="bad_password",
                failed_attempts=user.failed_login_attempts,
            )
            raise UnauthorizedError(message="Invalid email or password")

        # Check active
        if not user.is_active:
            await logger.awarning(
                "auth.login_failed",
                user_id=str(user.user_id),
                reason="inactive_account",
            )
            raise UnauthorizedError(message="Account is deactivated")

        # Successful login — reset counters
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = now
        await db.flush()

        access_token = AuthService.create_access_token(
            user_id=str(user.user_id),
            role=user.role.value,
        )
        refresh_token = AuthService.create_refresh_token(user_id=str(user.user_id))

        await logger.ainfo("auth.login_success", user_id=str(user.user_id))

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.jwt_access_token_expire_minutes * 60,
        )

    # ------------------------------------------------------------------
    # Password reset (BRD UC-AUTH-003)
    # ------------------------------------------------------------------

    @staticmethod
    def create_reset_token(email: str) -> str:
        """Create a JWT password-reset token (1-hour expiry)."""
        now = datetime.now(timezone.utc)
        claims = {
            "sub": email,
            "type": "reset",
            "iat": now,
            "exp": now + timedelta(hours=1),
        }
        return jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    @staticmethod
    async def reset_password(db: AsyncSession, token: str, new_password: str) -> None:
        """Validate reset token and update user password.

        Raises:
            UnauthorizedError: If the token is invalid, expired, or not a reset token.
        """
        payload = AuthService.decode_token(token)
        if payload.type != "reset":
            raise UnauthorizedError(message="Invalid reset token")

        result = await db.execute(select(User).where(User.email == payload.sub))
        user = result.scalar_one_or_none()
        if user is None:
            raise UnauthorizedError(message="Invalid reset token")

        user.password_hash = AuthService.hash_password(new_password)
        user.must_change_password = False
        user.failed_login_attempts = 0
        user.locked_until = None
        await db.flush()

        await logger.ainfo("auth.password_reset", user_id=str(user.user_id))
