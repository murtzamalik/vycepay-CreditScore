"""Tests for TOTP-based MFA service (Phase 12.7).

Covers:
  - TOTP secret generation
  - TOTP URI generation for QR codes
  - TOTP code verification (valid/invalid/window)
  - Backup code generation and hashing
  - MFA setup flow
  - MFA verification flow
  - MFA disable flow
  - Role-based MFA requirement
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pyotp
import pytest

from app.models.user import User, UserRole
from app.schemas.mfa import (
    MFADisableRequest,
    MFASetupResponse,
    MFAStatusResponse,
    MFAVerifyRequest,
    MFAVerifyResponse,
)
from app.services.mfa_service import (
    BACKUP_CODE_COUNT,
    MFA_REQUIRED_ROLES,
    MFAService,
    TOTP_DIGITS,
    TOTP_INTERVAL,
    TOTP_ISSUER,
)


def _make_user(**overrides: object) -> MagicMock:
    """Create a mock User for MFA testing."""
    defaults = {
        "user_id": uuid.uuid4(),
        "email": "test@vycescore.com",
        "password_hash": "$2b$12$fake_hash",
        "full_name": "Test User",
        "role": UserRole.ADMIN,
        "is_active": True,
        "mfa_enabled": False,
        "mfa_secret": None,
        "mfa_backup_codes": None,
    }
    defaults.update(overrides)
    user = MagicMock(spec=User)
    for k, v in defaults.items():
        setattr(user, k, v)
    return user


class TestSecretGeneration:
    """TOTP secret generation tests."""

    def test_generates_base32_string(self) -> None:
        secret = MFAService.generate_secret()
        assert isinstance(secret, str)
        assert len(secret) == 32

    def test_generates_unique_secrets(self) -> None:
        s1 = MFAService.generate_secret()
        s2 = MFAService.generate_secret()
        assert s1 != s2


class TestTOTPUri:
    """TOTP provisioning URI tests."""

    def test_generates_otpauth_uri(self) -> None:
        secret = MFAService.generate_secret()
        uri = MFAService.get_totp_uri(secret, "user@example.com")
        assert uri.startswith("otpauth://totp/")
        assert "VyceScore" in uri
        assert "user%40example.com" in uri or "user@example.com" in uri

    def test_uri_contains_secret(self) -> None:
        secret = MFAService.generate_secret()
        uri = MFAService.get_totp_uri(secret, "user@example.com")
        assert f"secret={secret}" in uri


class TestTOTPVerification:
    """TOTP code verification tests."""

    def test_verify_valid_code(self) -> None:
        secret = MFAService.generate_secret()
        totp = pyotp.TOTP(secret, digits=TOTP_DIGITS, interval=TOTP_INTERVAL)
        code = totp.now()
        assert MFAService.verify_totp(secret, code) is True

    def test_verify_invalid_code(self) -> None:
        secret = MFAService.generate_secret()
        assert MFAService.verify_totp(secret, "000000") is False

    def test_verify_empty_code(self) -> None:
        secret = MFAService.generate_secret()
        assert MFAService.verify_totp(secret, "") is False


class TestBackupCodes:
    """Backup code generation and hashing tests."""

    def test_generates_correct_count(self) -> None:
        codes = MFAService.generate_backup_codes()
        assert len(codes) == BACKUP_CODE_COUNT

    def test_codes_are_formatted(self) -> None:
        codes = MFAService.generate_backup_codes()
        for code in codes:
            assert "-" in code
            parts = code.split("-")
            assert len(parts) == 2
            assert len(parts[0]) == 4
            assert len(parts[1]) == 4

    def test_codes_are_unique(self) -> None:
        codes = MFAService.generate_backup_codes()
        assert len(set(codes)) == len(codes)

    def test_hash_backup_code_deterministic(self) -> None:
        code = "ABCD-1234"
        h1 = MFAService.hash_backup_code(code)
        h2 = MFAService.hash_backup_code(code)
        assert h1 == h2
        assert len(h1) == 64

    def test_hash_normalizes_case_and_dashes(self) -> None:
        h1 = MFAService.hash_backup_code("ABCD-1234")
        h2 = MFAService.hash_backup_code("abcd-1234")
        h3 = MFAService.hash_backup_code("ABCD1234")
        assert h1 == h2
        assert h1 == h3


class TestMFASetup:
    """MFA setup flow tests."""

    @pytest.mark.asyncio
    async def test_setup_returns_secret_and_codes(self) -> None:
        user = _make_user()
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()

        result = await MFAService.setup_mfa(mock_db, user)

        assert "secret" in result
        assert "totp_uri" in result
        assert "backup_codes" in result
        assert len(result["backup_codes"]) == BACKUP_CODE_COUNT
        assert result["totp_uri"].startswith("otpauth://")

    @pytest.mark.asyncio
    async def test_setup_stores_secret_on_user(self) -> None:
        user = _make_user()
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()

        result = await MFAService.setup_mfa(mock_db, user)

        assert user.mfa_secret == result["secret"]
        assert user.mfa_enabled is False  # Not yet confirmed
        assert user.mfa_backup_codes is not None


class TestMFAConfirmSetup:
    """MFA setup confirmation tests."""

    @pytest.mark.asyncio
    async def test_confirm_with_valid_code(self) -> None:
        secret = MFAService.generate_secret()
        user = _make_user(mfa_secret=secret)
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()

        totp = pyotp.TOTP(secret, digits=TOTP_DIGITS, interval=TOTP_INTERVAL)
        code = totp.now()

        result = await MFAService.confirm_mfa_setup(mock_db, user, code)

        assert result is True
        assert user.mfa_enabled is True

    @pytest.mark.asyncio
    async def test_confirm_with_invalid_code_raises(self) -> None:
        secret = MFAService.generate_secret()
        user = _make_user(mfa_secret=secret)
        mock_db = AsyncMock()

        with pytest.raises(ValueError, match="Invalid TOTP code"):
            await MFAService.confirm_mfa_setup(mock_db, user, "000000")

    @pytest.mark.asyncio
    async def test_confirm_without_setup_raises(self) -> None:
        user = _make_user(mfa_secret=None)
        mock_db = AsyncMock()

        with pytest.raises(ValueError, match="not been initiated"):
            await MFAService.confirm_mfa_setup(mock_db, user, "123456")


class TestMFAVerify:
    """MFA verification during login tests."""

    @pytest.mark.asyncio
    async def test_verify_valid_totp(self) -> None:
        secret = MFAService.generate_secret()
        user = _make_user(mfa_secret=secret, mfa_enabled=True)
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()

        totp = pyotp.TOTP(secret, digits=TOTP_DIGITS, interval=TOTP_INTERVAL)
        code = totp.now()

        result = await MFAService.verify_mfa(mock_db, user, code)
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_invalid_code(self) -> None:
        secret = MFAService.generate_secret()
        user = _make_user(mfa_secret=secret, mfa_enabled=True, mfa_backup_codes=[])
        mock_db = AsyncMock()

        result = await MFAService.verify_mfa(mock_db, user, "000000")
        assert result is False

    @pytest.mark.asyncio
    async def test_verify_with_backup_code(self) -> None:
        secret = MFAService.generate_secret()
        backup_code = "ABCD-1234"
        hashed_code = MFAService.hash_backup_code(backup_code)
        user = _make_user(
            mfa_secret=secret,
            mfa_enabled=True,
            mfa_backup_codes=[hashed_code, "other_hash"],
        )
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()

        result = await MFAService.verify_mfa(mock_db, user, backup_code)

        assert result is True
        # Backup code should be consumed
        assert hashed_code not in user.mfa_backup_codes

    @pytest.mark.asyncio
    async def test_verify_no_secret_returns_false(self) -> None:
        user = _make_user(mfa_secret=None, mfa_enabled=True)
        mock_db = AsyncMock()

        result = await MFAService.verify_mfa(mock_db, user, "123456")
        assert result is False


class TestMFADisable:
    """MFA disable flow tests."""

    @pytest.mark.asyncio
    async def test_disable_clears_mfa_data(self) -> None:
        user = _make_user(
            mfa_enabled=True,
            mfa_secret="secret123",
            mfa_backup_codes=["hash1", "hash2"],
        )
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()

        await MFAService.disable_mfa(mock_db, user)

        assert user.mfa_enabled is False
        assert user.mfa_secret is None
        assert user.mfa_backup_codes is None


class TestMFARoleRequirement:
    """Role-based MFA requirement tests."""

    def test_admin_requires_mfa(self) -> None:
        assert MFAService.is_mfa_required(UserRole.ADMIN) is True

    def test_operator_requires_mfa(self) -> None:
        assert MFAService.is_mfa_required(UserRole.OPERATOR) is True

    def test_partner_does_not_require_mfa(self) -> None:
        assert MFAService.is_mfa_required(UserRole.PARTNER) is False

    def test_read_only_does_not_require_mfa(self) -> None:
        assert MFAService.is_mfa_required(UserRole.READ_ONLY) is False


class TestMFAEnabledCheck:
    """is_mfa_enabled method tests."""

    def test_enabled_user(self) -> None:
        user = _make_user(mfa_enabled=True)
        assert MFAService.is_mfa_enabled(user) is True

    def test_disabled_user(self) -> None:
        user = _make_user(mfa_enabled=False)
        assert MFAService.is_mfa_enabled(user) is False


class TestMFASchemas:
    """MFA schema validation tests."""

    def test_verify_request_valid(self) -> None:
        req = MFAVerifyRequest(code="123456")
        assert req.code == "123456"

    def test_verify_request_too_short(self) -> None:
        with pytest.raises(Exception):
            MFAVerifyRequest(code="12")  # min_length=4

    def test_disable_request_valid(self) -> None:
        req = MFADisableRequest(password="SecureP@ss1")
        assert req.password == "SecureP@ss1"

    def test_status_response(self) -> None:
        status = MFAStatusResponse(
            mfa_enabled=True,
            mfa_required=True,
            backup_codes_remaining=8,
        )
        assert status.mfa_enabled is True
        assert status.backup_codes_remaining == 8
