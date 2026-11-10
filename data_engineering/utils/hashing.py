"""
PII hashing utility for VyceScore data pipelines.

Provides SHA-256 hashing with a configurable salt for anonymizing
personally identifiable information (PII) at data ingestion time.

Fields typically hashed:
    - national_id -> national_id_hash
    - phone_number -> phone_hash
    - full_name -> name_hash

The salt is configured via the VYCESCORE_PII_SALT environment variable
and must be consistent across all pipeline runs to ensure deterministic
hashing (required for entity resolution across datasets).

Compliance: Kenya Data Protection Act (DPA 2019) requires PII
anonymization after feature extraction. Raw PII is never persisted
beyond the staging layer.
"""

from __future__ import annotations

import hashlib
import os
from functools import lru_cache
from typing import Optional

# Default salt for development only -- production must override via env var.
_DEFAULT_DEV_SALT = "vycescore-dev-salt-DO-NOT-USE-IN-PROD"


@lru_cache(maxsize=1)
def _get_salt() -> str:
    """Retrieve the PII hashing salt from the environment.

    Returns:
        The configured salt string.

    Raises:
        ValueError: If no salt is configured and we are not in dev mode.
    """
    salt = os.getenv("VYCESCORE_PII_SALT")
    if salt is None:
        env = os.getenv("VYCESCORE_ENV", "development")
        if env != "development":
            raise ValueError(
                "VYCESCORE_PII_SALT environment variable must be set in "
                f"non-development environments (current: {env})"
            )
        salt = _DEFAULT_DEV_SALT
    return salt


def hash_pii(value: str, salt: Optional[str] = None) -> str:
    """Hash a PII value using SHA-256 with a salt.

    The hashing is deterministic: the same (value, salt) pair always
    produces the same hash. This allows entity resolution across
    datasets without exposing raw PII.

    Args:
        value: The raw PII string to hash (e.g., national ID number).
        salt: Optional salt override. If None, uses the configured
            VYCESCORE_PII_SALT environment variable.

    Returns:
        64-character lowercase hexadecimal SHA-256 digest.

    Raises:
        ValueError: If value is None or empty.

    Examples:
        >>> hash_pii("12345678", salt="test-salt")
        'a1b2c3...'  # deterministic 64-char hex string
    """
    if not value:
        raise ValueError("Cannot hash empty or None PII value")

    effective_salt = salt if salt is not None else _get_salt()
    salted = f"{effective_salt}{value}"
    return hashlib.sha256(salted.encode("utf-8")).hexdigest()


def hash_national_id(national_id: str, salt: Optional[str] = None) -> str:
    """Hash a Kenyan national ID number.

    Normalizes the national ID by stripping whitespace and converting
    to uppercase before hashing.

    Args:
        national_id: Raw national ID string.
        salt: Optional salt override.

    Returns:
        SHA-256 hash of the normalized national ID.
    """
    normalized = national_id.strip().upper()
    return hash_pii(normalized, salt=salt)


def hash_phone_number(phone: str, salt: Optional[str] = None) -> str:
    """Hash a phone number.

    Normalizes by removing spaces, dashes, and the leading '+' sign.
    Ensures the country code is included (defaults to 254 for Kenya).

    Args:
        phone: Raw phone number string.
        salt: Optional salt override.

    Returns:
        SHA-256 hash of the normalized phone number.
    """
    normalized = phone.strip().replace(" ", "").replace("-", "").replace("+", "")

    # Normalize Kenyan numbers: 07xx -> 2547xx
    if normalized.startswith("0") and len(normalized) == 10:
        normalized = f"254{normalized[1:]}"

    return hash_pii(normalized, salt=salt)


def hash_name(name: str, salt: Optional[str] = None) -> str:
    """Hash a person's name.

    Normalizes by stripping whitespace, converting to lowercase, and
    collapsing multiple spaces to single spaces.

    Args:
        name: Raw name string.
        salt: Optional salt override.

    Returns:
        SHA-256 hash of the normalized name.
    """
    normalized = " ".join(name.strip().lower().split())
    return hash_pii(normalized, salt=salt)


def verify_hash(value: str, expected_hash: str, salt: Optional[str] = None) -> bool:
    """Verify that a PII value matches an expected hash.

    Useful for validating entity linkage without exposing raw PII.

    Args:
        value: The raw PII value to check.
        expected_hash: The expected SHA-256 hash.
        salt: Optional salt override.

    Returns:
        True if the hash of value matches expected_hash.
    """
    computed = hash_pii(value, salt=salt)
    # Use constant-time comparison to prevent timing attacks
    return hashlib.compare_digest(computed, expected_hash)
