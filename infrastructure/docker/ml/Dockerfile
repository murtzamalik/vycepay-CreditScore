# ==============================================================================
# VyceScore ML Serving — Model inference image
# XGBoost/LightGBM with SHAP explainability
# ==============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Build dependencies
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        libgomp1 \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-ml.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements-ml.txt

# ---------------------------------------------------------------------------
# Stage 2: Production image
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS production

# Security: run as non-root
RUN groupadd --gid 1000 vycescore && \
    useradd --uid 1000 --gid vycescore --shell /bin/false --create-home vycescore

# Runtime dependencies for XGBoost/LightGBM
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libgomp1 \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

WORKDIR /app

# Create model cache directory
RUN mkdir -p /app/models /app/cache /tmp/shap_cache && \
    chown -R vycescore:vycescore /app /tmp/shap_cache

# Copy application code
COPY --chown=vycescore:vycescore . .

# Switch to non-root user
USER vycescore

# Environment for ML serving
ENV MODEL_DIR=/app/models
ENV SHAP_CACHE_DIR=/tmp/shap_cache
ENV OMP_NUM_THREADS=4
ENV PYTHONUNBUFFERED=1

# Expose inference port and metrics port
EXPOSE 8001 9090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

ENTRYPOINT ["python", "-m", "uvicorn"]
CMD ["app.ml_server:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2", "--log-level", "info"]
