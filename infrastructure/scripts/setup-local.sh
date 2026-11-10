#!/usr/bin/env bash
###############################################################################
# VyceScore — Local Development Environment Setup
# Sets up dependencies, Docker services, and validates configuration
###############################################################################

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
check_command() {
    if command -v "$1" &>/dev/null; then
        log_ok "$1 found: $(command -v "$1")"
        return 0
    else
        log_error "$1 not found. Please install it first."
        return 1
    fi
}

preflight() {
    log_info "Running pre-flight checks..."
    local failed=0

    check_command docker       || ((failed++))
    check_command docker-compose 2>/dev/null || check_command "docker compose" 2>/dev/null || {
        log_warn "docker-compose not found, will use 'docker compose'"
    }
    check_command kubectl      || ((failed++))
    check_command helm         || ((failed++))
    check_command terraform    || ((failed++))
    check_command python3      || check_command python || ((failed++))
    check_command node         || ((failed++))
    check_command aws          || log_warn "AWS CLI not found — needed for deployment only"

    if [[ $failed -gt 0 ]]; then
        log_error "$failed required tool(s) missing. Install them and re-run."
        exit 1
    fi
    echo ""
}

# ---------------------------------------------------------------------------
# Start local infrastructure (PostgreSQL + Redis)
# ---------------------------------------------------------------------------
start_local_services() {
    log_info "Starting local PostgreSQL and Redis..."

    docker network create vycescore-net 2>/dev/null || true

    # PostgreSQL
    if docker ps --format '{{.Names}}' | grep -q vycescore-postgres; then
        log_ok "PostgreSQL already running"
    else
        docker run -d \
            --name vycescore-postgres \
            --network vycescore-net \
            -e POSTGRES_USER=vycescore_admin \
            -e POSTGRES_PASSWORD=localdev123 \
            -e POSTGRES_DB=vycescore \
            -p 5432:5432 \
            --health-cmd "pg_isready -U vycescore_admin" \
            --health-interval 10s \
            --restart unless-stopped \
            postgres:15-alpine
        log_ok "PostgreSQL started on port 5432"
    fi

    # Redis
    if docker ps --format '{{.Names}}' | grep -q vycescore-redis; then
        log_ok "Redis already running"
    else
        docker run -d \
            --name vycescore-redis \
            --network vycescore-net \
            -p 6379:6379 \
            --health-cmd "redis-cli ping" \
            --health-interval 10s \
            --restart unless-stopped \
            redis:7-alpine
        log_ok "Redis started on port 6379"
    fi

    echo ""
}

# ---------------------------------------------------------------------------
# Set up Python virtual environment and install dependencies
# ---------------------------------------------------------------------------
setup_python() {
    log_info "Setting up Python environment..."

    PYTHON_CMD="python3"
    if ! command -v python3 &>/dev/null; then
        PYTHON_CMD="python"
    fi

    REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

    if [[ ! -d "$REPO_ROOT/.venv" ]]; then
        $PYTHON_CMD -m venv "$REPO_ROOT/.venv"
        log_ok "Virtual environment created at .venv/"
    else
        log_ok "Virtual environment already exists"
    fi

    source "$REPO_ROOT/.venv/bin/activate" 2>/dev/null || source "$REPO_ROOT/.venv/Scripts/activate" 2>/dev/null

    pip install --upgrade pip --quiet
    if [[ -f "$REPO_ROOT/requirements.txt" ]]; then
        pip install -r "$REPO_ROOT/requirements.txt" --quiet
        log_ok "Python dependencies installed"
    else
        log_warn "requirements.txt not found — skipping Python deps"
    fi

    if [[ -f "$REPO_ROOT/requirements-dev.txt" ]]; then
        pip install -r "$REPO_ROOT/requirements-dev.txt" --quiet
        log_ok "Dev dependencies installed"
    fi

    echo ""
}

# ---------------------------------------------------------------------------
# Set up frontend (Node.js)
# ---------------------------------------------------------------------------
setup_frontend() {
    log_info "Setting up frontend..."

    REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

    if [[ -d "$REPO_ROOT/frontend" && -f "$REPO_ROOT/frontend/package.json" ]]; then
        (cd "$REPO_ROOT/frontend" && npm ci --silent)
        log_ok "Frontend dependencies installed"
    else
        log_warn "frontend/ directory not found — skipping"
    fi

    echo ""
}

# ---------------------------------------------------------------------------
# Create .env file from template
# ---------------------------------------------------------------------------
setup_env_file() {
    log_info "Setting up environment file..."

    REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
    ENV_FILE="$REPO_ROOT/.env"

    if [[ -f "$ENV_FILE" ]]; then
        log_ok ".env file already exists"
    else
        cat > "$ENV_FILE" <<'ENVEOF'
# VyceScore — Local Development Environment Variables
# This file is for LOCAL DEVELOPMENT ONLY. Never commit to version control.

# Application
APP_NAME=vycescore
LOG_LEVEL=DEBUG
LOG_FORMAT=json
ENVIRONMENT=dev

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=vycescore
DB_USERNAME=vycescore_admin
DB_PASSWORD=localdev123
DB_POOL_SIZE=10

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_SSL=false

# API
API_HOST=0.0.0.0
API_PORT=8000
API_DOCS_ENABLED=true
CORS_ALLOWED_ORIGINS=http://localhost:3000

# Scoring
SCORE_MIN=300
SCORE_MAX=900
SCORE_CACHE_TTL_SECONDS=86400

# Secrets (use dummy values for local dev)
API_MASTER_KEY=dev-master-key-change-me
JWT_SECRET_KEY=dev-jwt-secret-change-me
ENVEOF
        log_ok ".env file created — review and update as needed"
    fi

    echo ""
}

# ---------------------------------------------------------------------------
# Wait for services to be healthy
# ---------------------------------------------------------------------------
wait_for_services() {
    log_info "Waiting for services to be healthy..."

    local retries=30
    local count=0

    # Wait for PostgreSQL
    while ! docker exec vycescore-postgres pg_isready -U vycescore_admin &>/dev/null; do
        ((count++))
        if [[ $count -ge $retries ]]; then
            log_error "PostgreSQL failed to start"
            exit 1
        fi
        sleep 1
    done
    log_ok "PostgreSQL is ready"

    # Wait for Redis
    count=0
    while ! docker exec vycescore-redis redis-cli ping &>/dev/null; do
        ((count++))
        if [[ $count -ge $retries ]]; then
            log_error "Redis failed to start"
            exit 1
        fi
        sleep 1
    done
    log_ok "Redis is ready"

    echo ""
}

# ---------------------------------------------------------------------------
# Print summary
# ---------------------------------------------------------------------------
print_summary() {
    echo ""
    echo "============================================================"
    log_ok "VyceScore local development environment is ready!"
    echo "============================================================"
    echo ""
    echo "  Services:"
    echo "    PostgreSQL:  localhost:5432 (user: vycescore_admin, db: vycescore)"
    echo "    Redis:       localhost:6379"
    echo ""
    echo "  Quick start:"
    echo "    source .venv/bin/activate     # Activate Python venv"
    echo "    uvicorn app.main:app --reload # Start API server"
    echo "    cd frontend && npm start      # Start Admin UI"
    echo ""
    echo "  Useful commands:"
    echo "    docker logs -f vycescore-postgres    # PostgreSQL logs"
    echo "    docker logs -f vycescore-redis       # Redis logs"
    echo "    docker stop vycescore-postgres vycescore-redis  # Stop services"
    echo ""
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    echo ""
    echo "============================================================"
    echo "  VyceScore — Local Development Setup"
    echo "============================================================"
    echo ""

    preflight
    start_local_services
    wait_for_services
    setup_python
    setup_frontend
    setup_env_file
    print_summary
}

main "$@"
