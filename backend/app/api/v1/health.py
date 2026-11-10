"""Health-check endpoint (re-export from endpoints package)."""

from app.api.v1.endpoints.health import router

__all__ = ["router"]
