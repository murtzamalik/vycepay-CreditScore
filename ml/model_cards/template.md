# Model Card: VyceScore Credit Scoring Model

## Model Details

- **Model name**: VyceScore XGBoost v{version}
- **Model type**: Gradient Boosted Decision Tree (XGBoost)
- **Version**: {version}
- **Date trained**: {date_trained}
- **Framework**: XGBoost {xgboost_version}, Python {python_version}
- **Owner**: VycePay ML Engineering

## Intended Use

- **Primary use**: Predict probability of Serious Delinquency (90+ days past due) within 12 months for MSMEs and individuals in Kenya and emerging markets.
- **Intended users**: VycePay partner financial institutions via VyceScore Lite and Pro APIs.
- **Out-of-scope uses**: This model should NOT be used for decisions outside credit risk assessment, or for populations significantly different from the training data (e.g., markets outside East Africa without recalibration).

## Training Data

- **Source**: VycePay (mobile money transactions), VyceTrade (supply chain data), compliance partners (KYC/AML).
- **Period**: {training_period}
- **Size**: {n_training_samples} entities
- **Positive rate**: {positive_rate}% (90+ DPD within 12 months)
- **Label source**: Phase 1 — Vyce-Observed Distress (VOD) proxy labels; Phase 2 — ground truth from partner bank loan outcomes.

## Features

| Feature | Description | Range |
|---------|-------------|-------|
| CBLRI | Cross-Border Liquidity Resilience Index | 0.0 - 1.0 |
| UTDI | Utility-Based Transactional Diversity Index | 0.0 - 1.0 |
| SCFV | Supply Chain Formalization Velocity | 0.0 - 1.0 |
| DDC Ratio | Digital Documentation Compliance | 0.0 - 1.0 |
| NIQ Score | Network Interdependence and Quality | 0 - 100 |
| GOS Index | Geographic Operational Stability | 0.0 - 1.0 |

## Performance Metrics

| Metric | Value | Target |
|--------|-------|--------|
| AUC-ROC | {auc_roc} | > 0.75 |
| Precision@1000 | {precision_at_1000} | > 0.30 |
| Calibration Error (ECE) | {calibration_error} | < 0.05 |
| KS Statistic | {ks_statistic} | — |

## Ethical Considerations

- **Fairness**: Model does not use protected attributes (gender, ethnicity, religion) as direct features. Periodic bias audits are conducted across demographic segments.
- **Financial inclusion**: Designed specifically to score entities lacking traditional credit bureau history, expanding access to credit for underserved populations.
- **Explainability**: VyceScore Pro API provides Top 3 Risk Drivers with directional indicators using SHAP values, satisfying Kenya Data Protection Act (DPA 2019) requirements.

## Limitations

- Performance may degrade for entities with very limited transaction history (< 3 months on VycePay).
- NIQ Score depends on partner VyceScores — new entities in sparse networks will have lower NIQ regardless of their own creditworthiness.
- Model is calibrated for Kenyan market conditions; deployment to other markets requires recalibration.

## Monitoring

- Feature drift monitored via Population Stability Index (PSI) on daily batch runs.
- Model performance tracked against live loan outcomes via the Feedback Service.
- Retraining triggered when PSI > 0.25 for any core feature or AUC-ROC drops below 0.72 on rolling 30-day evaluation.
