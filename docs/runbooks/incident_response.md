# VyceScore Incident Response Runbook

**Version:** 1.0
**Last Updated:** 2026-03-08
**Owner:** Security Engineering Team

## 1. Incident Classification

### Severity Levels

| Level | Description | Response Time | Examples |
|-------|-------------|---------------|----------|
| **SEV-1 (Critical)** | Production down, data breach, or active exploitation | 15 minutes | Data exfiltration, API gateway down, DB compromise |
| **SEV-2 (High)** | Significant degradation or potential security incident | 30 minutes | Scoring service failures, suspicious auth patterns, WAF alerts |
| **SEV-3 (Medium)** | Limited impact, no data exposure | 2 hours | Single service degradation, failed SAST findings, dependency CVE |
| **SEV-4 (Low)** | Informational, no immediate impact | Next business day | Log anomalies, minor config drift, documentation gaps |

## 2. Incident Response Phases

### Phase 1: Detection and Alerting

**Sources of Detection:**
- Prometheus/Grafana alerts (latency, error rates, resource exhaustion)
- WAF block rate spikes
- ELK stack anomaly detection (auth failures, unusual API patterns)
- Audit log integrity check failures
- Third-party security scanner findings (Trivy, Bandit, TruffleHog)
- External reports (customers, bug bounty, CERT-KE)

**On-Call Rotation:**
- Primary on-call: Check PagerDuty/Opsgenie
- Escalation: Security Engineering Lead -> CTO
- Contact CBK Incident Response if financial data is involved

### Phase 2: Triage and Classification

1. **Assess scope**: Which services are affected?
2. **Check audit logs**: `GET /v1/admin/audit-logs?category=<relevant>&start_time=<T>`
3. **Verify audit chain integrity**: Run chain verification for the affected time window
4. **Classify severity** using the table above
5. **Create incident ticket** in tracking system

### Phase 3: Containment

**Immediate Actions by Incident Type:**

#### Data Breach / Unauthorized Access
```bash
# 1. Revoke compromised API keys
# Via admin API: POST /v1/admin/customers/{id}/revoke-key

# 2. Force password reset for affected users
# Via admin API: POST /v1/admin/users/{id}/force-reset

# 3. Block suspicious IPs at WAF level
# Update WAF IP block list in infrastructure/security/waf/

# 4. Rotate encryption keys if PII exposure suspected
# Update VYCESCORE_ENCRYPTION_KEY_* environment variables

# 5. Invalidate all JWT sessions
# Rotate JWT_SECRET_KEY in environment configuration
```

#### Service Compromise
```bash
# 1. Isolate affected pods
kubectl cordon <node-name>
kubectl drain <node-name> --ignore-daemonsets

# 2. Scale down compromised deployment
kubectl scale deployment <name> --replicas=0 -n vycescore

# 3. Deploy clean version from known-good image
kubectl rollout undo deployment <name> -n vycescore

# 4. Review network policies
kubectl get networkpolicy -n vycescore
```

#### DDoS / Rate Limit Exhaustion
```bash
# 1. Tighten WAF rate limits
# Update infrastructure/security/waf/waf_rules.json

# 2. Enable geo-blocking if attack is region-specific

# 3. Scale up API Gateway and scoring service
kubectl scale deployment api-gateway --replicas=5 -n vycescore
```

### Phase 4: Eradication

1. **Identify root cause** through log analysis and code review
2. **Patch vulnerability** or close attack vector
3. **Update WAF rules** if new attack patterns discovered
4. **Run full SAST scan** on affected code paths
5. **Verify audit log chain integrity** post-incident

### Phase 5: Recovery

1. **Restore services** from known-good state
2. **Verify data integrity** (run score recalculation if needed)
3. **Re-enable disabled accounts** after verification
4. **Monitor closely** for 48 hours post-recovery
5. **Communicate with affected partners** via established channels

### Phase 6: Post-Incident

1. **Conduct blameless post-mortem** within 48 hours
2. **Document timeline** with all actions taken
3. **Update runbook** with lessons learned
4. **File regulatory notifications** if required (see below)

## 3. Regulatory Notification Requirements

### Kenya Data Protection Act (DPA 2019)
- **Timeline**: Notify the Office of the Data Protection Commissioner (ODPC) within 72 hours of becoming aware of a personal data breach
- **Content**: Nature of breach, categories of data subjects affected, approximate number of records, likely consequences, measures taken
- **Data Subject Notification**: Required if breach is likely to result in high risk to rights and freedoms

### Central Bank of Kenya (CBK)
- **Timeline**: Notify CBK within 24 hours for incidents affecting financial services
- **Content**: Nature of incident, impact on services, remediation steps

### Contact Information
- ODPC Kenya: complaints@odpc.go.ke
- CBK: communications@centralbank.go.ke
- CERT-KE: incident@ke-cirt.go.ke

## 4. Key Diagnostic Commands

### Check Service Health
```bash
# Health endpoint
curl -s https://api.vycescore.com/v1/health | jq .

# Prometheus metrics
curl -s http://prometheus:9090/api/v1/query?query=up

# Check pod status
kubectl get pods -n vycescore -o wide
```

### Check Authentication Anomalies
```bash
# Recent failed logins (via ELK)
# Query: event_type:login_failed AND @timestamp:[now-1h TO now]

# Locked accounts
# Via admin API: GET /v1/admin/users?locked=true
```

### Check Audit Log Integrity
```bash
# Verify hash chain (via internal service call)
# POST /internal/audit/verify-chain
# Body: {"start_sequence": 1, "end_sequence": null}
```

### Check WAF Activity
```bash
# WAF logs in S3
aws s3 ls s3://vycescore-waf-logs/ --recursive | tail -20

# CloudWatch WAF metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/WAFV2 \
  --metric-name BlockedRequests \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

## 5. Escalation Matrix

| Condition | Escalate To | Method |
|-----------|------------|--------|
| SEV-1 confirmed | CTO + Security Lead | Phone call |
| Data breach confirmed | Legal + DPO | Phone + Email |
| CBK-regulated service affected | Compliance Officer | Phone call |
| Cannot contain within 1 hour | External IR consultancy | Pre-arranged contract |
| Partner data affected | Partner Relations | Email within 2 hours |

## 6. Communication Templates

### Internal Stakeholder Update
```
Subject: [SEV-X] VyceScore Incident - [Brief Description]

Status: [Investigating | Contained | Resolved]
Impact: [Description of user/service impact]
Timeline: [When detected, key actions taken]
Next Steps: [Planned actions]
ETA to Resolution: [Estimate]
```

### Partner Notification
```
Subject: VyceScore Service Notice - [Date]

Dear Partner,

We are writing to inform you of a [service disruption/security incident]
affecting VyceScore services. [Brief, factual description].

Impact: [What the partner needs to know]
Current Status: [What we are doing]
Expected Resolution: [Timeline]

We will provide updates every [frequency] until resolution.

VyceScore Security Team
```
