"""Structured logging setup with JSON output and correlation IDs using structlog."""

from __future__ import annotations

import logging
import uuid

import structlog


def generate_correlation_id() -> str:
    """Generate a unique correlation ID for request tracing."""
    return uuid.uuid4().hex


def setup_logging(log_level: str = "INFO", json_output: bool = True) -> None:
    """Configure structlog with JSON rendering for production, console for dev.

    Args:
        log_level: Python log level string (e.g. ``"INFO"``, ``"DEBUG"``).
        json_output: When ``True`` (default), render logs as JSON lines.
            Set to ``False`` for human-readable console output during local
            development.
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    if json_output:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level.upper())


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger, optionally named."""
    return structlog.get_logger(name)
