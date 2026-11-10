# VyceScore Model Card — v1.0

## Model Details

| Field | Value |
|-------|-------|
| **Model Name** | VyceScore XGBoost Credit Scoring Model |
| **Version** | 1.0 |
| **Type** | Binary Classification (Gradient Boosted Trees) |
| **Framework** | XGBoost 2.0+ |
| **Target Variable** | Probability of Serious Delinquency (90+ DPD within 12 months) |
| **Output Range** | VyceScore 300-900 (higher = lower risk) |
| **Maintainers** | VycePay Data Science Team |
| **Last Updated** | 2026-03-08 |

## Intended Use

### Primary Use Case
Credit scoring for MSMEs and individuals in Kenya and emerging markets who lack traditional credit history. The model uses alternative data (mobile money transactions, supply chain data, compliance/identity verification) to generate credit scores.

### Product Tiers
- **VyceScore Lite API**: Returns VyceScore + NIQ Score. Target latency <500ms.
- **VyceScore Pro API**: Returns VyceScore + Top 3 SHAP-based Risk Drivers. Target latency <2s. Satisfies Kenya DPA 2019 explainability requirements.
- **Deep Dive API**: Enterprise model licensing with custom scoring.

### Intended Users
- Financial institutions (banks, MFIs, SACCOs) in Kenya
- Credit analysts performing underwriting
- Risk management teams

### Out-of-Scope Use Cases
- Consumer-facing credit score display without institution context
- Markets outside East Africa (model is calibrated for Kenya)
- Loan decisioning without human review (model provides risk assessment, not approval/denial)

## Model Architecture

### Algorithm
XGBoost (Extreme Gradient Boosting) binary classifier.

### Hyperparameters (BRD-specified)
| Parameter | Value |
|-----------|-------|
| max_depth | 6 |
| learning_rate | 0.05 |
| n_estimators | 500 |
| subsample | 0.8 |
| colsample_bytree | 0.8 |
| min_child_weight | 3 |
| gamma | 0.1 |
| scale_pos_weight | 3 |

### Score Conversion
- Formula: `VyceScore = 300 + (1 - P(default)) * 600`
- Range: 300 (highest risk) to 900 (lowest risk)

### Score Interpretation
| Score Range | Risk Category |
|-------------|---------------|
| 800-900 | Very Low Risk |
| 700-799 | Low Risk |
| 600-699 | Medium Risk |
| 500-599 | High Risk |
| 300-499 | Very High Risk |

## Features

### Six Core Features (The Scoring Moat)
1. **CBLRI** (Cross-Border Liquidity Resilience Index) — Consistency of international cash flows.
2. **UTDI** (Utility-Based Transactional Diversity Index) — Merchant category diversity per quarter.
3. **SCFV** (Supply Chain Formalization Velocity) — Growth rate of digitized supplier-buyer links via VyceTrade.
4. **DDC Ratio** (Digital Documentation Compliance) — Operational task completion rate.
5. **NIQ Score** (Network Interdependence and Quality) — Average VyceScore of top 5 trading partners (0-100 scale).
6. **GOS Index** (Geographic Operational Stability) — GPS variance of transaction endpoints.

### Data Sources
- **VycePay**: FT/IBFT transactions, remittances, merchant activity
- **VyceTrade**: Supplier payments, invoices, supply chain links
- **Compliance Partners**: Smile ID (KYC), ComplyAdvantage (AML)

## Training Data

### Phase 1 (Current): VOD Proxy Labels
- **Labeling Strategy**: Vyce-Observed Distress (VOD) — behavioral distress signals used as proxy for credit risk before ground-truth loan outcomes are available.
- **Distress Signals**: GOS volatility, CBLRI drop percentage, transaction pattern z-score.
- **Label Confidence**: Each label includes a confidence score reflecting data quality and signal strength.
- **Data Split**: 60% train / 20% validation / 20% test (stratified).

### Phase 2 (Planned): Ground Truth Labels
- Loan outcomes from partner banks (90+ DPD within 12 months).
- Active learning to prioritize high-uncertainty samples.
- A/B testing for model deployment.

## Performance Metrics

### Targets (from BRD)
| Metric | Target | Description |
|--------|--------|-------------|
| AUC-ROC | > 0.75 | Discriminatory power |
| Precision@1000 | > 0.30 | Top-K risk identification |
| Expected Calibration Error | < 0.05 | Probability calibration |

### Additional Metrics Tracked
- KS Statistic (class separation)
- Precision@100, Precision@500
- Demographic parity across customer segments

## Explainability

### Method
SHAP (SHapley Additive exPlanations) TreeExplainer for XGBoost.

### Output Format
Top 3 risk drivers per prediction, each including:
- **Factor**: Human-readable feature name
- **Impact**: "positive" (increases risk) or "negative" (decreases risk)
- **Description**: Natural language explanation
- **Contribution**: Percentage of total absolute SHAP value

### Regulatory Compliance
Satisfies Kenya Data Protection Act (DPA 2019) requirement for "meaningful information about the logic involved" in automated decisions affecting data subjects.

## Limitations

### Known Limitations
1. **VOD proxy labels**: Phase 1 labels are based on behavioral distress signals, not actual loan defaults. Model accuracy will improve once ground-truth labels are available in Phase 2.
2. **Data recency**: Features are computed on 30-day and 90-day windows. Score may not reflect very recent changes in financial behavior.
3. **Cold start**: New entities with less than 30 days of transaction history receive lower confidence scores.
4. **Geographic bias**: Model is calibrated for Kenya. Performance may degrade for entities operating primarily in other markets.
5. **Network effects**: NIQ Score depends on the VyceScore of trading partners. Sparse networks may produce less reliable NIQ scores.

### Failure Modes
- Missing features default to 0 or NaN, which may produce unreliable scores.
- Extreme outliers in transaction data may produce miscalibrated probabilities.
- Model drift: changing economic conditions may reduce model performance over time.

## Ethical Considerations

### Fairness
- Demographic parity checks are performed across customer segments.
- No protected attributes (gender, ethnicity, religion) are used as direct features.
- Geographic features (GOS Index) measure operational stability, not geographic discrimination.

### Privacy
- All PII is encrypted at rest and in transit.
- Raw data is anonymized after feature extraction.
- API requests are logged to an immutable audit trail.
- 10-year data retention per CBK regulations.

### Impact
- The model is designed to expand financial inclusion by scoring MSMEs and individuals who lack traditional credit history.
- Misuse risk: overly aggressive lending based on model scores without human review.
- Mitigation: scores are advisory; human review is required for final lending decisions.

## Monitoring

### Model Performance Monitoring
- Population Stability Index (PSI) for feature drift detection.
- Daily batch recalculation at 03:00 UTC.
- Performance metrics tracked via MLflow.

### Drift Thresholds
| PSI Value | Action |
|-----------|--------|
| < 0.10 | No action needed |
| 0.10 - 0.25 | Investigate |
| > 0.25 | Retrain model |

### Retraining Triggers
- PSI > 0.25 on any core feature
- AUC-ROC drops below 0.70
- New ground-truth labels available from partner banks
- Quarterly scheduled retraining

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-03-08 | Initial model with VOD proxy labels and 6 core features |
