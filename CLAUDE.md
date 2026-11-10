# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VyceScore is a credit scoring engine for financial institutions in Kenya and emerging markets. It uses alternative data (mobile money transactions, supply chain data, compliance/identity verification) to generate credit scores (300-900) for MSMEs and individuals who lack traditional credit history.

### Product Tiers
- **VyceScore Lite API**: Rapid pre-screening — returns VyceScore + NIQ Score (<500ms)
- **VyceScore Pro API**: Full underwriting — returns VyceScore + Top 3 Risk Drivers with SHAP explainability (<2s)
- **Deep Dive API**: Enterprise model licensing with custom scoring development

### Six Core ML Features (The Scoring Moat)
1. **CBLRI** — Cross-Border Liquidity Resilience Index (international cash flow consistency)
2. **UTDI** — Utility-Based Transactional Diversity Index (merchant category diversity per quarter)
3. **SCFV** — Supply Chain Formalization Velocity (digitized supplier-buyer link growth via VyceTrade)
4. **DDC Ratio** — Digital Documentation Compliance (operational task completion rate)
5. **NIQ Score** — Network Interdependence and Quality (avg VyceScore of top 5 trading partners)
6. **GOS Index** — Geographic Operational Stability (GPS variance of transaction endpoints)

## Architecture

**Microservices, API-first, event-driven, cloud-agnostic.**

### System Components
- **API Gateway** — Authentication (API key via X-API-Key header), rate limiting (tier-based), routing, SSL termination
- **Authentication Service** — User auth, API key management, RBAC (Admin/Operator/Partner/Read-only), JWT sessions
- **Scoring Service** — Feature retrieval, XGBoost inference, SHAP explanation generation, Redis caching (24h TTL)
- **Feature Engineering Service** — Data ingestion from VycePay/VyceTrade, validation, feature computation, feature store updates
- **Model Management Service** — ML training pipelines, model versioning, A/B testing, canary deployment
- **Feedback Service** — Loan outcome collection from partner banks, ground truth labeling, retraining triggers
- **Licensing & Billing Service** — Tier enforcement, usage tracking, quota management
- **Admin UI** — React + TypeScript, Redux Toolkit, Material-UI or Ant Design, Recharts/Chart.js

### Data Sources
- **VycePay**: FT/IBFT transactions, remittances, merchant activity
- **VyceTrade**: Supplier payments, invoices, supply chain links
- **Compliance Partners**: Smile ID (KYC), ComplyAdvantage (AML)

### Data Flow
- **Batch**: Daily at 02:00 UTC — extract → validate → feature engineer → model inference → cache refresh → KPI reports
- **Real-time**: API request → auth → cache check → feature fetch → inference → SHAP → response
- **Feedback loop**: Partner bank loan outcome → validate → training pool → retrain trigger → A/B test → deploy

### Infrastructure Stack
| Layer | Technology |
|-------|-----------|
| Compute | Kubernetes with auto-scaling |
| Database | PostgreSQL (relational), Redis (cache) |
| Storage | S3-compatible object storage (data lake, Parquet) |
| Message Queue | Kafka or RabbitMQ |
| Monitoring | Prometheus + Grafana |
| Logging | ELK stack |
| CI/CD | GitHub Actions or GitLab CI |
| ML Model | XGBoost/LightGBM (Gradient Boosting) |

### API Design
- RESTful, JSON, HTTPS only
- URL path versioning: `/v1/`, `/v2/`
- Auth: `X-API-Key` header + OAuth 2.0
- Rate limit headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`
- Key endpoints: `GET /v1/scores/lite/{nationalId}`, `GET /v1/scores/pro/{nationalId}`, `POST /v1/scores/batch`

## ML Model Details

- **Target**: Probability of Serious Delinquency (90+ DPD) within 12 months, transformed to 300-900 scale
- **Training strategy**: Phase 1 uses Vyce-Observed Distress (VOD) as proxy labels; Phase 2 incorporates ground truth from partner bank loan outcomes via active learning
- **Explainability**: SHAP values → Top 3 risk drivers with directional indicators
- **Performance targets**: AUC-ROC > 0.75, API availability 99.9%, Lite <500ms, Pro <2s

## Compliance Context

- **Kenya Data Protection Act (DPA 2019)**: Requires "meaningful information about the logic involved" in automated decisions — Pro API's Top 3 Risk Drivers satisfies this
- **Central Bank of Kenya (CBK)**: Risk-Based Credit Pricing Model compliance; financial inclusion mandate
- **Data retention**: 10 years; PII encrypted at rest and in transit; raw data anonymized after feature extraction
- All API requests logged to immutable audit trail

## Documentation

Business and technical requirements are in `/docs/`:
- `VyceScore_BRD.pdf` — Full business requirements document (primary reference)
- `VyceScore High Level Data Flow Diagram.pdf` — System data flow
- `VyceScore DFD.pdf` — Detailed data flow diagram
- `VyceScore_ Technical & Strategic Moat Document (Kenya Focus).pdf` — Strategic and technical moat analysis
- VycePay business plans and pitch decks are also available in `/docs/`
