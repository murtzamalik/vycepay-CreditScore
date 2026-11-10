# VyceScore → VycePay: Score Retrieval Integration Guide

Oct 10, 2026 · @Iftikhar

## Overview

This guide explains how VycePay services retrieve credit scores from VyceScore over a REST API, for example to decide whether to offer a loan in the wallet app. It is for VycePay backend engineers.

It assumes the data push from the *VycePay → VyceScore Data Push Integration Guide* is already live: scores are built from the wallet data VycePay sends.

| What flows | Mechanism | Freshness |
| --- | --- | --- |
| VyceScore (300–900), NIQ Score, top 3 risk drivers | REST API over HTTPS | Scores refresh nightly; cached 24 h |

**Base URL.** All API paths in this guide are relative to `{BASE_URL}`, for example `{BASE_URL}/v1/scores/lite/{nationalId}`. Get the actual base URL for each environment (sandbox, staging, production) from the VyceScore team. Do not hard-code it; read it from configuration.

## Getting started

Before writing code, request the following from the VyceScore team for each environment. Store every secret in your secrets manager, never in source control or mobile app bundles.

| Item | Used for | Notes |
| --- | --- | --- |
| `BASE_URL` | All REST calls | One per environment (sandbox, staging, production) |
| API key | `X-API-Key` header on REST calls | Issued per environment; tied to a license tier (Lite, Pro or Deep Dive) |
| Sandbox test IDs | Testing | National IDs with known scores |

Recommended order of work:

1. Call `GET {BASE_URL}/v1/health` to confirm network access.
2. Fetch a Lite score for a sandbox test ID to confirm your API key works.
3. Build the Pro flow if you need the reasons behind a score.
4. Complete the go-live checklist at the end of this guide.

## Authentication and security

Every REST call must use HTTPS and carry your API key in the `X-API-Key` header. Calls without a key or with an unknown key are rejected with `401`.

```bash
curl -H "X-API-Key: $VYCESCORE_API_KEY" "$BASE_URL/v1/scores/lite/12345678"
```

**API keys**

- Call VyceScore only from VycePay backend services. Never embed the key in the mobile app or web front end.
- Your key's license tier decides which endpoints you can call. A Lite key gets `403 FORBIDDEN` on Pro endpoints.
- If a key leaks, contact the VyceScore team at once to revoke and reissue it.

**Request tracing.** You may send an `X-Correlation-ID` header with your own request ID. VyceScore echoes it back, or generates one if you omit it. Quote it when reporting problems.

**Raw IDs in the path.** The score endpoints take the raw national ID in the URL path over HTTPS; VyceScore hashes it on arrival and never logs or stores it in plain text. Do not log full score URLs on your side either.

## Retrieving scores

Use Lite for fast pre-screening (for example, deciding whether to show a loan offer in the wallet) and Pro when you need the reasons behind a score.

| Endpoint | Returns | Tiers | Target latency |
| --- | --- | --- | --- |
| `GET /v1/scores/lite/{nationalId}` | VyceScore + NIQ Score | Lite, Pro, Deep Dive | < 500 ms |
| `GET /v1/scores/pro/{nationalId}` | VyceScore + NIQ + top 3 risk drivers | Pro, Deep Dive | < 2 s |
| `POST /v1/scores/batch` | Lite results for up to 100 IDs | Lite, Pro, Deep Dive | — |
| `GET /v1/health` | Service status | No key needed | — |

Scores are recomputed nightly, so calling more than once a day for the same customer returns the same result. Cache responses on your side for up to 24 hours.

### Lite score

```bash
curl -H "X-API-Key: $VYCESCORE_API_KEY" "$BASE_URL/v1/scores/lite/12345678"
```

```json
{
  "vyce_score": 712,
  "niq_score": 64,
  "score_date": "2026-10-10",
  "score_version": "v1.3.0",
  "subject_id": "a41f9c...64 hex chars",
  "metadata": {
    "model_version": "v1.3.0",
    "feature_date": "2026-10-09",
    "data_quality": "high"
  }
}
```

`vyce_score` runs from 300 to 900 and `niq_score` from 0 to 100. `data_quality` is `high`, `medium` or `low`; treat a `low` score with caution, as the customer has little transaction history.

### Pro score

```bash
curl -H "X-API-Key: $VYCESCORE_API_KEY" "$BASE_URL/v1/scores/pro/12345678?includeHistory=true"
```

```json
{
  "vyce_score": 712,
  "niq_score": 64,
  "risk_drivers": [
    {"factor": "Transaction consistency", "impact": "positive", "description": "Steady monthly inflows over the last 12 months", "contribution": 42},
    {"factor": "Merchant diversity", "impact": "positive", "description": "Payments spread across many merchant categories", "contribution": 31},
    {"factor": "Location stability", "impact": "negative", "description": "Transactions from widely varying locations", "contribution": 27}
  ],
  "score_date": "2026-10-10",
  "model_version": "v1.3.0",
  "prediction_horizon": "12_months",
  "confidence_interval": {"lower": 690, "upper": 734},
  "interpretation": {"risk_level": "Low Risk", "interpretation": "Good creditworthiness"},
  "history": [
    {"vyce_score": 698, "niq_score": 61, "score_date": "2026-09-10", "model_version": "v1.3.0"}
  ]
}
```

`risk_drivers` holds one to three entries; `impact` is `positive` or `negative` and `contribution` is a percentage (0–100). Add `includeHistory=true` to get scores from the last 12 months. Values shown are illustrative.

**Score bands**

| VyceScore | `risk_level` | Interpretation |
| --- | --- | --- |
| 800–900 | Very Low Risk | Excellent creditworthiness |
| 700–799 | Low Risk | Good creditworthiness |
| 600–699 | Medium Risk | Fair creditworthiness |
| 500–599 | High Risk | Poor creditworthiness |
| 300–499 | Very High Risk | Very poor creditworthiness |

### Batch scoring

```bash
curl -X POST "$BASE_URL/v1/scores/batch" \
  -H "X-API-Key: $VYCESCORE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"national_ids": ["12345678", "23456789"]}'
```

```json
{
  "results": [ { "vyce_score": 712, "niq_score": 64, "...": "same shape as a Lite response" } ],
  "total": 1,
  "failed": 1
}
```

Send between 1 and 100 IDs per call. IDs that cannot be scored are counted in `failed` and left out of `results`. Match results back to your customers using `subject_id`, the unsalted SHA-256 of the upper-cased, trimmed national ID.

## Errors, rate limits and retries

Every error uses the same JSON body, so branch on `error.code`, not on the message text.

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Subject with identifier 'a41f9c0b2e7d...' not found",
    "details": {}
  }
}
```

| HTTP | `error.code` | Meaning | What to do |
| --- | --- | --- | --- |
| 401 | `MISSING_API_KEY`, `INVALID_API_KEY` | No key, or key not recognised | Check configuration; do not retry |
| 403 | `FORBIDDEN` | Key's tier does not include this endpoint | Use Lite, or ask for a tier upgrade |
| 404 | `NOT_FOUND` | No score yet for this national ID | Treat as "no score"; the customer may be new or have too little history |
| 422 | `VALIDATION_ERROR` | Malformed request, e.g. more than 100 IDs in a batch | Fix the request; `details.errors` lists the problems |
| 429 | `RATE_LIMITED` | Hourly limit reached | Wait for the number of seconds in `Retry-After` |
| 5xx | `HTTP_ERROR` or none | Temporary VyceScore problem | Retry with backoff |

**Rate limits.** Limits are counted per API key over a sliding one-hour window. Default limits are 1,000 requests per hour for Lite, 500 for Pro and 200 for Deep Dive; your contract may set different figures. One batch call counts as one request. Each response carries:

- `X-RateLimit-Limit`: your limit for the window
- `X-RateLimit-Remaining`: requests left
- `X-RateLimit-Reset`: Unix time when capacity frees up

**Retries.** Retry only `429` and `5xx` responses and network timeouts, up to 3 times with exponential backoff and jitter (for example 1 s, 2 s, 4 s). Set client timeouts of about 2 s for Lite and 5 s for Pro. If VyceScore stays unavailable, fall back to your own decision rules rather than blocking the customer journey.

## Compliance obligations

- **Consent.** Request a customer's score only when they have consented to credit scoring (for example, when they apply for a loan). Store the consent record and timestamp.
- **Explaining decisions (Kenya DPA 2019).** If a VycePay credit decision relies on a VyceScore, the customer is entitled to meaningful information about the logic. Use the Pro API's `risk_drivers` to give that explanation in plain language.
- **Encryption.** Use HTTPS for every call. Encrypt stored API responses at rest.
- **Retention.** Keep score responses only as long as your privacy notice and lending records require.
- **Audit.** VyceScore logs every API call against your API key in an immutable audit trail. Keep matching request logs on your side (with `X-Correlation-ID`, without raw IDs) to support reconciliation and regulator queries.

## Testing and go-live

Build and test against the sandbox environment first; the VyceScore team supplies sandbox test national IDs with known scores. Sign-off on every item below is required before production credentials are issued.

- [ ] Production `BASE_URL` and API key received and stored in the secrets manager
- [ ] `GET /v1/health` reachable from VycePay production servers
- [ ] Lite and Pro calls return the expected scores for the sandbox test IDs
- [ ] `401`, `403`, `404`, `422` and `429` handled as described in Errors, rate limits and retries
- [ ] Timeouts, retries and the fallback path tested with VyceScore unavailable
- [ ] Customer consent captured before any score request
- [ ] No raw national IDs or API keys in VycePay logs
- [ ] Contacts for incidents named on both sides

**Support.** Contact the VyceScore team through the channel agreed at onboarding. Include the environment, the `X-Correlation-ID`, the endpoint, and the time in UTC. Never send raw national IDs or API keys in support messages.
