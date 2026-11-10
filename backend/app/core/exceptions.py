"""Custom exception classes and FastAPI exception handlers.

All error responses follow the standard format:
    {"error": {"code": "...", "message": "...", "details": {}}}
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.common import ErrorDetail, ErrorResponse


class VyceScoreError(Exception):
    """Base exception for all VyceScore application errors."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class NotFoundError(VyceScoreError):
    """Resource not found."""

    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(
            code="NOT_FOUND",
            message=f"{resource} with identifier '{identifier}' not found",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"resource": resource, "identifier": identifier},
        )


class UnauthorizedError(VyceScoreError):
    """Authentication required or failed."""

    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(
            code="UNAUTHORIZED",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ForbiddenError(VyceScoreError):
    """Insufficient permissions."""

    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(
            code="FORBIDDEN",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class RateLimitedError(VyceScoreError):
    """Rate limit exceeded."""

    def __init__(self) -> None:
        super().__init__(
            code="RATE_LIMITED",
            message="Too many requests",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )


def _build_error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorDetail(code=code, message=message, details=details or {})
    )
    return JSONResponse(status_code=status_code, content=body.model_dump())


async def vycescore_error_handler(request: Request, exc: VyceScoreError) -> JSONResponse:
    """Handle VyceScoreError subclasses."""
    return _build_error_response(exc.status_code, exc.code, exc.message, exc.details)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle Starlette/FastAPI HTTP exceptions in standard format."""
    return _build_error_response(
        status_code=exc.status_code,
        code="HTTP_ERROR",
        message=str(exc.detail),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors in standard format."""
    return _build_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code="VALIDATION_ERROR",
        message="Request validation failed",
        details={"errors": exc.errors()},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all custom exception handlers on the FastAPI app instance."""
    app.add_exception_handler(VyceScoreError, vycescore_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
