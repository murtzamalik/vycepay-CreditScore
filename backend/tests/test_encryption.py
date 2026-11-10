"""Tests for AES-256-GCM encryption service (Phase 12.1).

Covers:
  - Encryption and decryption round-trip
  - Different plaintext values produce different ciphertexts (unique nonces)
  - Invalid ciphertext format raises ValueError
  - Key provider configuration
  - EncryptedString SQLAlchemy type
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from app.core.encryption import (
    EncryptedString,
    EnvKeyProvider,
    KeyProvider,
    decrypt_value,
    encrypt_value,
    generate_encryption_key,
    configure_key_provider,
    get_key_provider,
)


# Test encryption key (64 hex chars = 256 bits)
TEST_KEY = "a" * 64
TEST_KEY_ENV_VAR = "VYCESCORE_ENCRYPTION_MASTER_KEY"


@pytest.fixture(autouse=True)
def _set_encryption_key() -> None:
    """Ensure a test encryption key is available."""
    os.environ[TEST_KEY_ENV_VAR] = TEST_KEY
    # Reset the provider so it picks up the new env var
    configure_key_provider(EnvKeyProvider())
    yield  # type: ignore[misc]
    os.environ.pop(TEST_KEY_ENV_VAR, None)


class TestEncryptDecrypt:
    """Encryption and decryption round-trip tests."""

    def test_encrypt_decrypt_roundtrip(self) -> None:
        plaintext = "Hello, VyceScore!"
        encrypted = encrypt_value(plaintext)
        decrypted = decrypt_value(encrypted)
        assert decrypted == plaintext

    def test_encrypt_produces_three_part_format(self) -> None:
        encrypted = encrypt_value("test")
        parts = encrypted.split("$")
        assert len(parts) == 3
        assert parts[0] == "default"  # key_id

    def test_different_plaintexts_different_ciphertexts(self) -> None:
        e1 = encrypt_value("plaintext1")
        e2 = encrypt_value("plaintext2")
        assert e1 != e2

    def test_same_plaintext_different_nonces(self) -> None:
        """Each encryption should use a unique nonce."""
        e1 = encrypt_value("same-value")
        e2 = encrypt_value("same-value")
        assert e1 != e2
        # But both decrypt to the same value
        assert decrypt_value(e1) == decrypt_value(e2)

    def test_empty_string_roundtrip(self) -> None:
        encrypted = encrypt_value("")
        assert decrypt_value(encrypted) == ""

    def test_unicode_roundtrip(self) -> None:
        plaintext = "Kenyan shilling: KES 1,000"
        encrypted = encrypt_value(plaintext)
        assert decrypt_value(encrypted) == plaintext

    def test_long_string_roundtrip(self) -> None:
        plaintext = "x" * 10000
        encrypted = encrypt_value(plaintext)
        assert decrypt_value(encrypted) == plaintext

    def test_invalid_format_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid encrypted value format"):
            decrypt_value("not-valid-format")

    def test_invalid_key_id_uses_fallback(self) -> None:
        """When a specific key ID is not found, the master key is used as fallback."""
        encrypted = encrypt_value("test")
        # Replace key_id with unknown one — since master key is set,
        # it falls back and decryption still works
        parts = encrypted.split("$", 2)
        bad_encrypted = f"unknown_key${parts[1]}${parts[2]}"
        # The EnvKeyProvider falls back to master key, so decryption
        # succeeds (same underlying key). In production with separate
        # keys per ID, this would fail.
        result = decrypt_value(bad_encrypted)
        assert result == "test"

    def test_truly_missing_key_raises(self) -> None:
        """When no master key and no specific key, decryption fails."""
        os.environ.pop(TEST_KEY_ENV_VAR, None)
        os.environ.pop("VYCESCORE_ENCRYPTION_KEY_DEFAULT", None)
        configure_key_provider(EnvKeyProvider())
        encrypted = "nonexistent$dGVzdA==$dGVzdA=="
        with pytest.raises(Exception):
            decrypt_value(encrypted)


class TestEnvKeyProvider:
    """EnvKeyProvider key management tests."""

    def test_get_key_returns_bytes(self) -> None:
        provider = EnvKeyProvider()
        key = provider.get_key("default")
        assert isinstance(key, bytes)
        assert len(key) == 32  # 256 bits

    def test_missing_key_raises(self) -> None:
        os.environ.pop(TEST_KEY_ENV_VAR, None)
        os.environ.pop("VYCESCORE_ENCRYPTION_KEY_DEFAULT", None)
        provider = EnvKeyProvider()
        with pytest.raises(EnvironmentError, match="Encryption key not configured"):
            provider.get_key("default")

    def test_invalid_key_length_raises(self) -> None:
        os.environ[TEST_KEY_ENV_VAR] = "too-short"
        provider = EnvKeyProvider()
        with pytest.raises(ValueError, match="64 hex characters"):
            provider.get_key("default")

    def test_specific_key_id_env_var(self) -> None:
        specific_key = "b" * 64
        os.environ["VYCESCORE_ENCRYPTION_KEY_V2"] = specific_key
        provider = EnvKeyProvider()
        key = provider.get_key("v2")
        assert key == bytes.fromhex(specific_key)
        os.environ.pop("VYCESCORE_ENCRYPTION_KEY_V2", None)

    def test_key_caching(self) -> None:
        provider = EnvKeyProvider()
        key1 = provider.get_key("default")
        key2 = provider.get_key("default")
        assert key1 is key2  # Same object from cache


class TestEncryptedStringType:
    """EncryptedString SQLAlchemy TypeDecorator tests."""

    def test_process_bind_param_encrypts(self) -> None:
        col_type = EncryptedString(length=512)
        result = col_type.process_bind_param("test-value", dialect=None)
        assert result is not None
        assert result != "test-value"
        assert "$" in result

    def test_process_bind_param_none(self) -> None:
        col_type = EncryptedString(length=512)
        result = col_type.process_bind_param(None, dialect=None)
        assert result is None

    def test_process_result_value_decrypts(self) -> None:
        col_type = EncryptedString(length=512)
        encrypted = encrypt_value("test-value")
        result = col_type.process_result_value(encrypted, dialect=None)
        assert result == "test-value"

    def test_process_result_value_none(self) -> None:
        col_type = EncryptedString(length=512)
        result = col_type.process_result_value(None, dialect=None)
        assert result is None


class TestGenerateEncryptionKey:
    """Key generation utility tests."""

    def test_generates_64_hex_chars(self) -> None:
        key = generate_encryption_key()
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)

    def test_generates_unique_keys(self) -> None:
        k1 = generate_encryption_key()
        k2 = generate_encryption_key()
        assert k1 != k2
