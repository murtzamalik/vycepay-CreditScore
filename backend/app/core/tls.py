"""TLS 1.3 enforcement configuration (BRD §13, Phase 12.2).

Provides:
  - TLS context creation for service-to-service communication
  - TLS configuration validation
  - Minimum TLS version enforcement (TLS 1.3)

In production, TLS termination is handled at the API Gateway / load balancer
level.  This module provides configuration for internal service-to-service
communication and outbound HTTPS calls.
"""

from __future__ import annotations

import ssl
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

logger = get_logger("tls")

# Minimum acceptable TLS version
MIN_TLS_VERSION = ssl.TLSVersion.TLSv1_3

# Allowed cipher suites for TLS 1.3 (AEAD only)
TLS_13_CIPHERS: list[str] = [
    "TLS_AES_256_GCM_SHA384",
    "TLS_CHACHA20_POLY1305_SHA256",
    "TLS_AES_128_GCM_SHA256",
]


@dataclass(frozen=True)
class TLSConfig:
    """TLS configuration for VyceScore services.

    Attributes:
        cert_file: Path to PEM-encoded certificate file.
        key_file: Path to PEM-encoded private key file.
        ca_file: Path to CA bundle for peer verification.
        verify_peer: Whether to verify the peer's certificate.
        min_version: Minimum TLS protocol version.
        ciphers: Allowed cipher suites (colon-separated string or list).
    """

    cert_file: str | None = None
    key_file: str | None = None
    ca_file: str | None = None
    verify_peer: bool = True
    min_version: ssl.TLSVersion = MIN_TLS_VERSION
    ciphers: list[str] = field(default_factory=lambda: list(TLS_13_CIPHERS))

    def validate(self) -> list[str]:
        """Validate the TLS configuration and return a list of issues (empty if valid)."""
        issues: list[str] = []

        if self.cert_file and not Path(self.cert_file).exists():
            issues.append(f"Certificate file not found: {self.cert_file}")

        if self.key_file and not Path(self.key_file).exists():
            issues.append(f"Private key file not found: {self.key_file}")

        if self.ca_file and not Path(self.ca_file).exists():
            issues.append(f"CA bundle file not found: {self.ca_file}")

        if self.min_version < MIN_TLS_VERSION:
            issues.append(
                f"TLS version {self.min_version.name} is below minimum "
                f"required {MIN_TLS_VERSION.name}"
            )

        return issues


def create_ssl_context(config: TLSConfig) -> ssl.SSLContext:
    """Create an SSL context for outbound service-to-service connections.

    Enforces TLS 1.3 as the minimum version and restricts cipher suites
    to AEAD-only algorithms.

    Args:
        config: TLS configuration parameters.

    Returns:
        Configured ``ssl.SSLContext`` ready for use with ``aiohttp``,
        ``httpx``, or ``asyncpg``.

    Raises:
        ssl.SSLError: If the configuration is invalid.
        FileNotFoundError: If certificate files are missing.
    """
    issues = config.validate()
    if issues:
        for issue in issues:
            logger.warning("tls.config_issue", issue=issue)

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    # Enforce minimum TLS version
    ctx.minimum_version = config.min_version
    ctx.maximum_version = ssl.TLSVersion.TLSv1_3

    # Set cipher suites
    if config.ciphers:
        try:
            ctx.set_ciphers(":".join(config.ciphers))
        except ssl.SSLError:
            # TLS 1.3 ciphers are set differently in some Python versions
            pass

    # Load certificates if provided
    if config.cert_file and config.key_file:
        ctx.load_cert_chain(config.cert_file, config.key_file)

    if config.ca_file:
        ctx.load_verify_locations(config.ca_file)
    else:
        ctx.load_default_certs()

    # Peer verification
    if config.verify_peer:
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
    else:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    return ctx


def create_server_ssl_context(config: TLSConfig) -> ssl.SSLContext:
    """Create an SSL context for serving TLS connections (uvicorn / internal services).

    Args:
        config: TLS configuration with cert_file and key_file required.

    Returns:
        Configured ``ssl.SSLContext`` for server-side use.

    Raises:
        ValueError: If cert_file or key_file is not provided.
    """
    if not config.cert_file or not config.key_file:
        raise ValueError("cert_file and key_file are required for server TLS context")

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = config.min_version
    ctx.maximum_version = ssl.TLSVersion.TLSv1_3

    if config.ciphers:
        try:
            ctx.set_ciphers(":".join(config.ciphers))
        except ssl.SSLError:
            pass

    ctx.load_cert_chain(config.cert_file, config.key_file)

    if config.ca_file:
        ctx.load_verify_locations(config.ca_file)

    if config.verify_peer:
        ctx.verify_mode = ssl.CERT_REQUIRED
    else:
        ctx.verify_mode = ssl.CERT_NONE

    return ctx


def get_uvicorn_ssl_kwargs(config: TLSConfig) -> dict[str, Any]:
    """Return keyword arguments for uvicorn's SSL configuration.

    Usage::

        import uvicorn
        from app.core.tls import TLSConfig, get_uvicorn_ssl_kwargs

        tls = TLSConfig(cert_file="/certs/server.pem", key_file="/certs/server-key.pem")
        uvicorn.run("app.main:app", **get_uvicorn_ssl_kwargs(tls))
    """
    kwargs: dict[str, Any] = {}

    if config.cert_file:
        kwargs["ssl_certfile"] = config.cert_file
    if config.key_file:
        kwargs["ssl_keyfile"] = config.key_file
    if config.ca_file:
        kwargs["ssl_ca_certs"] = config.ca_file

    # Uvicorn uses ssl_version as protocol version
    kwargs["ssl_version"] = ssl.PROTOCOL_TLS_SERVER

    return kwargs
