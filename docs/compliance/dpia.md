# Data Protection Impact Assessment (DPIA)

**Project:** VyceScore Credit Scoring Engine
**Version:** 1.0
**Date:** 2026-03-08
**Prepared By:** Security Engineering, VyceScore
**Regulatory Framework:** Kenya Data Protection Act, 2019 (DPA 2019)
**DPA Section:** Section 31 — Data Protection Impact Assessment

## 1. Overview

### 1.1 Purpose
This DPIA assesses the data protection risks associated with VyceScore, a credit scoring engine that processes personal and financial data of individuals and MSMEs in Kenya. Per Section 31 of the Kenya DPA 2019, a DPIA is required when processing is likely to result in high risk to the rights and freedoms of data subjects, particularly when using new technologies or automated decision-making.

### 1.2 Scope
- VyceScore Lite API (rapid pre-screening)
- VyceScore Pro API (full underwriting with explainability)
- Deep Dive API (enterprise model licensing)
- Admin Portal (internal management)
- Data ingestion from VycePay and VyceTrade platforms

### 1.3 Data Controller
VycePay Limited, registered in Kenya.

### 1.4 Data Protection Officer
[DPO Name], dpo@vycepay.co.ke

## 2. Description of Processing

### 2.1 Nature of Processing
VyceScore processes personal data to generate credit scores (300-900 scale) using machine learning (XGBoost gradient boosting). The system:
- Ingests transaction data from VycePay (mobile money) and VyceTrade (supply chain)
- Computes six proprietary ML features (CBLRI, UTDI, SCFV, DDC Ratio, NIQ Score, GOS Index)
- Runs inference to predict probability of serious delinquency (90+ DPD within 12 months)
- Provides SHAP-based explainability (Top 3 Risk Drivers) for the Pro API
- Serves scores to partner financial institutions via API

### 2.2 Purpose of Processing
- Enable financial institutions to assess creditworthiness of individuals and MSMEs lacking traditional credit history
- Support financial inclusion in Kenya per CBK mandate
- Provide regulatory-compliant risk assessment with explainability

### 2.3 Categories of Data Subjects
- Individual Kenyans (mobile money users)
- Micro, Small, and Medium Enterprises (MSMEs)
- Business owners and operators

### 2.4 Categories of Personal Data

| Category | Data Elements | Sensitivity |
|----------|--------------|-------------|
| Identity | National ID (stored as SHA-256 hash only) | High |
| Financial | Transaction amounts, frequencies, merchant categories | High |
| Geographic | Transaction location GPS coordinates (aggregated to GOS Index) | Medium |
| Network | Trading partner relationships (anonymized for NIQ Score) | Medium |
| Compliance | KYC verification status, AML screening results | High |
| Behavioral | Transaction patterns, diversity metrics, formalization velocity | Medium |

### 2.5 Data Flows
1. **Ingestion**: VycePay/VyceTrade -> Kafka -> Feature Engineering Service
2. **Processing**: Raw data -> Feature computation -> Feature store (PostgreSQL)
3. **Scoring**: Feature store -> XGBoost inference -> Score + SHAP explanations
4. **Serving**: API Gateway -> Partner financial institution
5. **Feedback**: Partner loan outcomes -> Training data -> Model retraining

### 2.6 Legal Basis for Processing
- **Section 30(1)(b)**: Processing necessary for performance of a contract (credit assessment)
- **Section 30(1)(f)**: Legitimate interest of the data controller (financial inclusion)
- **Central Bank of Kenya**: Risk-Based Credit Pricing Model compliance

## 3. Necessity and Proportionality

### 3.1 Necessity Assessment
- Credit scoring is essential for financial institutions to comply with CBK risk management requirements
- Alternative data-based scoring addresses the financial inclusion gap for unbanked/underbanked populations
- Without VyceScore, partner institutions would either refuse credit or rely on less accurate methods

### 3.2 Proportionality Measures
- **Data Minimization**: National IDs are immediately hashed (SHA-256); raw PII is not stored
- **Purpose Limitation**: Data is processed solely for credit scoring; no secondary use
- **Storage Limitation**: 10-year retention per CBK requirements; anonymization after feature extraction
- **Accuracy**: Daily batch recalculation ensures scores reflect current behavior
- **Explainability**: SHAP-based Top 3 Risk Drivers satisfy DPA 2019 requirement for "meaningful information about the logic involved" in automated decisions

## 4. Risk Assessment

### 4.1 Identified Risks

| # | Risk | Likelihood | Severity | Overall Risk | Mitigation |
|---|------|-----------|----------|-------------|------------|
| R1 | Unauthorized access to scoring data | Medium | High | High | API key auth, JWT, RBAC, MFA for admins, VPN-only admin access |
| R2 | Data breach exposing PII | Low | Critical | High | AES-256-GCM encryption at rest, TLS 1.3 in transit, WAF, no raw PII storage |
| R3 | Discriminatory scoring outcomes | Medium | High | High | Bias monitoring, fairness metrics in model training, SHAP explainability |
| R4 | Inaccurate scores causing financial harm | Medium | High | High | Daily recalculation, model monitoring, partner feedback loop, A/B testing |
| R5 | Unauthorized model tampering | Low | High | Medium | Model versioning, canary deployment, immutable audit logs with hash chain |
| R6 | Non-compliance with data subject rights | Low | High | Medium | Automated data access, correction, and deletion endpoints |
| R7 | Insider threat (employee misuse) | Low | High | Medium | RBAC, audit logging, principle of least privilege, MFA |
| R8 | Third-party data source compromise | Medium | Medium | Medium | Input validation, anomaly detection, contractual obligations |
| R9 | Audit trail tampering | Low | Critical | Medium | SHA-256 hash chain integrity, append-only storage, verification API |
| R10 | Key management failure | Low | Critical | Medium | Env-based keys for dev, Vault/KMS for production, key rotation support |

### 4.2 Risk Mitigation Details

#### R1 & R7: Access Control
- Four-tier RBAC: Admin, Operator, Partner, Read-Only
- TOTP MFA mandatory for Admin and Operator roles
- Admin portal accessible only via VPN
- Account lockout after 5 failed login attempts (30-minute lockout)
- All admin actions logged to immutable audit trail

#### R2: Data Protection
- PII (National ID) stored only as SHA-256 hash
- Sensitive fields encrypted with AES-256-GCM (EncryptedString column type)
- TLS 1.3 enforced for all communication
- WAF with OWASP Top 10 rule coverage
- 10-year data retention with automated cleanup

#### R3 & R4: Model Fairness and Accuracy
- SHAP explainability provides transparent scoring rationale
- Model performance targets: AUC-ROC > 0.75
- Active learning from partner bank loan outcomes
- Daily batch recalculation ensures score currency
- Canary deployment for model updates

#### R6: Data Subject Rights
- Right of Access: API endpoint returns all data held about a subject
- Right of Rectification: Correction requests with admin review workflow
- Right to Deletion: Anonymization (not physical deletion) preserves regulatory compliance

#### R9: Audit Integrity
- Hash chain (blockchain-like) linking each audit entry to the previous
- Verification function to detect any tampering
- Category-based retention policies (3-10 years depending on type)

## 5. Data Subject Rights Implementation

| Right (DPA 2019 Section) | Implementation | Endpoint |
|--------------------------|---------------|----------|
| Right of Access (s.26) | Full data export per subject | `GET /v1/data-rights/access/{subjectId}` |
| Right of Rectification (s.27) | Correction request workflow | `POST /v1/data-rights/correction` |
| Right to Erasure (s.28) | Anonymization of identity data | `POST /v1/data-rights/deletion/{subjectId}` |
| Right to Object (s.26(4)) | Processing objection via correction endpoint | `POST /v1/data-rights/correction` |
| Automated Decision Rights (s.35) | SHAP explainability in Pro API | `GET /v1/scores/pro/{nationalId}` |

## 6. Consultation

### 6.1 Stakeholders Consulted
- Legal Counsel (Kenya DPA 2019 compliance)
- Central Bank of Kenya (CBK regulatory requirements)
- Partner Financial Institutions (data usage expectations)
- Data Protection Officer

### 6.2 Office of the Data Protection Commissioner (ODPC)
This DPIA will be submitted to the ODPC per Section 31(2) of DPA 2019, as the processing involves:
- Automated decision-making with legal effects (credit scoring)
- Large-scale processing of sensitive financial data
- Systematic monitoring of data subjects' financial behavior

## 7. Approval and Review

### 7.1 Approval
This DPIA has been reviewed and approved by:

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Data Protection Officer | [Name] | [Date] | [Signature] |
| Chief Technology Officer | [Name] | [Date] | [Signature] |
| Chief Compliance Officer | [Name] | [Date] | [Signature] |

### 7.2 Review Schedule
- **Quarterly**: Review risk ratings and mitigation effectiveness
- **Annually**: Full DPIA review and update
- **Ad-hoc**: After any significant change to processing activities, data sources, or ML models
- **Post-incident**: After any data breach or security incident

### 7.3 Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-03-08 | Security Engineering | Initial DPIA |
