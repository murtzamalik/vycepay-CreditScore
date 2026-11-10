"""Tests for the VyceScore authentication system.

Covers:
  - Password hashing and verification
  - API key generation and hashing
  - JWT creation, decoding, and expiry
  - Failed login lockout logic
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jose import jwt

from app.config import get_settings
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.models.user import User, UserRole
from app.schemas.auth import TokenPayload
from app.services.auth_service import (
    MAX_FAILED_ATTEMPTS,
    AuthService,
)

settings = get_settings()


# -----------------------------------------------------------------------
# Password hashing and verification
# -----------------------------------------------------------------------


class TestPasswordHashing:
    """Password hashing with bcrypt."""

    def test_hash_password_returns_bcrypt_hash(self) -> None:
        hashed = AuthService.hash_password("SecureP@ss1")
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
        assert hashed != "SecureP@ss1"

    def test_verify_password_correct(self) -> None:
        hashed = AuthService.hash_password("MyPassword123")
        assert AuthService.verify_password("MyPassword123", hashed) is True

    def test_verify_password_incorrect(self) -> None:
        hashed = AuthService.hash_password("MyPassword123")
        assert AuthService.verify_password("WrongPassword", hashed) is False

    def test_different_passwords_produce_different_hashes(self) -> None:
        h1 = AuthService.hash_password("Password1")
        h2 = AuthService.hash_password("Password2")
        assert h1 != h2

    def test_same_password_produces_different_hashes_due_to_salt(self) -> None:
        h1 = AuthService.hash_password("SamePassword")
        h2 = AuthService.hash_password("SamePassword")
        # bcrypt uses random salt, so hashes differ
        assert h1 != h2
        # But both verify correctly
        assert AuthService.verify_password("SamePassword", h1) is True
        assert AuthService.verify_password("SamePassword", h2) is True


# -----------------------------------------------------------------------
# API key generation and hashing
# -----------------------------------------------------------------------


class TestAPIKeyManagement:
    """API key generation and SHA-256 hashing."""

    def test_generate_api_key_returns_tuple(self) -> None:
        raw_key, key_hash = AuthService.generate_api_key()
        assert isinstance(raw_key, str)
        assert isinstance(key_hash, str)

    def test_generated_key_has_prefix(self) -> None:
        raw_key, _ = AuthService.generate_api_key()
        assert raw_key.startswith("vyc_")

    def test_hash_matches_generated_hash(self) -> None:
        raw_key, key_hash = AuthService.generate_api_key()
        assert AuthService.hash_api_key(raw_key) == key_hash

    def test_hash_is_sha256_hex(self) -> None:
        _, key_hash = AuthService.generate_api_key()
        assert len(key_hash) == 64  # SHA-256 hex digest length
        assert all(c in "0123456789abcdef" for c in key_hash)

    def test_different_keys_produce_different_hashes(self) -> None:
        _, h1 = AuthService.generate_api_key()
        _, h2 = AuthService.generate_api_key()
        assert h1 != h2

    def test_hash_api_key_deterministic(self) -> None:
        raw_key = "vyc_test-key-12345"
        h1 = AuthService.hash_api_key(raw_key)
        h2 = AuthService.hash_api_key(raw_key)
        assert h1 == h2


# -----------------------------------------------------------------------
# JWT creation and decoding
# -----------------------------------------------------------------------


class TestJWTTokens:
    """JWT access, refresh, and reset token lifecycle."""

    def test_create_access_token(self) -> None:
        user_id = str(uuid.uuid4())
        token = AuthService.create_access_token(user_id, "Admin")
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        assert payload["sub"] == user_id
        assert payload["role"] == "Admin"
        assert payload["type"] == "access"

    def test_create_refresh_token(self) -> None:
        user_id = str(uuid.uuid4())
        token = AuthService.create_refresh_token(user_id)
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        assert payload["sub"] == user_id
        assert payload["type"] == "refresh"
        assert "role" not in payload

    def test_decode_token_access(self) -> None:
        user_id = str(uuid.uuid4())
        token = AuthService.create_access_token(user_id, "Operator")
        result = AuthService.decode_token(token)
        assert isinstance(result, TokenPayload)
        assert result.sub == user_id
        assert result.role == "Operator"
        assert result.type == "access"

    def test_decode_token_refresh(self) -> None:
        user_id = str(uuid.uuid4())
        token = AuthService.create_refresh_token(user_id)
        result = AuthService.decode_token(token)
        assert result.type == "refresh"
        assert result.sub == user_id

    def test_decode_invalid_token_raises(self) -> None:
        with pytest.raises(UnauthorizedError, match="Invalid or expired token"):
            AuthService.decode_token("not-a-valid-jwt-token")

    def test_decode_expired_token_raises(self) -> None:
        """Create a token that expired 1 hour ago."""
        now = datetime.now(timezone.utc)
        claims = {
            "sub": str(uuid.uuid4()),
            "role": "Admin",
            "type": "access",
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1),
        }
        expired_token = jwt.encode(
            claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(UnauthorizedError, match="Invalid or expired token"):
            AuthService.decode_token(expired_token)

    def test_create_reset_token(self) -> None:
        email = "user@example.com"
        token = AuthService.create_reset_token(email)
        result = AuthService.decode_token(token)
        assert result.sub == email
        assert result.type == "reset"

    def test_access_token_expiry_is_correct(self) -> None:
        user_id = str(uuid.uuid4())
        token = AuthService.create_access_token(user_id, "Admin")
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        iat = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        delta = exp - iat
        expected_minutes = settings.jwt_access_token_expire_minutes
        assert abs(delta.total_seconds() - expected_minutes * 60) < 2

    def test_refresh_token_expiry_is_correct(self) -> None:
        user_id = str(uuid.uuid4())
        token = AuthService.create_refresh_token(user_id)
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        iat = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        delta = exp - iat
        expected_days = settings.jwt_refresh_token_expire_days
        assert abs(delta.total_seconds() - expected_days * 86400) < 2


# -----------------------------------------------------------------------
# Failed login lockout logic
# -----------------------------------------------------------------------


def _make_user(**overrides: object) -> MagicMock:
    """Create a mock User object with sensible defaults for testing.

    Uses MagicMock to avoid SQLAlchemy instrumentation issues in unit tests.
    """
    defaults: dict[str, object] = {
        "user_id": uuid.uuid4(),
        "email": "test@vycescore.com",
        "password_hash": AuthService.hash_password("CorrectPassword1"),
        "full_name": "Test User",
        "role": UserRole.ADMIN,
        "is_active": True,
        "failed_login_attempts": 0,
        "locked_until": None,
        "last_login": None,
        "must_change_password": False,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    user = MagicMock(spec=User)
    for k, v in defaults.items():
        setattr(user, k, v)
    return user


def _mock_db_with_user(user: User | None) -> AsyncMock:
    """Return a mock AsyncSession that returns the given user on execute."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = user

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.flush = AsyncMock()
    return mock_db


class TestLoginLockout:
    """Failed login lockout after MAX_FAILED_ATTEMPTS consecutive failures."""

    @pytest.mark.asyncio
    async def test_successful_login_returns_tokens(self) -> None:
        user = _make_user()
        db = _mock_db_with_user(user)

        response = await AuthService.authenticate_user(db, "test@vycescore.com", "CorrectPassword1")

        assert response.access_token
        assert response.refresh_token
        assert response.token_type == "bearer"
        assert response.expires_in == settings.jwt_access_token_expire_minutes * 60

    @pytest.mark.asyncio
    async def test_successful_login_resets_failed_attempts(self) -> None:
        user = _make_user(failed_login_attempts=3)
        db = _mock_db_with_user(user)

        await AuthService.authenticate_user(db, "test@vycescore.com", "CorrectPassword1")

        assert user.failed_login_attempts == 0
        assert user.locked_until is None

    @pytest.mark.asyncio
    async def test_wrong_password_increments_failed_attempts(self) -> None:
        user = _make_user()
        db = _mock_db_with_user(user)

        with pytest.raises(UnauthorizedError, match="Invalid email or password"):
            await AuthService.authenticate_user(db, "test@vycescore.com", "WrongPassword1")

        assert user.failed_login_attempts == 1

    @pytest.mark.asyncio
    async def test_account_locks_after_max_failed_attempts(self) -> None:
        user = _make_user(failed_login_attempts=MAX_FAILED_ATTEMPTS - 1)
        db = _mock_db_with_user(user)

        with pytest.raises(UnauthorizedError, match="Invalid email or password"):
            await AuthService.authenticate_user(db, "test@vycescore.com", "WrongPassword1")

        assert user.failed_login_attempts == MAX_FAILED_ATTEMPTS
        assert user.locked_until is not None
        assert user.locked_until > datetime.now(timezone.utc)

    @pytest.mark.asyncio
    async def test_locked_account_raises_forbidden(self) -> None:
        user = _make_user(
            locked_until=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        db = _mock_db_with_user(user)

        with pytest.raises(ForbiddenError, match="temporarily locked"):
            await AuthService.authenticate_user(db, "test@vycescore.com", "CorrectPassword1")

    @pytest.mark.asyncio
    async def test_expired_lockout_allows_login(self) -> None:
        user = _make_user(
            locked_until=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db = _mock_db_with_user(user)

        response = await AuthService.authenticate_user(db, "test@vycescore.com", "CorrectPassword1")
        assert response.access_token

    @pytest.mark.asyncio
    async def test_unknown_email_raises_unauthorized(self) -> None:
        db = _mock_db_with_user(None)

        with pytest.raises(UnauthorizedError, match="Invalid email or password"):
            await AuthService.authenticate_user(db, "nobody@example.com", "AnyPassword1")

    @pytest.mark.asyncio
    async def test_inactive_user_raises_unauthorized(self) -> None:
        user = _make_user(is_active=False)
        db = _mock_db_with_user(user)

        with pytest.raises(UnauthorizedError, match="deactivated"):
            await AuthService.authenticate_user(db, "test@vycescore.com", "CorrectPassword1")

    @pytest.mark.asyncio
    async def test_successful_login_updates_last_login(self) -> None:
        user = _make_user()
        db = _mock_db_with_user(user)

        before = datetime.now(timezone.utc)
        await AuthService.authenticate_user(db, "test@vycescore.com", "CorrectPassword1")

        assert user.last_login is not None
        assert user.last_login >= before


# -----------------------------------------------------------------------
# Password reset
# -----------------------------------------------------------------------


class TestPasswordReset:
    """Password reset token creation and application."""

    @pytest.mark.asyncio
    async def test_reset_password_updates_hash(self) -> None:
        email = "reset@vycescore.com"
        user = _make_user(email=email, must_change_password=True, failed_login_attempts=3)
        db = _mock_db_with_user(user)
        old_hash = user.password_hash

        token = AuthService.create_reset_token(email)
        await AuthService.reset_password(db, token, "NewSecureP@ss1")

        assert user.password_hash != old_hash
        assert AuthService.verify_password("NewSecureP@ss1", user.password_hash)
        assert user.must_change_password is False
        assert user.failed_login_attempts == 0
        assert user.locked_until is None

    @pytest.mark.asyncio
    async def test_reset_with_access_token_raises(self) -> None:
        user_id = str(uuid.uuid4())
        access_token = AuthService.create_access_token(user_id, "Admin")

        db = _mock_db_with_user(None)
        with pytest.raises(UnauthorizedError, match="Invalid reset token"):
            await AuthService.reset_password(db, access_token, "NewPassword1")

    @pytest.mark.asyncio
    async def test_reset_with_unknown_email_raises(self) -> None:
        token = AuthService.create_reset_token("unknown@example.com")
        db = _mock_db_with_user(None)

        with pytest.raises(UnauthorizedError, match="Invalid reset token"):
            await AuthService.reset_password(db, token, "NewPassword1")
