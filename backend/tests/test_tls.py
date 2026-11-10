"""Tests for TLS 1.3 enforcement configuration (Phase 12.2).

Covers:
  - TLSConfig validation
  - SSL context creation
  - Minimum TLS version enforcement
  - Uvicorn SSL kwargs generation
"""

from __future__ import annotations

import ssl
import tempfile
from pathlib import Path

import pytest

from app.core.tls import (
    MIN_TLS_VERSION,
    TLS_13_CIPHERS,
    TLSConfig,
    create_ssl_context,
    create_server_ssl_context,
    get_uvicorn_ssl_kwargs,
)


class TestTLSConfig:
    """TLSConfig dataclass tests."""

    def test_default_config(self) -> None:
        config = TLSConfig()
        assert config.min_version == ssl.TLSVersion.TLSv1_3
        assert config.verify_peer is True
        assert config.cert_file is None
        assert config.key_file is None
        assert len(config.ciphers) > 0

    def test_validate_no_issues_for_defaults(self) -> None:
        config = TLSConfig()
        issues = config.validate()
        assert issues == []

    def test_validate_missing_cert_file(self) -> None:
        config = TLSConfig(cert_file="/nonexistent/cert.pem")
        issues = config.validate()
        assert any("Certificate file not found" in i for i in issues)

    def test_validate_missing_key_file(self) -> None:
        config = TLSConfig(key_file="/nonexistent/key.pem")
        issues = config.validate()
        assert any("Private key file not found" in i for i in issues)

    def test_validate_missing_ca_file(self) -> None:
        config = TLSConfig(ca_file="/nonexistent/ca.pem")
        issues = config.validate()
        assert any("CA bundle file not found" in i for i in issues)

    def test_validate_low_tls_version(self) -> None:
        config = TLSConfig(min_version=ssl.TLSVersion.TLSv1_2)
        issues = config.validate()
        assert any("below minimum" in i for i in issues)

    def test_frozen_dataclass(self) -> None:
        config = TLSConfig()
        with pytest.raises(AttributeError):
            config.min_version = ssl.TLSVersion.TLSv1_2  # type: ignore[misc]


class TestCreateSSLContext:
    """SSL context creation tests."""

    def test_creates_context_with_defaults(self) -> None:
        config = TLSConfig(verify_peer=False)
        ctx = create_ssl_context(config)
        assert isinstance(ctx, ssl.SSLContext)
        assert ctx.minimum_version == ssl.TLSVersion.TLSv1_3

    def test_verify_peer_disabled(self) -> None:
        config = TLSConfig(verify_peer=False)
        ctx = create_ssl_context(config)
        assert ctx.verify_mode == ssl.CERT_NONE


class TestServerSSLContext:
    """Server SSL context creation tests."""

    def test_requires_cert_and_key(self) -> None:
        config = TLSConfig()
        with pytest.raises(ValueError, match="cert_file and key_file are required"):
            create_server_ssl_context(config)


class TestUvicornSSLKwargs:
    """Uvicorn SSL configuration tests."""

    def test_returns_dict(self) -> None:
        config = TLSConfig()
        kwargs = get_uvicorn_ssl_kwargs(config)
        assert isinstance(kwargs, dict)
        assert "ssl_version" in kwargs

    def test_includes_cert_file(self) -> None:
        config = TLSConfig(cert_file="/certs/server.pem", key_file="/certs/key.pem")
        kwargs = get_uvicorn_ssl_kwargs(config)
        assert kwargs["ssl_certfile"] == "/certs/server.pem"
        assert kwargs["ssl_keyfile"] == "/certs/key.pem"

    def test_includes_ca_file(self) -> None:
        config = TLSConfig(ca_file="/certs/ca.pem")
        kwargs = get_uvicorn_ssl_kwargs(config)
        assert kwargs["ssl_ca_certs"] == "/certs/ca.pem"

    def test_no_cert_files_minimal_kwargs(self) -> None:
        config = TLSConfig()
        kwargs = get_uvicorn_ssl_kwargs(config)
        assert "ssl_certfile" not in kwargs
        assert "ssl_keyfile" not in kwargs


class TestMinimumTLSVersion:
    """Ensure TLS 1.3 is enforced as minimum."""

    def test_min_version_is_tls_13(self) -> None:
        assert MIN_TLS_VERSION == ssl.TLSVersion.TLSv1_3

    def test_cipher_suites_are_aead(self) -> None:
        for cipher in TLS_13_CIPHERS:
            assert "GCM" in cipher or "POLY1305" in cipher or "CCM" in cipher
