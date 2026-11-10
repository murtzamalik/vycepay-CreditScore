"""AES-256-GCM encryption for PII fields at rest (Kenya DPA 2019, BRD §13).

Provides:
  - AES-256-GCM encrypt / decrypt helpers
  - Key management interface (env var for dev, Vault integration point for prod)
  - SQLAlchemy custom type ``EncryptedString`` for transparent column encryption

Security invariants:
  - Encryption keys are NEVER logged or exposed in error messages.
  - Each ciphertext has a unique 12-byte nonce (GCM standard).
  - Key rotation is supported via versioned key identifiers.
"""

from __future__ import annotations

import base64
import os
import secrets
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import String, TypeDecorator

from app.core.logging import get_logger

logger = get_logger("encryption")

# ---------------------------------------------------------------------------
# Key management
# ---------------------------------------------------------------------------

_NONCE_SIZE = 12  # 96-bit nonce recommended for AES-GCM
_KEY_SIZE = 32  # 256 bits


class KeyProvider:
    """Abstract key provider interface.

    Subclass for Vault / KMS integration in production.
    """

    def get_key(self, key_id: str = "default") -> bytes:
        """Return the raw 256-bit encryption key for *key_id*."""
        raise NotImplementedError

    def get_current_key_id(self) -> str:
        """Return the active key identifier for new encryptions."""
        return "default"


class EnvKeyProvider(KeyProvider):
    """Load encryption keys from environment variables.

    Expected env var format: ``VYCESCORE_ENCRYPTION_KEY_<KEY_ID>`` containing
    a 64-character hex string (256 bits).

    For development convenience, if no env var is set, a deterministic key
    derived from ``VYCESCORE_ENCRYPTION_MASTER_KEY`` is used.
    """

    _ENV_PREFIX = "VYCESCORE_ENCRYPTION_KEY_"
    _MASTER_ENV = "VYCESCORE_ENCRYPTION_MASTER_KEY"

    def __init__(self) -> None:
        self._cache: dict[str, bytes] = {}

    def get_key(self, key_id: str = "default") -> bytes:
        if key_id in self._cache:
            return self._cache[key_id]

        env_name = f"{self._ENV_PREFIX}{key_id.upper()}"
        hex_key = os.environ.get(env_name)

        if hex_key is None:
            # Fallback to master key
            hex_key = os.environ.get(self._MASTER_ENV)

        if hex_key is None:
            raise EnvironmentError(
                f"Encryption key not configured. Set {env_name} or "
                f"{self._MASTER_ENV} environment variable (64-char hex string)."
            )

        if len(hex_key) != 64:
            raise ValueError(
                f"Encryption key must be exactly 64 hex characters (256 bits), "
                f"got {len(hex_key)}."
            )

        key_bytes = bytes.fromhex(hex_key)
        self._cache[key_id] = key_bytes
        return key_bytes


class VaultKeyProvider(KeyProvider):
    """Placeholder for HashiCorp Vault integration.

    In production, this would use the Vault Transit secrets engine
    or fetch data encryption keys from Vault's KV store.
    """

    def __init__(self, vault_addr: str, vault_token: str, mount_path: str = "transit") -> None:
        self._vault_addr = vault_addr
        self._vault_token = vault_token
        self._mount_path = mount_path

    def get_key(self, key_id: str = "default") -> bytes:
        # TODO: Implement Vault Transit or KV v2 key retrieval
        raise NotImplementedError(
            "VaultKeyProvider is a placeholder. Implement Vault API calls for production."
        )


# ---------------------------------------------------------------------------
# Module-level key provider singleton
# ---------------------------------------------------------------------------

_key_provider: KeyProvider | None = None


def configure_key_provider(provider: KeyProvider) -> None:
    """Set the global key provider instance."""
    global _key_provider
    _key_provider = provider


def get_key_provider() -> KeyProvider:
    """Return the global key provider, lazily initializing with EnvKeyProvider."""
    global _key_provider
    if _key_provider is None:
        _key_provider = EnvKeyProvider()
    return _key_provider


# ---------------------------------------------------------------------------
# AES-256-GCM encrypt / decrypt
# ---------------------------------------------------------------------------


def encrypt_value(plaintext: str, key_id: str | None = None) -> str:
    """Encrypt *plaintext* with AES-256-GCM.

    Returns a base64-encoded string in the format::

        <key_id>$<nonce_b64>$<ciphertext_b64>

    The key_id prefix supports key rotation — old ciphertexts can be
    decrypted with their original key while new data uses the current key.
    """
    provider = get_key_provider()
    kid = key_id or provider.get_current_key_id()
    key = provider.get_key(kid)

    nonce = secrets.token_bytes(_NONCE_SIZE)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)

    nonce_b64 = base64.urlsafe_b64encode(nonce).decode("ascii")
    ct_b64 = base64.urlsafe_b64encode(ciphertext).decode("ascii")

    return f"{kid}${nonce_b64}${ct_b64}"


def decrypt_value(encrypted: str) -> str:
    """Decrypt a value produced by :func:`encrypt_value`.

    Parses the ``<key_id>$<nonce_b64>$<ciphertext_b64>`` format and
    retrieves the corresponding key from the provider.
    """
    parts = encrypted.split("$", 2)
    if len(parts) != 3:
        raise ValueError("Invalid encrypted value format — expected key_id$nonce$ciphertext")

    kid, nonce_b64, ct_b64 = parts
    provider = get_key_provider()
    key = provider.get_key(kid)

    nonce = base64.urlsafe_b64decode(nonce_b64)
    ciphertext = base64.urlsafe_b64decode(ct_b64)

    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")


# ---------------------------------------------------------------------------
# SQLAlchemy custom type for encrypted columns
# ---------------------------------------------------------------------------


class EncryptedString(TypeDecorator):
    """SQLAlchemy column type that transparently encrypts/decrypts string values.

    Usage::

        class MyModel(Base):
            email = mapped_column(EncryptedString(length=512), nullable=False)

    Values are stored as ``key_id$nonce_b64$ciphertext_b64`` strings.
    The ``length`` parameter should accommodate the base64 expansion
    (roughly 1.5x plaintext length + overhead).
    """

    impl = String
    cache_ok = True

    def __init__(self, length: int = 512, **kwargs: Any) -> None:
        super().__init__(length=length, **kwargs)

    def process_bind_param(self, value: str | None, dialect: Any) -> str | None:
        """Encrypt on write."""
        if value is None:
            return None
        return encrypt_value(value)

    def process_result_value(self, value: str | None, dialect: Any) -> str | None:
        """Decrypt on read."""
        if value is None:
            return None
        try:
            return decrypt_value(value)
        except Exception:
            # If decryption fails (e.g. key rotation in progress), log and
            # return the raw value so the application can handle gracefully.
            logger.error(
                "encryption.decrypt_failed",
                hint="Check key provider configuration",
            )
            return value


def generate_encryption_key() -> str:
    """Generate a random 256-bit key as a 64-character hex string.

    Utility for key provisioning — output should be stored in a secrets
    manager, never in source code.
    """
    return secrets.token_hex(32)
