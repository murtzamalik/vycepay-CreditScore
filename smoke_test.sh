#!/usr/bin/env bash
# ==============================================================================
# VyceScore API Smoke Test
# ==============================================================================
# Prerequisites:
#   1. Docker services running:  docker compose up -d
#   2. DB migrated:              cd backend && source .venv/Scripts/activate && PYTHONPATH=. alembic upgrade head
#   3. Test data seeded:         python seed_test_data.py
#   4. API server running:       PYTHONPATH=. uvicorn app.main:app --host 127.0.0.1 --port 8000
#
# Usage:  bash smoke_test.sh
# ==============================================================================

BASE_URL="http://127.0.0.1:8000"
API_KEY="vyc_test_smoke_key_12345678901234"
VALID_ID="12345678"
INVALID_ID="99999999"
PASSED=0
FAILED=0

# Colors (disabled if not a terminal)
if [ -t 1 ]; then
    GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
else
    GREEN=''; RED=''; YELLOW=''; NC=''
fi

# ── Helpers ──────────────────────────────────────────────────────────────────

assert_status() {
    local test_name="$1" expected="$2" actual="$3" body="$4"
    if [ "$actual" -eq "$expected" ]; then
        echo -e "  ${GREEN}PASS${NC}  $test_name  (HTTP $actual)"
        PASSED=$((PASSED + 1))
    else
        echo -e "  ${RED}FAIL${NC}  $test_name  (expected $expected, got $actual)"
        echo "        Response: $(echo "$body" | head -c 200)"
        FAILED=$((FAILED + 1))
    fi
}

assert_json() {
    local test_name="$1" expr="$2" expected="$3" body="$4"
    local actual
    actual=$(echo "$body" | python -c "import sys,json; print(json.load(sys.stdin)$expr)" 2>/dev/null)
    if [ "$actual" = "$expected" ]; then
        echo -e "  ${GREEN}PASS${NC}  $test_name"
        PASSED=$((PASSED + 1))
    else
        echo -e "  ${RED}FAIL${NC}  $test_name  (expected '$expected', got '$actual')"
        FAILED=$((FAILED + 1))
    fi
}

request() {
    local method="$1"; shift
    local url="$1"; shift
    local response
    response=$(curl -s -w "\n%{http_code}" "$@" -X "$method" "$url")
    HTTP_BODY=$(echo "$response" | sed '$d')
    HTTP_STATUS=$(echo "$response" | tail -1)
}

echo ""
echo -e "${YELLOW}============================================${NC}"
echo -e "${YELLOW}  VyceScore API Smoke Test${NC}"
echo -e "${YELLOW}============================================${NC}"
echo ""

# ── Pre-flight: check server is running ──────────────────────────────────────

request GET "$BASE_URL/v1/health"
if [ "$HTTP_STATUS" != "200" ]; then
    echo -e "${RED}ERROR: Server not reachable at $BASE_URL${NC}"
    echo "Start it with: cd backend && source .venv/Scripts/activate && PYTHONPATH=. uvicorn app.main:app --port 8000"
    exit 1
fi

# ==============================================================================
# 1. HEALTH CHECK
# ==============================================================================
echo -e "${YELLOW}[1] Health Check${NC}"

assert_status "GET /v1/health returns 200" 200 "$HTTP_STATUS" "$HTTP_BODY"
assert_json "status = healthy" "['status']" "healthy" "$HTTP_BODY"
assert_json "version = 0.1.0" "['version']" "0.1.0" "$HTTP_BODY"
echo ""

# ==============================================================================
# 2. AUTHENTICATION & AUTHORIZATION
# ==============================================================================
echo -e "${YELLOW}[2] Authentication${NC}"

# No API key
request GET "$BASE_URL/v1/scores/lite/$VALID_ID"
assert_status "No API key returns 401" 401 "$HTTP_STATUS" "$HTTP_BODY"

# Invalid API key
request GET "$BASE_URL/v1/scores/lite/$VALID_ID" -H "X-API-Key: vyc_totally_wrong_key"
assert_status "Invalid API key returns 401" 401 "$HTTP_STATUS" "$HTTP_BODY"

# Valid API key
request GET "$BASE_URL/v1/scores/lite/$VALID_ID" -H "X-API-Key: $API_KEY"
assert_status "Valid API key returns 200" 200 "$HTTP_STATUS" "$HTTP_BODY"
echo ""

# ==============================================================================
# 3. LITE SCORE API  (GET /v1/scores/lite/{national_id})
# ==============================================================================
echo -e "${YELLOW}[3] Lite Score API${NC}"

request GET "$BASE_URL/v1/scores/lite/$VALID_ID" -H "X-API-Key: $API_KEY"
assert_status "Lite score returns 200" 200 "$HTTP_STATUS" "$HTTP_BODY"
assert_json "vyce_score = 720" "['vyce_score']" "720" "$HTTP_BODY"
assert_json "niq_score = 75" "['niq_score']" "75" "$HTTP_BODY"
assert_json "score_version = v1.0.0" "['score_version']" "v1.0.0" "$HTTP_BODY"
assert_json "score_date present" "['score_date']" "2026-03-08" "$HTTP_BODY"

# Unknown subject
request GET "$BASE_URL/v1/scores/lite/$INVALID_ID" -H "X-API-Key: $API_KEY"
assert_status "Unknown subject returns 404" 404 "$HTTP_STATUS" "$HTTP_BODY"
assert_json "Error code = NOT_FOUND" "['error']['code']" "NOT_FOUND" "$HTTP_BODY"
echo ""

# ==============================================================================
# 4. PRO SCORE API  (GET /v1/scores/pro/{national_id})
# ==============================================================================
echo -e "${YELLOW}[4] Pro Score API${NC}"

request GET "$BASE_URL/v1/scores/pro/$VALID_ID" -H "X-API-Key: $API_KEY"
assert_status "Pro score returns 200" 200 "$HTTP_STATUS" "$HTTP_BODY"
assert_json "vyce_score = 720" "['vyce_score']" "720" "$HTTP_BODY"
assert_json "niq_score = 75" "['niq_score']" "75" "$HTTP_BODY"

# Risk drivers (SHAP explainability - Top 3)
assert_json "Driver #1 = Cross-Border Liquidity" "['risk_drivers'][0]['factor']" "Cross-Border Liquidity" "$HTTP_BODY"
assert_json "Driver #1 impact = positive" "['risk_drivers'][0]['impact']" "positive" "$HTTP_BODY"
assert_json "Driver #2 = Transaction Diversity" "['risk_drivers'][1]['factor']" "Transaction Diversity" "$HTTP_BODY"
assert_json "Driver #3 = Geographic Stability" "['risk_drivers'][2]['factor']" "Geographic Stability" "$HTTP_BODY"
assert_json "Driver #3 impact = negative" "['risk_drivers'][2]['impact']" "negative" "$HTTP_BODY"

driver_count=$(echo "$HTTP_BODY" | python -c "import sys,json; print(len(json.load(sys.stdin)['risk_drivers']))" 2>/dev/null)
if [ "$driver_count" = "3" ]; then
    echo -e "  ${GREEN}PASS${NC}  Returns exactly 3 risk drivers"
    PASSED=$((PASSED + 1))
else
    echo -e "  ${RED}FAIL${NC}  Expected 3 risk drivers, got $driver_count"
    FAILED=$((FAILED + 1))
fi

# Confidence interval
assert_json "Confidence lower = 680" "['confidence_interval']['lower']" "680" "$HTTP_BODY"
assert_json "Confidence upper = 760" "['confidence_interval']['upper']" "760" "$HTTP_BODY"

# Interpretation
assert_json "Risk level = Low Risk" "['interpretation']['risk_level']" "Low Risk" "$HTTP_BODY"
assert_json "Model version present" "['model_version']" "v1.0.0" "$HTTP_BODY"

# Unknown subject
request GET "$BASE_URL/v1/scores/pro/$INVALID_ID" -H "X-API-Key: $API_KEY"
assert_status "Unknown subject returns 404" 404 "$HTTP_STATUS" "$HTTP_BODY"
echo ""

# ==============================================================================
# 5. FEEDBACK API  (POST /v1/feedback/loan-outcome)
# ==============================================================================
echo -e "${YELLOW}[5] Feedback API${NC}"

# Valid feedback payload (schema requires: loan_id, subject_id, loan_amount,
# disbursement_date, outcome_date, days_past_due, is_default)
FEEDBACK_PAYLOAD=$(cat <<'ENDJSON'
{
    "loan_id": "LN-SMOKE-001",
    "subject_id": "12345678",
    "loan_amount": 50000.00,
    "disbursement_date": "2026-01-15",
    "outcome_date": "2026-03-01",
    "days_past_due": 0,
    "is_default": false
}
ENDJSON
)

request POST "$BASE_URL/v1/feedback/loan-outcome" \
    -H "X-API-Key: $API_KEY" \
    -H "Content-Type: application/json" \
    -d "$FEEDBACK_PAYLOAD"

if [ "$HTTP_STATUS" -ge 200 ] && [ "$HTTP_STATUS" -lt 300 ]; then
    echo -e "  ${GREEN}PASS${NC}  POST /v1/feedback/loan-outcome accepted  (HTTP $HTTP_STATUS)"
    PASSED=$((PASSED + 1))
else
    echo -e "  ${RED}FAIL${NC}  POST /v1/feedback/loan-outcome  (expected 2xx, got $HTTP_STATUS)"
    echo "        Response: $(echo "$HTTP_BODY" | head -c 300)"
    FAILED=$((FAILED + 1))
fi

# Missing required field
BAD_PAYLOAD='{"loan_id": "LN-BAD-001"}'
request POST "$BASE_URL/v1/feedback/loan-outcome" \
    -H "X-API-Key: $API_KEY" \
    -H "Content-Type: application/json" \
    -d "$BAD_PAYLOAD"
assert_status "Invalid feedback returns 422" 422 "$HTTP_STATUS" "$HTTP_BODY"
echo ""

# ==============================================================================
# 6. JWT-PROTECTED ENDPOINTS (KPIs, Data Rights, Admin)
# ==============================================================================
echo -e "${YELLOW}[6] JWT-Protected Endpoints (auth enforcement)${NC}"

# These endpoints require Bearer JWT, not API key.
# Verify they reject API-key-only requests with 401.

request GET "$BASE_URL/v1/kpis" -H "X-API-Key: $API_KEY"
assert_status "GET /v1/kpis rejects API key (needs JWT)" 401 "$HTTP_STATUS" "$HTTP_BODY"

request GET "$BASE_URL/v1/data-rights/access/$VALID_ID" -H "X-API-Key: $API_KEY"
assert_status "GET /v1/data-rights rejects API key (needs JWT)" 401 "$HTTP_STATUS" "$HTTP_BODY"

request GET "$BASE_URL/v1/admin/customers" -H "X-API-Key: $API_KEY"
assert_status "GET /v1/admin/customers rejects API key (needs JWT)" 401 "$HTTP_STATUS" "$HTTP_BODY"
echo ""

# ==============================================================================
# 7. RATE LIMIT HEADERS
# ==============================================================================
echo -e "${YELLOW}[7] Rate Limit Headers${NC}"

headers=$(curl -s -D - -o /dev/null -H "X-API-Key: $API_KEY" "$BASE_URL/v1/scores/lite/$VALID_ID")

if echo "$headers" | grep -qi "x-ratelimit-limit"; then
    echo -e "  ${GREEN}PASS${NC}  X-RateLimit-Limit header present"
    PASSED=$((PASSED + 1))
else
    echo -e "  ${RED}FAIL${NC}  X-RateLimit-Limit header missing"
    FAILED=$((FAILED + 1))
fi

if echo "$headers" | grep -qi "x-ratelimit-remaining"; then
    echo -e "  ${GREEN}PASS${NC}  X-RateLimit-Remaining header present"
    PASSED=$((PASSED + 1))
else
    echo -e "  ${RED}FAIL${NC}  X-RateLimit-Remaining header missing"
    FAILED=$((FAILED + 1))
fi

if echo "$headers" | grep -qi "x-correlation-id"; then
    echo -e "  ${GREEN}PASS${NC}  X-Correlation-Id header present"
    PASSED=$((PASSED + 1))
else
    echo -e "  ${RED}FAIL${NC}  X-Correlation-Id header missing"
    FAILED=$((FAILED + 1))
fi
echo ""

# ==============================================================================
# 8. OPENAPI / DOCS
# ==============================================================================
echo -e "${YELLOW}[8] API Documentation${NC}"

request GET "$BASE_URL/docs"
assert_status "Swagger UI available at /docs" 200 "$HTTP_STATUS" ""

request GET "$BASE_URL/openapi.json"
assert_status "OpenAPI spec at /openapi.json" 200 "$HTTP_STATUS" ""

endpoint_count=$(echo "$HTTP_BODY" | python -c "import sys,json; print(len(json.load(sys.stdin)['paths']))" 2>/dev/null)
if [ "$endpoint_count" -gt 10 ]; then
    echo -e "  ${GREEN}PASS${NC}  OpenAPI spec has $endpoint_count endpoints"
    PASSED=$((PASSED + 1))
else
    echo -e "  ${RED}FAIL${NC}  Expected >10 endpoints, got $endpoint_count"
    FAILED=$((FAILED + 1))
fi
echo ""

# ==============================================================================
# SUMMARY
# ==============================================================================
TOTAL=$((PASSED + FAILED))
echo -e "${YELLOW}============================================${NC}"
if [ "$FAILED" -eq 0 ]; then
    echo -e "  ${GREEN}ALL $TOTAL TESTS PASSED${NC}"
else
    echo -e "  Results: ${GREEN}$PASSED passed${NC}, ${RED}$FAILED failed${NC}, $TOTAL total"
fi
echo -e "${YELLOW}============================================${NC}"
echo ""

if [ "$FAILED" -gt 0 ]; then
    exit 1
fi
