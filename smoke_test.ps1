# ==============================================================================
# VyceScore API Smoke Test (PowerShell)
# ==============================================================================
# Prerequisites:
#   1. Docker services running:  docker compose up -d
#   2. DB migrated:              alembic upgrade head
#   3. Test data seeded
#   4. API server running:       uvicorn app.main:app --host 127.0.0.1 --port 8000
#
# Usage:  .\smoke_test.ps1
# ==============================================================================

$BASE_URL = "http://127.0.0.1:8000"
$API_KEY = "vyc_test_smoke_key_12345678901234"
$VALID_ID = "12345678"
$INVALID_ID = "99999999"
$PASSED = 0
$FAILED = 0

# ── Helpers ──────────────────────────────────────────────────────────────────

function Write-Pass($msg) {
    Write-Host "  PASS  " -ForegroundColor Green -NoNewline
    Write-Host $msg
    $script:PASSED++
}

function Write-Fail($msg, $detail) {
    Write-Host "  FAIL  " -ForegroundColor Red -NoNewline
    Write-Host $msg
    if ($detail) { Write-Host "        $detail" -ForegroundColor DarkGray }
    $script:FAILED++
}

function Invoke-Api {
    param(
        [string]$Method = "GET",
        [string]$Url,
        [hashtable]$Headers = @{},
        [string]$Body
    )
    try {
        $params = @{
            Method = $Method
            Uri = $Url
            Headers = $Headers
            ErrorAction = "Stop"
            UseBasicParsing = $true
        }
        if ($Body) {
            $params.Body = $Body
            $params.ContentType = "application/json"
        }
        $response = Invoke-WebRequest @params
        return @{
            Status = [int]$response.StatusCode
            Body = $response.Content
        }
    }
    catch {
        $status = 0
        $body = ""
        if ($_.Exception.Response) {
            $status = [int]$_.Exception.Response.StatusCode
            try {
                $stream = $_.Exception.Response.GetResponseStream()
                $reader = New-Object System.IO.StreamReader($stream)
                $body = $reader.ReadToEnd()
                $reader.Close()
                $stream.Close()
            } catch {
                # PowerShell 7+ stores it differently
                if ($_.ErrorDetails -and $_.ErrorDetails.Message) {
                    $body = $_.ErrorDetails.Message
                }
            }
        }
        # PowerShell 7+ / newer Invoke-WebRequest
        if ($status -eq 0 -and $_.Exception.Response.StatusCode) {
            $status = [int]$_.Exception.Response.StatusCode.value__
        }
        if (-not $body -and $_.ErrorDetails -and $_.ErrorDetails.Message) {
            $body = $_.ErrorDetails.Message
        }
        return @{
            Status = $status
            Body = $body
        }
    }
}

function Get-JsonValue($json, $path) {
    try {
        $obj = $json | ConvertFrom-Json
        foreach ($key in $path) {
            if ($key -match '^\d+$') {
                $obj = $obj[[int]$key]
            } else {
                $obj = $obj.$key
            }
        }
        return [string]$obj
    } catch {
        return $null
    }
}

function Assert-Status($testName, $expected, $actual, $body) {
    if ($actual -eq $expected) {
        Write-Pass "$testName  (HTTP $actual)"
    } else {
        Write-Fail "$testName  (expected $expected, got $actual)" $body.Substring(0, [Math]::Min(200, $body.Length))
    }
}

function Assert-Json($testName, [string[]]$path, $expected, $body) {
    $actual = Get-JsonValue $body $path
    if ($actual -eq $expected) {
        Write-Pass $testName
    } else {
        Write-Fail "$testName  (expected '$expected', got '$actual')"
    }
}

# ==============================================================================

Write-Host ""
Write-Host "============================================" -ForegroundColor Yellow
Write-Host "  VyceScore API Smoke Test" -ForegroundColor Yellow
Write-Host "============================================" -ForegroundColor Yellow
Write-Host ""

# ── Pre-flight ───────────────────────────────────────────────────────────────

$r = Invoke-Api -Url "$BASE_URL/v1/health"
if ($r.Status -ne 200) {
    Write-Host "ERROR: Server not reachable at $BASE_URL" -ForegroundColor Red
    Write-Host "Start it with: uvicorn app.main:app --host 127.0.0.1 --port 8000"
    exit 1
}

# ==============================================================================
# 1. HEALTH CHECK
# ==============================================================================
Write-Host "[1] Health Check" -ForegroundColor Yellow

Assert-Status "GET /v1/health returns 200" 200 $r.Status $r.Body
Assert-Json "status = healthy" @("status") "healthy" $r.Body
Assert-Json "version = 0.1.0" @("version") "0.1.0" $r.Body
Write-Host ""

# ==============================================================================
# 2. AUTHENTICATION
# ==============================================================================
Write-Host "[2] Authentication" -ForegroundColor Yellow

$r = Invoke-Api -Url "$BASE_URL/v1/scores/lite/$VALID_ID"
Assert-Status "No API key returns 401" 401 $r.Status $r.Body

$r = Invoke-Api -Url "$BASE_URL/v1/scores/lite/$VALID_ID" -Headers @{"X-API-Key"="vyc_totally_wrong_key"}
Assert-Status "Invalid API key returns 401" 401 $r.Status $r.Body

$r = Invoke-Api -Url "$BASE_URL/v1/scores/lite/$VALID_ID" -Headers @{"X-API-Key"=$API_KEY}
Assert-Status "Valid API key returns 200" 200 $r.Status $r.Body
Write-Host ""

# ==============================================================================
# 3. LITE SCORE API
# ==============================================================================
Write-Host "[3] Lite Score API" -ForegroundColor Yellow

$r = Invoke-Api -Url "$BASE_URL/v1/scores/lite/$VALID_ID" -Headers @{"X-API-Key"=$API_KEY}
Assert-Status "Lite score returns 200" 200 $r.Status $r.Body
Assert-Json "vyce_score = 720" @("vyce_score") "720" $r.Body
Assert-Json "niq_score = 75" @("niq_score") "75" $r.Body
Assert-Json "score_version = v1.0.0" @("score_version") "v1.0.0" $r.Body
Assert-Json "score_date present" @("score_date") "2026-03-08" $r.Body

$r = Invoke-Api -Url "$BASE_URL/v1/scores/lite/$INVALID_ID" -Headers @{"X-API-Key"=$API_KEY}
Assert-Status "Unknown subject returns 404" 404 $r.Status $r.Body
Assert-Json "Error code = NOT_FOUND" @("error","code") "NOT_FOUND" $r.Body
Write-Host ""

# ==============================================================================
# 4. PRO SCORE API
# ==============================================================================
Write-Host "[4] Pro Score API" -ForegroundColor Yellow

$r = Invoke-Api -Url "$BASE_URL/v1/scores/pro/$VALID_ID" -Headers @{"X-API-Key"=$API_KEY}
Assert-Status "Pro score returns 200" 200 $r.Status $r.Body
Assert-Json "vyce_score = 720" @("vyce_score") "720" $r.Body
Assert-Json "niq_score = 75" @("niq_score") "75" $r.Body

# Risk drivers
Assert-Json "Driver #1 = Cross-Border Liquidity" @("risk_drivers","0","factor") "Cross-Border Liquidity" $r.Body
Assert-Json "Driver #1 impact = positive" @("risk_drivers","0","impact") "positive" $r.Body
Assert-Json "Driver #2 = Transaction Diversity" @("risk_drivers","1","factor") "Transaction Diversity" $r.Body
Assert-Json "Driver #3 = Geographic Stability" @("risk_drivers","2","factor") "Geographic Stability" $r.Body
Assert-Json "Driver #3 impact = negative" @("risk_drivers","2","impact") "negative" $r.Body

$driverCount = (($r.Body | ConvertFrom-Json).risk_drivers).Count
if ($driverCount -eq 3) {
    Write-Pass "Returns exactly 3 risk drivers"
} else {
    Write-Fail "Expected 3 risk drivers, got $driverCount"
}

# Confidence interval
Assert-Json "Confidence lower = 680" @("confidence_interval","lower") "680" $r.Body
Assert-Json "Confidence upper = 760" @("confidence_interval","upper") "760" $r.Body

# Interpretation
Assert-Json "Risk level = Low Risk" @("interpretation","risk_level") "Low Risk" $r.Body
Assert-Json "Model version present" @("model_version") "v1.0.0" $r.Body

$r = Invoke-Api -Url "$BASE_URL/v1/scores/pro/$INVALID_ID" -Headers @{"X-API-Key"=$API_KEY}
Assert-Status "Unknown subject returns 404" 404 $r.Status $r.Body
Write-Host ""

# ==============================================================================
# 5. FEEDBACK API
# ==============================================================================
Write-Host "[5] Feedback API" -ForegroundColor Yellow

$loanId = "LN-SMOKE-" + (Get-Random -Minimum 100000 -Maximum 999999)
$feedbackBody = @{
    loan_id = $loanId
    subject_id = "12345678"
    loan_amount = 50000.00
    disbursement_date = "2026-01-15"
    outcome_date = "2026-03-01"
    days_past_due = 0
    is_default = $false
} | ConvertTo-Json

$r = Invoke-Api -Method POST -Url "$BASE_URL/v1/feedback/loan-outcome" `
    -Headers @{"X-API-Key"=$API_KEY} -Body $feedbackBody

if ($r.Status -ge 200 -and $r.Status -lt 300) {
    Write-Pass "POST /v1/feedback/loan-outcome accepted  (HTTP $($r.Status))"
} else {
    Write-Fail "POST /v1/feedback/loan-outcome  (expected 2xx, got $($r.Status))" $r.Body
}

# Invalid payload
$r = Invoke-Api -Method POST -Url "$BASE_URL/v1/feedback/loan-outcome" `
    -Headers @{"X-API-Key"=$API_KEY} -Body '{"loan_id":"LN-BAD"}'
Assert-Status "Invalid feedback returns 422" 422 $r.Status $r.Body
Write-Host ""

# ==============================================================================
# 6. JWT-PROTECTED ENDPOINTS
# ==============================================================================
Write-Host "[6] JWT-Protected Endpoints (auth enforcement)" -ForegroundColor Yellow

$r = Invoke-Api -Url "$BASE_URL/v1/kpis" -Headers @{"X-API-Key"=$API_KEY}
Assert-Status "GET /v1/kpis rejects API key (needs JWT)" 401 $r.Status $r.Body

$r = Invoke-Api -Url "$BASE_URL/v1/data-rights/access/$VALID_ID" -Headers @{"X-API-Key"=$API_KEY}
Assert-Status "GET /v1/data-rights rejects API key (needs JWT)" 401 $r.Status $r.Body

$r = Invoke-Api -Url "$BASE_URL/v1/admin/customers" -Headers @{"X-API-Key"=$API_KEY}
Assert-Status "GET /v1/admin/customers rejects API key (needs JWT)" 401 $r.Status $r.Body
Write-Host ""

# ==============================================================================
# 7. RATE LIMIT HEADERS
# ==============================================================================
Write-Host "[7] Rate Limit Headers" -ForegroundColor Yellow

try {
    $resp = Invoke-WebRequest -Uri "$BASE_URL/v1/scores/lite/$VALID_ID" `
        -Headers @{"X-API-Key"=$API_KEY} -UseBasicParsing -ErrorAction Stop
    $hdrs = $resp.Headers

    if ($hdrs["X-RateLimit-Limit"]) { Write-Pass "X-RateLimit-Limit header present" }
    else { Write-Fail "X-RateLimit-Limit header missing" }

    if ($hdrs["X-RateLimit-Remaining"]) { Write-Pass "X-RateLimit-Remaining header present" }
    else { Write-Fail "X-RateLimit-Remaining header missing" }

    if ($hdrs["X-Correlation-Id"]) { Write-Pass "X-Correlation-Id header present" }
    else { Write-Fail "X-Correlation-Id header missing" }
} catch {
    Write-Fail "Could not check rate limit headers" $_.Exception.Message
}
Write-Host ""

# ==============================================================================
# 8. API DOCUMENTATION
# ==============================================================================
Write-Host "[8] API Documentation" -ForegroundColor Yellow

$r = Invoke-Api -Url "$BASE_URL/docs"
Assert-Status "Swagger UI available at /docs" 200 $r.Status ""

$r = Invoke-Api -Url "$BASE_URL/openapi.json"
Assert-Status "OpenAPI spec at /openapi.json" 200 $r.Status ""

$endpointCount = @(($r.Body | ConvertFrom-Json).paths.PSObject.Properties).Length
if ($endpointCount -gt 10) {
    Write-Pass "OpenAPI spec has $endpointCount endpoints"
} else {
    Write-Fail "Expected >10 endpoints, got $endpointCount"
}
Write-Host ""

# ==============================================================================
# SUMMARY
# ==============================================================================
$TOTAL = $PASSED + $FAILED
Write-Host "============================================" -ForegroundColor Yellow
if ($FAILED -eq 0) {
    Write-Host "  ALL $TOTAL TESTS PASSED" -ForegroundColor Green
} else {
    Write-Host -NoNewline "  Results: "
    Write-Host -NoNewline "$PASSED passed" -ForegroundColor Green
    Write-Host -NoNewline ", "
    Write-Host -NoNewline "$FAILED failed" -ForegroundColor Red
    Write-Host ", $TOTAL total"
}
Write-Host "============================================" -ForegroundColor Yellow
Write-Host ""

if ($FAILED -gt 0) { exit 1 }
