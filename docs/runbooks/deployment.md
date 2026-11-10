# Deployment Runbook

## Overview

VyceScore uses a GitOps deployment model with ArgoCD. Changes merged to `main` are automatically deployed to staging. Production deployments require manual approval.

## Prerequisites

- `kubectl` configured for the target cluster
- `argocd` CLI installed and authenticated
- AWS CLI configured with appropriate IAM role
- Access to the VyceScore GitHub repository

## Deployment Pipeline

```
Code Merge → CI (lint/test/build) → Docker Build → ECR Push
→ ArgoCD Staging (auto-sync) → Smoke Tests
→ ArgoCD Production (manual approval) → Blue-Green Switch → Smoke Tests
```

## Standard Deployment (Staging)

Staging deployments are automatic on merge to `main`.

### Manual trigger:
```bash
# Via GitHub Actions
gh workflow run cd.yml -f environment=staging

# Via ArgoCD CLI
SHA=$(git rev-parse --short HEAD)
argocd app set vycescore-staging \
  --helm-set services.backendApi.image.tag=$SHA \
  --helm-set services.frontend.image.tag=$SHA \
  --helm-set services.mlServing.image.tag=$SHA \
  --helm-set services.worker.image.tag=$SHA \
  --grpc-web
argocd app sync vycescore-staging --grpc-web --prune
argocd app wait vycescore-staging --grpc-web --timeout 300 --health
```

### Verify staging:
```bash
curl -sf https://staging-api.vycescore.com/health | jq .
curl -sf https://staging-api.vycescore.com/v1/health | jq .
```

## Production Deployment

### Pre-deployment checklist:
- [ ] Staging smoke tests passing
- [ ] No critical alerts in Grafana
- [ ] Database migrations applied (if any)
- [ ] Team notified in Slack
- [ ] Change window confirmed (Mon-Fri 09:00-18:00 EAT)

### Deploy:
```bash
# Option 1: Tag-based (preferred)
git tag -a v1.X.Y -m "Release v1.X.Y"
git push origin v1.X.Y

# Option 2: Manual workflow dispatch
gh workflow run cd.yml -f environment=production

# Option 3: ArgoCD CLI
argocd app sync vycescore-production --grpc-web --prune
argocd app wait vycescore-production --grpc-web --timeout 600 --health
```

### Post-deployment verification:
```bash
# Health check
curl -sf https://api.vycescore.com/health | jq .

# API version check
curl -sf https://api.vycescore.com/v1/health | jq .

# Check ArgoCD sync status
argocd app get vycescore-production --grpc-web

# Check pod status
kubectl get pods -n vycescore -o wide
kubectl top pods -n vycescore
```

## Rollback Procedures

### ArgoCD rollback (fastest):
```bash
# List recent deployments
argocd app history vycescore-production --grpc-web

# Rollback to previous revision
argocd app rollback vycescore-production --grpc-web
argocd app wait vycescore-production --grpc-web --timeout 300 --health
```

### Helm rollback:
```bash
# List revisions
helm history vycescore -n vycescore

# Rollback
helm rollback vycescore <REVISION> -n vycescore
```

### Image tag rollback:
```bash
# Deploy a specific known-good tag
argocd app set vycescore-production \
  --helm-set services.backendApi.image.tag=<GOOD_SHA> \
  --helm-set services.mlServing.image.tag=<GOOD_SHA> \
  --grpc-web
argocd app sync vycescore-production --grpc-web
```

## Blue-Green Deployment (Production)

Production uses blue-green deployment for zero-downtime releases.

### Check active slot:
```bash
kubectl get svc backend-api -n vycescore -o jsonpath='{.spec.selector.slot}'
```

### Switch traffic:
```bash
# The CD pipeline handles slot switching automatically.
# Manual switch if needed:
argocd app set vycescore-production \
  --helm-set blueGreen.activeSlot=green \
  --grpc-web
argocd app sync vycescore-production --grpc-web
```

## Troubleshooting

### Pods not starting:
```bash
kubectl describe pod <POD_NAME> -n vycescore
kubectl logs <POD_NAME> -n vycescore --previous
```

### OOM kills:
```bash
kubectl top pods -n vycescore
kubectl describe pod <POD_NAME> -n vycescore | grep -A5 "Last State"
```

### ArgoCD sync stuck:
```bash
argocd app get vycescore-<ENV> --grpc-web -o json | jq '.status.conditions'
argocd app terminate-op vycescore-<ENV> --grpc-web
argocd app sync vycescore-<ENV> --grpc-web --force
```

## Contacts

| Role | Contact |
|------|---------|
| Platform Lead | platform@vycescore.com |
| On-call Engineer | PagerDuty rotation |
| Database Admin | dba@vycescore.com |
