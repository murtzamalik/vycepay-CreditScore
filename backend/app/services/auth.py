"""Backward-compatible re-export of AuthService.

New code should import from ``app.services.auth_service`` directly.
"""

from app.services.auth_service import AuthService  # noqa: F401

__all__ = ["AuthService"]
