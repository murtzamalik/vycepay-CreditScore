"""National ID hashing utility (BRD §13.1.1, §13.1.2).

SHA-256 hash of national IDs ensures PII is never stored or logged in
plain text, satisfying Kenya DPA 2019 requirements.

IMPORTANT: Raw national IDs must NEVER be stored, logged, or returned
in API responses. Always use this function to produce the hash first.
"""

from __future__ import annotations

import hashlib


def hash_national_id(national_id: str) -> str:
    """Return the SHA-256 hex digest of a national ID.

    The input is stripped of whitespace and uppercased before hashing to
    ensure consistent hashes regardless of formatting differences.
    """
    normalised = national_id.strip().upper()
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()
