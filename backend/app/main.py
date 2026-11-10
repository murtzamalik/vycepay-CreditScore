"""FastAPI application factory with lifespan, CORS, structured logging, and routers."""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import v1_router
from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging, get_logger
from app.core.metrics import setup_prometheus
from app.core.middleware import (
    CorrelationIdMiddleware,
    RateLimitMiddleware,
    RequestLoggingMiddleware,
)
from app.services.kpi_scheduler import start_kpi_scheduler, stop_kpi_scheduler
from app.services.kyc_refresh_scheduler import (
    start_kyc_refresh_scheduler,
    stop_kyc_refresh_scheduler,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown logic."""
    json_output = settings.app_env != "development"
    setup_logging(settings.log_level, json_output=json_output)
    logger = get_logger("lifespan")
    await logger.ainfo("startup", app_name=settings.app_name, env=settings.app_env)

    # Start KPI scheduler
    start_kpi_scheduler()
    await logger.ainfo("kpi_scheduler_started")

    # Start KYC refresh scheduler
    start_kyc_refresh_scheduler()
    await logger.ainfo("kyc_refresh_scheduler_started")

    yield

    # Stop schedulers
    stop_kyc_refresh_scheduler()
    stop_kpi_scheduler()
    await logger.ainfo("shutdown")


def create_app() -> FastAPI:
    """Application factory — builds and returns the configured FastAPI instance."""
    application = FastAPI(
        title=settings.app_name,
        description="Credit scoring engine for financial institutions in Kenya and emerging markets",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ---- Exception handlers ----
    register_exception_handlers(application)

    # ---- Middleware (order matters: outermost first) ----
    application.add_middleware(CorrelationIdMiddleware)
    application.add_middleware(RequestLoggingMiddleware)
    application.add_middleware(RateLimitMiddleware, requests_per_minute=settings.rate_limit_lite)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---- Prometheus metrics ----
    setup_prometheus(application)

    # ---- Routers ----
    application.include_router(v1_router)

    return application


app = create_app()
