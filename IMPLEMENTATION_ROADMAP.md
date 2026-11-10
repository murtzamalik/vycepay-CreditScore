# VyceScore Implementation Roadmap

> Derived from VyceScore BRD v1.0 (March 2026). Phases are dependency-ordered: each phase builds on the outputs of the previous one.

---

## Phase 0: Foundation & Local Dev Environment
**Duration:** 1 sprint | **Agents:** DevOpsEngineer, TechLead
**Goal:** Every developer can run the full stack locally.

| # | Task | BRD Ref | Depends On |
|---|------|---------|------------|
| 0.1 | Docker Compose for local dev (PostgreSQL 15, Redis 7, Kafka) | §7.5, §14.1.1 | — |
| 0.2 | Backend project skeleton: FastAPI app, health endpoint, structured logging | §7.2, §7.4 | — |
| 0.3 | Frontend project skeleton: Vite + React 18 + TS strict, dev proxy to backend | §7.3 | — |
| 0.4 | Git repository setup: branching strategy, PR templates, .gitignore | §14.2 | — |
| 0.5 | CI pipeline (GitHub Actions): lint, test, build for backend + frontend | §14.2.1 | 0.2, 0.3 |
| 0.6 | `.env.example` files and configuration management (Pydantic Settings) | §7.5 | 0.2 |

**Exit Criteria:** `docker compose up` starts all services; CI passes on a clean PR; health endpoint returns 200.

---

## Phase 1: Core Data Model & Database
**Duration:** 1 sprint | **Agents:** BackendEngineer, DataEngineer
**Goal:** All domain entities exist in PostgreSQL with migrations.

| # | Task | BRD Ref | Depends On |
|---|------|---------|------------|
| 1.1 | Subject entity (id, type, id_hash, kyc_status, aml_status, timestamps) | §11.1.1 | 0.2 |
| 1.2 | Customer entity (FI) with license tier, status, api_key_hash, quotas | §11.1.5 | 0.2 |
| 1.3 | Score entity with history support (vyce_score, niq_score, model_version, confidence interval) | §11.1.2 | 1.1 |
| 1.4 | RiskDriver entity (score_id FK, rank, factor, impact, SHAP value, description) | §11.1.3 | 1.3 |
| 1.5 | Feature entity (subject_id FK, feature_name, value, category, data_source, quality_score) | §11.1.4 | 1.1 |
| 1.6 | ApiRequestLog entity (customer_id FK, endpoint, response_status, response_time_ms, ip_hash) | §11.1.6 | 1.2 |
| 1.7 | Table partitioning: Score by month, Feature by month, ApiRequestLog by day | §11.4 | 1.3, 1.5, 1.6 |
| 1.8 | Alembic migration scripts for all entities | §11 | 1.1–1.7 |
| 1.9 | TimescaleDB hypertables for KPI snapshots (§10.5 schema) | §10.5 | 1.8 |

**Exit Criteria:** `alembic upgrade head` creates all tables; models pass unit tests; partitioning verified.

---

## Phase 2: Authentication & Authorization
**Duration:** 1 sprint | **Agents:** BackendEngineer, SecurityEngineer
**Goal:** Secure API access with API keys, JWT, and RBAC.

| # | Task | BRD Ref | Depends On |
|---|------|---------|------------|
| 2.1 | API key generation, hashing (SHA-256), and validation (`X-API-Key` header) | UC-AUTH-001, §9.1 | 1.2 |
| 2.2 | JWT access + refresh token creation and verification (15min / 7d expiry) | UC-AUTH-002, UC-AUTH-004 | 1.2 |
| 2.3 | Password hashing (bcrypt), login endpoint, failed attempt lockout (5 attempts) | UC-AUTH-002, §13.4.1 | 1.2 |
| 2.4 | RBAC middleware: Admin, Operator, Partner, Read-only role enforcement | UC-USER-003, §7.2.2 | 2.2 |
| 2.5 | Password reset flow (token with expiry, email link, session invalidation) | UC-AUTH-003 | 2.3 |
| 2.6 | Rate limiting middleware (tier-based: Lite 1000/hr, Pro 500/hr, Deep Dive 200/hr) | §9.9 | 2.1 |
| 2.7 | Rate limit response headers (X-RateLimit-Limit, Remaining, Reset, Window) | §9.9 | 2.6 |
| 2.8 | Audit logging for all auth events (login, logout, failed attempts, password changes) | §13.3.1 | 1.6, 2.3 |

**Exit Criteria:** API key auth works end-to-end; JWT login/refresh cycle works; rate limiting returns correct headers; unauthorized requests get 401/403.

---

## Phase 3: Scoring APIs (Lite + Pro)
**Duration:** 1-2 sprints | **Agents:** BackendEngineer, DataScientist
**Goal:** Core scoring endpoints are live with cache and explainability.

| # | Task | BRD Ref | Depends On |
|---|------|---------|------------|
| 3.1 | `GET /v1/scores/lite/{nationalId}` — returns VyceScore + NIQ + metadata | §9.2.1, UC-SCORE-001 | 2.1 |
| 3.2 | `GET /v1/scores/pro/{nationalId}` — returns score + top 3 risk drivers + confidence interval | §9.3.1, UC-SCORE-002 | 3.1 |
| 3.3 | License tier validation (Pro endpoint requires Pro/DeepDive license) | §9.3.1 | 2.4, 3.2 |
| 3.4 | Redis score cache with 24h TTL; cache-hit returns instantly, cache-miss triggers inference | §6.2.2 | 3.1 |
| 3.5 | National ID hashing (SHA-256) — never store or log raw national IDs | §13.1.1, §13.1.2 | 3.1 |
| 3.6 | Pydantic response schemas: ScoreLiteResponse, ScoreProResponse (§9.2, §9.3 format) | §9.2.1, §9.3.1 | 3.1 |
| 3.7 | Standard error response format: `{"error": {"code": "...", "message": "...", "details": {}}}` | §9.8 | 3.1 |
| 3.8 | Audit logging for all score requests (§11.1.6 schema) | §13.3.1 | 1.6, 3.1 |
| 3.9 | `includeHistory` query parameter for Pro API | §9.3.1 | 3.2 |
| 3.10 | Score interpretation metadata (risk level label based on score range table §4.3) | §4.3 | 3.6 |

**Exit Criteria:** Lite API returns score <500ms (from cache); Pro API returns score + 3 risk drivers <2s; 404 for unknown subjects; correct error format on all failures.

---

## Phase 4: ML Model — Training & Serving (VOD Phase 1)
**Duration:** 2 sprints | **Agents:** DataScientist, DataEngineer
**Goal:** XGBoost model trained on VOD proxy labels, served for real-time inference.

| # | Task | BRD Ref | Depends On |
|---|------|---------|------------|
| 4.1 | VOD signal calculation: GOS Index Volatility, CBLRI Drop, Tx Pattern Breakdown | §12.2.1, §12.2.2 | — |
| 4.2 | VOD label assignment: flag users exhibiting distress signals | §12.2.1 | 4.1 |
| 4.3 | Feature engineering: implement all transaction features (§11.3.1) | §11.3.1 | — |
| 4.4 | Feature engineering: implement network features (§11.3.2) | §11.3.2 | — |
| 4.5 | Feature engineering: implement supply chain features (§11.3.3) | §11.3.3 | — |
| 4.6 | Feature engineering: implement compliance features (§11.3.4) | §11.3.4 | — |
| 4.7 | Six core features: CBLRI, UTDI, SCFV, DDC Ratio, NIQ Score, GOS Index | §4.2.1 | 4.3–4.6 |
| 4.8 | XGBoost training pipeline with BRD hyperparameters (§12.1.2) | §12.1.1, §12.1.2 | 4.2, 4.7 |
| 4.9 | MLflow experiment tracking (params, metrics, model artifacts) | §12.5.1 | 4.8 |
| 4.10 | Model evaluation: AUC-ROC, Precision@1000, Calibration Error, fairness checks | §12.3.3 | 4.8 |
| 4.11 | SHAP explainability: TreeExplainer, top 3 risk driver selection with contribution % | §12.4.1, §12.4.2 | 4.8 |
| 4.12 | Score conversion: `vyceScore = 300 + (1 - probability) * 600` | §12.1.1 | 4.8 |
| 4.13 | Model serving endpoint (BentoML or FastAPI wrapper) connected to Scoring Service | §12.6 | 4.8, 3.1 |
| 4.14 | Model card documentation for v1 model | §12.5.1 | 4.10 |

**Exit Criteria:** Model AUC-ROC > 0.75 on holdout set; SHAP produces coherent top-3 drivers; model registered in MLflow; scoring service calls model and returns real scores.

---

## Phase 5: Data Pipelines & Feature Store
**Duration:** 2 sprints | **Agents:** DataEngineer, DataScientist
**Goal:** Automated daily data ingestion, feature computation, and score refresh.

| # | Task | BRD Ref | Depends On |
|---|------|---------|------------|
| 5.1 | Feast feature store: entity definitions (customer), feature views (6 core + transaction features) | §12.6, §11.3 | 4.7 |
| 5.2 | Feast online store (Redis) + offline store (S3/Parquet) configuration | §12.6 | 5.1 |
| 5.3 | VycePay ingestion DAG: extract FT/IBFT, remittance, merchant data (T-1) | §5.1, §6.2.1 | 0.1 |
| 5.4 | VyceTrade ingestion DAG: extract supplier payments, invoices, supply chain links | §5.2, §6.2.1 | 0.1 |
| 5.5 | Data quality validation (Great Expectations): completeness, ranges, uniqueness, formats | §10.3.1 | 5.3, 5.4 |
| 5.6 | PySpark feature engineering job: compute all features from raw data | §6.2.1 step 5 | 5.3, 5.4, 4.7 |
| 5.7 | Daily scoring DAG (02:00 UTC): extract → validate → feature eng → inference → cache refresh → KPI reports | §6.2.1 | 5.3–5.6, 4.13 |
| 5.8 | Feature freshness monitoring (target: < 48h) | §10.3.2 | 5.7 |
| 5.9 | Data retention automation: PII anonymization after feature extraction, 10-year retention | §5.5, §13.1.2 | 5.3 |
| 5.10 | Kafka consumer for VycePay real-time critical events | §5.4 | 0.1 |

**Exit Criteria:** Daily DAG runs end-to-end on schedule; features in Feast serve to scoring service; data quality checks pass >95%; cache refreshed with latest scores.

---

## Phase 6: Batch Processing & Feedback APIs
**Duration:** 1 sprint | **Agents:** BackendEngineer, DataEngineer
**Goal:** Batch scoring for partner uploads and feedback loop for model improvement.

| # | Task | BRD Ref | Depends On |
|---|------|---------|------------|
| 6.1 | `POST /v1/batches` — accept CSV/JSON file (≤10MB), validate format, queue job | §9.5.1, UC-SCORE-003 | 3.1 |
| 6.2 | `GET /v1/batches/{batchId}` — return job status (queued/processing/completed/failed) | §9.5.2 | 6.1 |
| 6.3 | Background batch processor: chunk (100 records), bulk feature fetch, parallel inference | §6.2.3 | 6.1, 4.13 |
| 6.4 | Batch result file generation (CSV/JSON) and download endpoint | §6.2.3 | 6.3 |
| 6.5 | Batch completion notification (webhook callback) | §6.2.3 | 6.4 |
| 6.6 | `POST /v1/feedback/loan-outcome` — submit loan performance data | §9.6.1, UC-FDBK-001 | 2.1 |
| 6.7 | Feedback validation: loan reference exists, DPD value, dedup by loan ID (409 on conflict) | §9.6.1 | 6.6 |
| 6.8 | Ground truth label storage in training pool | §12.2.3 | 6.7 |
| 6.9 | Retraining trigger evaluation (1000+ new labels OR AUC-ROC < 0.72) | §12.3.2, UC-FDBK-002 | 6.8 |

**Exit Criteria:** Partner can upload a batch file and receive scored results; feedback endpoint stores labels; retraining trigger fires when conditions met.

---

## Phase 7: Customer & User Management (Admin APIs)
**Duration:** 1 sprint | **Agents:** BackendEngineer
**Goal:** Full customer lifecycle management through admin APIs.

| # | Task | BRD Ref | Depends On |
|---|------|---------|------------|
| 7.1 | `POST /v1/admin/customers` — onboard new FI (generate API key pair, set tier) | UC-CUST-001 | 2.1, 2.4 |
| 7.2 | `GET /v1/admin/customers` — list with filtering (status, tier) and pagination | §9.7.1 | 7.1 |
| 7.3 | `PUT /v1/admin/customers/{id}/license` — update tier, query limit, enabled features | §9.7.2, UC-CUST-002 | 7.1 |
| 7.4 | `POST /v1/admin/customers/{id}/activate` — activate production access | UC-CUST-003 | 7.1 |
| 7.5 | Sandbox vs. production environment flag per customer | UC-CUST-003 | 7.1 |
| 7.6 | `POST /v1/admin/users` — create admin user with temp password + welcome email | UC-USER-001 | 2.3 |
| 7.7 | `PUT /v1/admin/users/{id}` — update user role, deactivate (revoke sessions) | UC-USER-002, UC-USER-003 | 7.6 |
| 7.8 | Usage tracking: count API calls per customer per month against quota | §7.2.7 | 1.6, 2.6 |
| 7.9 | Quota enforcement: block requests when monthly limit exceeded (return error §9.8) | §7.2.7 | 7.8 |

**Exit Criteria:** Full customer onboarding → API key → sandbox → production activation flow works; users can be created and role-managed; quota enforcement blocks over-limit requests.

---

## Phase 8: Admin Portal (Frontend)
**Duration:** 2 sprints | **Agents:** FrontendEngineer
**Goal:** Functional admin UI for system management and monitoring.

| # | Task | BRD Ref | Depends On |
|---|------|---------|------------|
| 8.1 | Login page with email/password, failed attempt handling, MFA placeholder | UC-AUTH-002, §7.3.1 | 2.2, 2.3 |
| 8.2 | App shell: sidebar navigation (role-based menu), header with user info | §7.3.1 | 8.1 |
| 8.3 | Route guards: AuthGuard (redirect if unauthenticated), RoleGuard (check RBAC) | §7.3.1 | 8.1 |
| 8.4 | Customer management page: list, onboard, configure license, activate | UC-CUST-001–003 | 7.1–7.5 |
| 8.5 | User management page: create, edit role, deactivate | UC-USER-001–003 | 7.6–7.7 |
| 8.6 | Score lookup page: search by national ID, display Lite/Pro score with gauge chart | UC-SCORE-001–002 | 3.1, 3.2 |
| 8.7 | Score detail view: score gauge (300-900), NIQ, risk drivers list, score history chart | §9.3.1 | 8.6 |
| 8.8 | KPI dashboard: model performance (AUC-ROC trend), query volume, data quality | UC-MON-001, §10 | 1.9 |
| 8.9 | Audit log viewer: search by date/user/action, pagination, detail view, CSV/PDF export | UC-MON-002 | 1.6 |
| 8.10 | White-label theming support: per-partner colors, logo, fonts via MUI theme provider | §7.3.2 | 8.2 |

**Exit Criteria:** Admin can log in, manage customers/users, look up scores, view KPI dashboards, and search audit logs. Role-based access restricts views appropriately.

---

## Phase 9: KPIs, Monitoring & Observability
**Duration:** 1 sprint | **Agents:** DevOpsEngineer, BackendEngineer
**Goal:** All BRD-defined KPIs computed on schedule; production monitoring in place.

| # | Task | BRD Ref | Depends On |
|---|------|---------|------------|
| 9.1 | KPI snapshot storage: TimescaleDB schema (§10.5 format) with 10-year retention | §10.5 | 1.9 |
| 9.2 | Hourly KPIs (:05 past hour): P95 response time (Lite/Pro), error rate | §10.4.1, §10.4.3 | 9.1, 1.6 |
| 9.3 | Daily KPIs (03:00 UTC): AUC-ROC, daily query volume, data completeness, feature freshness | §10.1.1, §10.2.1, §10.3 | 9.1, 4.10, 5.7 |
| 9.4 | Weekly KPIs (Mon 04:00 UTC): Precision@K, Calibration Error | §10.1.2, §10.1.3 | 9.1, 4.10 |
| 9.5 | Monthly KPIs (1st 05:00 UTC): system availability, adoption rate, ARPU | §10.4.2, §10.2.2, §10.2.3 | 9.1, 7.8 |
| 9.6 | Prometheus metrics: request rate, error rate, latency per endpoint (RED method) | §14.3.1 | 0.2 |
| 9.7 | Grafana dashboards: API health, model performance, data pipeline status | §14.3.1 | 9.6 |
| 9.8 | Alerting rules: error rate >1% (critical), latency SLO breach, AUC-ROC <0.72, pod crashes | §14.3.2 | 9.7 |
| 9.9 | Distributed tracing with Jaeger (correlation IDs across services) | §7.5 | 0.2 |
| 9.10 | ELK/Loki logging pipeline for structured logs | §7.5 | 0.2 |

**Exit Criteria:** All 13 BRD KPIs computed on their defined schedules; Grafana dashboards show live metrics; critical alerts fire correctly.

---

## Phase 10: Active Learning & Model Lifecycle
**Duration:** 1-2 sprints | **Agents:** DataScientist, DataEngineer
**Goal:** Automated model retraining from production feedback with safe deployment.

| # | Task | BRD Ref | Depends On |
|---|------|---------|------------|
| 10.1 | Ground truth integration: Phase 2 training with partner bank loan outcomes | §12.2.3 | 6.8 |
| 10.2 | Automated retraining pipeline: assemble training data → train → evaluate → register | §12.3.1 | 10.1, 4.8 |
| 10.3 | Retraining triggers: 1000+ new labels, AUC-ROC <0.72, monthly schedule, manual | §12.3.2 | 10.2 |
| 10.4 | Model evaluation gate: AUC-ROC >0.75, Precision@1000 >0.30, ECE <0.05, fairness | §12.3.3 | 10.2 |
| 10.5 | Shadow mode deployment: new model runs in parallel, no score impact | §12.5.2 | 10.4 |
| 10.6 | Canary deployment: 5% → A/B testing → full rollout with auto-rollback | §12.5.2 | 10.5 |
| 10.7 | Model drift detection: PSI for features, score distribution monitoring | §12.6 | 4.8 |
| 10.8 | Model management UI: version list, A/B results, retraining status, manual trigger | §7.2.8 | 8.8, 10.6 |

**Exit Criteria:** Retraining triggers automatically; new model goes through shadow → canary → rollout; auto-rollback on error spike; admin can view model status in UI.

---

## Phase 11: Deep Dive API & Custom Scoring
**Duration:** 1 sprint | **Agents:** BackendEngineer, DataScientist
**Goal:** Enterprise custom scoring with configurable models.

| # | Task | BRD Ref | Depends On |
|---|------|---------|------------|
| 11.1 | `POST /v1/scores/custom` — accept custom model configuration, return custom score | §9.4.1 | 3.1, 4.13 |
| 11.2 | Industry-specific model variants (retail, manufacturing, services, agriculture) | §4.2.1 | 4.8 |
| 11.3 | Configurable prediction horizons (30, 90, 365 days) | §4.2.1 | 11.1 |
| 11.4 | Dynamic model selection based on data quality and quantity | §4.2.1 | 11.1 |
| 11.5 | Deep Dive license tier enforcement (rate limit: 200/hr) | §9.4.1 | 2.6, 11.1 |

**Exit Criteria:** Custom scoring endpoint accepts model config and returns scores with configured horizon; industry-specific models selectable.

---

## Phase 12: Compliance, Security Hardening & Audit
**Duration:** 1 sprint | **Agents:** SecurityEngineer, DevOpsEngineer
**Goal:** Full regulatory compliance and security hardening for production.

| # | Task | BRD Ref | Depends On |
|---|------|---------|------------|
| 12.1 | PII encryption at rest (AES-256) for all sensitive DB fields | §13.1.1 | 1.8 |
| 12.2 | TLS 1.3 enforcement for all service-to-service communication | §13.1.1 | 0.1 |
| 12.3 | Immutable audit log storage (write-once Elasticsearch indices) | §13.3.1 | 1.6 |
| 12.4 | Audit log retention policies: 10-year for API/score/admin, 7-year for auth, 3-year for system | §13.3.2 | 12.3 |
| 12.5 | Data subject rights: access, correction, deletion endpoints (DPA 2019) | §13.2.1 | 1.1 |
| 12.6 | Account lockout after 5 failed login attempts | §13.4.1 | 2.3 |
| 12.7 | MFA for Admin and Operator roles | §13.4.1 | 2.2 |
| 12.8 | WAF configuration: OWASP Top 10 rule set | §13.4.2 | 0.1 |
| 12.9 | VPN-only access for admin portal in production | §13.4.2 | 8.1 |
| 12.10 | SAST in CI pipeline + dependency scanning (Trivy, Snyk) | §13.4.3 | 0.5 |
| 12.11 | Incident response runbook documentation | §13.5 | — |
| 12.12 | DPIA document completion | §13.2.1 | — |

**Exit Criteria:** All PII encrypted at rest; audit logs immutable with correct retention; MFA works for admin; WAF blocks OWASP attacks; security scans pass in CI.

---

## Phase 13: Infrastructure & Production Deployment
**Duration:** 1-2 sprints | **Agents:** DevOpsEngineer
**Goal:** Production-ready Kubernetes deployment with HA, backup, and DR.

| # | Task | BRD Ref | Depends On |
|---|------|---------|------------|
| 13.1 | Terraform: VPC, subnets, EKS cluster, RDS PostgreSQL, ElastiCache Redis | §7.5, §14.1.2 | — |
| 13.2 | Terraform: Kafka (MSK), S3 buckets, IAM roles | §7.5 | 13.1 |
| 13.3 | Helm charts for all services with env-specific values (dev/staging/prod) | §14.1.2 | 13.1 |
| 13.4 | ArgoCD GitOps: auto-sync staging, manual-approve production | §14.2.2 | 13.3 |
| 13.5 | CD pipeline: build images → push ECR → ArgoCD sync → smoke tests | §14.2.2 | 13.4 |
| 13.6 | Blue-green deployment with automatic rollback on health check failure | §14.2.2 | 13.5 |
| 13.7 | HashiCorp Vault for secrets management (API keys, DB creds, encryption keys) | §13.4.1 | 13.1 |
| 13.8 | Database backups: continuous PITR + daily snapshots, cross-region replication | §14.4.1 | 13.1 |
| 13.9 | Redis: RDB + AOF, cluster failover, cross-AZ replication | §14.4.1 | 13.1 |
| 13.10 | Sandbox environment provisioning for customer testing | §14.1.1, UC-CUST-001 | 13.1 |
| 13.11 | Capacity planning: HPA with CPU/memory thresholds, pod anti-affinity | §14.6 | 13.3 |
| 13.12 | Operational runbooks: incident response, deployment, model rollback, DR | §14.5 | 13.6 |

**Exit Criteria:** Production cluster running with HA; RPO <1h, RTO <4h; ArgoCD deploys from main; secrets in Vault; sandbox available for partners.

---

## Phase 14: Partner Dashboard & Billing
**Duration:** 1 sprint | **Agents:** FrontendEngineer, BackendEngineer
**Goal:** Partner-facing dashboard and usage-based billing.

| # | Task | BRD Ref | Depends On |
|---|------|---------|------------|
| 14.1 | Partner dashboard: score lookup, usage stats, API key management (masked display) | §7.3.2 | 8.6, 7.8 |
| 14.2 | White-label embedding: iframe/web component options with domain configuration | §7.3.2 | 8.10 |
| 14.3 | Billing calculation: monthly charges based on tier + query volume | §7.2.7 | 7.8 |
| 14.4 | Usage reports: monthly statement per customer with query breakdown | §7.2.7 | 14.3 |
| 14.5 | Partner API key rotation and revocation self-service | §7.2.2 | 7.1 |

**Exit Criteria:** Partners can view their scores, usage, and API keys; billing calculates correctly; white-label theming works per partner.

---

## Phase 15: Compliance Partners Integration
**Duration:** 1 sprint | **Agents:** BackendEngineer, SecurityEngineer
**Goal:** Live KYC and AML screening integrated into scoring pipeline.

| # | Task | BRD Ref | Depends On |
|---|------|---------|------------|
| 15.1 | Smile ID integration: KYC verification API (ID verification, biometric match, liveness) | §5.3.1 | 3.1 |
| 15.2 | ComplyAdvantage integration: AML screening (sanctions, PEP, adverse media) | §5.3.2 | 3.1 |
| 15.3 | Compliance status stored on Subject entity (kyc_status, aml_status) | §11.1.1 | 15.1, 15.2 |
| 15.4 | Compliance features fed into scoring model (§11.3.4) | §11.3.4 | 15.3, 4.6 |
| 15.5 | Monthly KYC refresh for existing users | §5.4 | 15.1 |

**Exit Criteria:** New subjects get KYC/AML screening; compliance features influence scores; monthly refresh runs.

---

## Dependency Graph (Simplified)

```
Phase 0 (Foundation)
  └── Phase 1 (Data Model)
        ├── Phase 2 (Auth)
        │     └── Phase 3 (Scoring APIs)
        │           ├── Phase 4 (ML Model)
        │           │     └── Phase 5 (Data Pipelines)
        │           │           └── Phase 6 (Batch + Feedback)
        │           │                 └── Phase 10 (Active Learning)
        │           └── Phase 7 (Customer Mgmt)
        │                 └── Phase 8 (Admin Portal)
        │                       └── Phase 14 (Partner Dashboard)
        └── Phase 9 (KPIs + Monitoring)

Phase 11 (Deep Dive) ← Phase 3, 4
Phase 12 (Security Hardening) ← Phase 1, 2, 8
Phase 13 (Production Infra) ← independent, parallel track
Phase 15 (Compliance Partners) ← Phase 3, 4
```

---

## Priority Summary

| Priority | Phases | Rationale |
|----------|--------|-----------|
| **P0 — Must Have First** | 0, 1, 2, 3 | No product without database, auth, and score APIs |
| **P0 — Core ML** | 4, 5 | Scoring APIs need a real model and feature pipeline |
| **P1 — Essential** | 6, 7, 8, 9 | Batch processing, customer management, admin UI, monitoring |
| **P1 — Production** | 12, 13 | Security hardening and infra required before go-live |
| **P2 — Growth** | 10, 11, 14, 15 | Active learning, Deep Dive API, partner dashboard, compliance integrations |

---

## Milestones

| Milestone | Phases Complete | Deliverable |
|-----------|----------------|-------------|
| **Alpha** | 0–3 | Scoring APIs live with mock/cached data, auth working |
| **Beta** | 4–6 | Real ML model scoring, daily pipeline, batch processing |
| **MVP** | 7–9 | Admin portal, customer management, KPI monitoring |
| **Production Launch** | 12–13 | Security hardened, production infrastructure, compliance |
| **GA (General Availability)** | 10–11, 14–15 | Active learning, Deep Dive, partner dashboard, compliance partners |
