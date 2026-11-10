"""Re-export from app.config for backward compatibility."""

from app.config import Settings, get_settings

__all__ = ["Settings", "get_settings"]
