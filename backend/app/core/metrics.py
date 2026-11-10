"""Prometheus metrics instrumentation (Task 9.6).

Exposes application-level metrics via the prometheus_client library.
The ``/metrics`` endpoint is mounted directly on the FastAPI app (not behind
the v1 router) so that Prometheus can scrape it without authentication.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse
from fastapi.routing import APIRoute
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# ---------------------------------------------------------------------------
# Custom registry (avoids default process/platform collectors in tests)
# ---------------------------------------------------------------------------

REGISTRY = CollectorRegistry(auto_describe=True)

# ---------------------------------------------------------------------------
# Request metrics
# ---------------------------------------------------------------------------

REQUEST_COUNT = Counter(
    "vycescore_http_requests_total",
    "Total HTTP requests",
    labelnames=["method", "endpoint", "status"],
    registry=REGISTRY,
)

REQUEST_LATENCY = Histogram(
    "vycescore_http_request_duration_seconds",
    "HTTP request latency in seconds",
    labelnames=["method", "endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0),
    registry=REGISTRY,
)

ACTIVE_REQUESTS = Gauge(
    "vycescore_http_requests_in_progress",
    "Number of HTTP requests currently being processed",
    labelnames=["method"],
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Scoring / ML metrics
# ---------------------------------------------------------------------------

SCORE_GENERATION_COUNT = Counter(
    "vycescore_score_generations_total",
    "Total number of credit scores generated",
    labelnames=["tier", "cache_hit"],
    registry=REGISTRY,
)

MODEL_INFERENCE_LATENCY = Histogram(
    "vycescore_model_inference_duration_seconds",
    "Model inference latency in seconds",
    labelnames=["model_version"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0),
    registry=REGISTRY,
)

SHAP_COMPUTATION_LATENCY = Histogram(
    "vycescore_shap_computation_duration_seconds",
    "SHAP explanation computation latency in seconds",
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 1.5, 2.0, 5.0),
    registry=REGISTRY,
)

MODEL_INFERENCE_ERRORS = Counter(
    "vycescore_model_inference_errors_total",
    "Total model inference errors",
    labelnames=["model_version", "error_type"],
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Batch pipeline metrics
# ---------------------------------------------------------------------------

BATCH_PIPELINE_LAST_SUCCESS = Gauge(
    "vycescore_batch_pipeline_last_success_timestamp",
    "Unix timestamp of the last successful batch pipeline run",
    registry=REGISTRY,
)

BATCH_SCORES_PROCESSED = Counter(
    "vycescore_batch_scores_processed_total",
    "Total scores processed in batch runs",
    registry=REGISTRY,
)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


def _normalise_path(path: str) -> str:
    """Collapse dynamic path segments to reduce cardinality.

    e.g. /v1/scores/lite/12345678 -> /v1/scores/lite/{nationalId}
    """
    parts = path.strip("/").split("/")
    normalised: list[str] = []
    for i, part in enumerate(parts):
        # Heuristic: if a segment looks like a UUID or numeric ID, replace it
        if len(part) > 8 and not part.startswith("v"):
            normalised.append("{id}")
        else:
            normalised.append(part)
    return "/" + "/".join(normalised)


class PrometheusMiddleware:
    """ASGI middleware that records request metrics."""

    def __init__(self, app: object) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)  # type: ignore[union-attr]
            return

        method = scope.get("method", "GET")
        path = scope.get("path", "/")

        # Skip metrics endpoint itself to avoid recursion
        if path == "/metrics":
            await self.app(scope, receive, send)  # type: ignore[union-attr]
            return

        normalised = _normalise_path(path)
        ACTIVE_REQUESTS.labels(method=method).inc()
        start = time.perf_counter()

        status_code = 500  # default in case of unhandled error

        async def send_wrapper(message: dict) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)  # type: ignore[union-attr]
        finally:
            duration = time.perf_counter() - start
            ACTIVE_REQUESTS.labels(method=method).dec()
            REQUEST_COUNT.labels(
                method=method,
                endpoint=normalised,
                status=str(status_code),
            ).inc()
            REQUEST_LATENCY.labels(
                method=method,
                endpoint=normalised,
            ).observe(duration)


# ---------------------------------------------------------------------------
# /metrics endpoint
# ---------------------------------------------------------------------------


def metrics_endpoint(_request: Request) -> Response:
    """Expose Prometheus metrics in text exposition format."""
    body = generate_latest(REGISTRY)
    return Response(content=body, media_type=CONTENT_TYPE_LATEST)


def setup_prometheus(app: FastAPI) -> None:
    """Register Prometheus middleware and /metrics endpoint on the FastAPI app."""
    # Add middleware (outermost so it captures all requests)
    app.add_middleware(PrometheusMiddleware)  # type: ignore[arg-type]

    # Add /metrics route (unauthenticated, not behind /v1)
    app.add_api_route("/metrics", metrics_endpoint, methods=["GET"], include_in_schema=False)
