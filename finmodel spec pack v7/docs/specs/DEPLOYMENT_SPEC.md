# Deployment & Infrastructure Specification
**Date:** 2026-02-11

## Overview
FinModel deployment architecture supports scalable, secure, and reliable operation across development, staging, and production environments. This document defines infrastructure, deployment procedures, disaster recovery, and operational practices.

## Environment Strategy

### Environments

| Environment | Purpose | Data | Deployment |
|---|---|---|---|
| **Development** | Local development | Synthetic/test data | Manual |
| **Staging** | Pre-production testing | Sanitized prod data | Auto on merge to `main` |
| **Production** | Live customer workloads | Real data | Manual approval + auto |

### Environment Configuration

```yaml
# .env.development
ENVIRONMENT=development
LOG_LEVEL=DEBUG
DATABASE_URL=postgresql://localhost:5432/finmodel_dev
SUPABASE_URL=http://localhost:54321
REDIS_URL=redis://localhost:6379
LLM_PROVIDER=mock  # Use mock LLM for faster dev

# .env.staging
ENVIRONMENT=staging
LOG_LEVEL=INFO
DATABASE_URL=postgresql://staging-db.xxx.supabase.co:5432/postgres
SUPABASE_URL=https://xxx.supabase.co
REDIS_URL=redis://staging-redis.xxx:6379
LLM_PROVIDER=anthropic,openai

# .env.production
ENVIRONMENT=production
LOG_LEVEL=WARNING
DATABASE_URL=postgresql://prod-db.xxx.supabase.co:5432/postgres
SUPABASE_URL=https://xxx.supabase.co
REDIS_URL=redis://prod-redis.xxx:6379
LLM_PROVIDER=anthropic,openai
ENABLE_METRICS=true
ENABLE_TRACING=true
```

---

## Infrastructure Architecture

### Deployment Topology

```
┌─────────────────────────────────────────────────┐
│              CloudFlare CDN                      │  ← Static assets, DDoS protection
└─────────────────┬───────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────┐
│         Load Balancer (ALB/NLB)                  │  ← SSL termination, routing
└───┬──────────────┬────────────────┬──────────────┘
    │              │                │
┌───▼───┐      ┌───▼───┐       ┌───▼───┐
│ API   │      │ API   │       │ API   │           ← Stateless FastAPI instances
│ Pod 1 │      │ Pod 2 │       │ Pod 3 │
└───┬───┘      └───┬───┘       └───┬───┘
    │              │                │
    └──────────────┴────────────────┘
                   │
    ┌──────────────┼──────────────┐
    │              │              │
┌───▼────┐   ┌─────▼─────┐  ┌────▼────┐
│ Redis  │   │ Supabase  │  │ Celery  │
│ Cache  │   │ (Postgres │  │ Workers │
└────────┘   │  + Auth   │  └─────────┘
             │  + Storage│
             └───────────┘
```

### Container Architecture

**API Service (FastAPI):**
```dockerfile
# Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY apps/api/ ./apps/api/
COPY shared/ ./shared/

# Non-root user
RUN useradd -m -u 1000 appuser
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/api/v1/health/ready || exit 1

EXPOSE 8000

CMD ["uvicorn", "apps.api.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

**Web Service (Next.js):**
```dockerfile
# Dockerfile.web
FROM node:20-alpine AS builder

WORKDIR /app
COPY apps/web/package*.json ./
RUN npm ci
COPY apps/web/ ./
RUN npm run build

FROM node:20-alpine
WORKDIR /app
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./

EXPOSE 3000
CMD ["npm", "start"]
```

**Background Worker (Celery):**
```dockerfile
# Dockerfile.worker
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/api/ ./apps/api/
COPY shared/ ./shared/

CMD ["celery", "-A", "apps.api.app.worker", "worker", "-l", "info", "-c", "4"]
```

### Kubernetes Manifests (Optional)

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: finmodel-api
  namespace: finmodel
spec:
  replicas: 3
  selector:
    matchLabels:
      app: finmodel-api
  template:
    metadata:
      labels:
        app: finmodel-api
    spec:
      containers:
      - name: api
        image: finmodel/api:v1.0.0
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: finmodel-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            configMapKeyRef:
              name: finmodel-config
              key: redis-url
        resources:
          requests:
            cpu: 500m
            memory: 1Gi
          limits:
            cpu: 2000m
            memory: 4Gi
        livenessProbe:
          httpGet:
            path: /api/v1/health/live
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /api/v1/health/ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10

---
apiVersion: v1
kind: Service
metadata:
  name: finmodel-api
  namespace: finmodel
spec:
  selector:
    app: finmodel-api
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer

---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: finmodel-api-hpa
  namespace: finmodel
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: finmodel-api
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

---

## Secret Management

### Development
```bash
# .env file (gitignored)
cp .env.example .env
# Edit with actual values
```

### Staging / Production

**Option 1: AWS Secrets Manager**
```python
import boto3
import json

def get_secret(secret_name):
    client = boto3.client('secretsmanager', region_name='us-east-1')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# At startup
secrets = get_secret('finmodel/production')
DATABASE_URL = secrets['DATABASE_URL']
ANTHROPIC_API_KEY = secrets['ANTHROPIC_API_KEY']
```

**Option 2: Kubernetes Secrets**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: finmodel-secrets
  namespace: finmodel
type: Opaque
stringData:
  database-url: postgresql://user:pass@host/db
  anthropic-api-key: sk-ant-...
  openai-api-key: sk-...
```

**Option 3: HashiCorp Vault**
```python
import hvac

client = hvac.Client(url='https://vault.example.com')
client.auth.approle.login(role_id=ROLE_ID, secret_id=SECRET_ID)

secrets = client.secrets.kv.v2.read_secret_version(
    path='finmodel/production'
)
```

### Secret Rotation

```python
# Automatic secret rotation (every 90 days)
# AWS Lambda or Kubernetes CronJob

import boto3

def rotate_database_password():
    # Generate new password
    new_password = generate_secure_password()

    # Update database
    db_client.update_password(new_password)

    # Update secret
    secrets_client.put_secret_value(
        SecretId='finmodel/database-password',
        SecretString=new_password
    )

    # Notify operator
    send_notification("Database password rotated")

# Schedule: every 90 days
```

---

## CI/CD Pipeline

### GitHub Actions Workflow

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches:
      - main
      - staging
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Run linters
        run: |
          ruff check .
          black --check .
          mypy .

      - name: Run unit tests
        run: pytest tests/unit/ -v --cov

      - name: Start Supabase (for integration tests)
        run: docker-compose up -d supabase

      - name: Run integration tests
        run: pytest tests/integration/ -v

      - name: Upload coverage
        uses: codecov/codecov-action@v3

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main' || github.ref == 'refs/heads/staging'
    steps:
      - uses: actions/checkout@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2

      - name: Login to Container Registry
        uses: docker/login-action@v2
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push API image
        uses: docker/build-push-action@v4
        with:
          context: .
          file: Dockerfile
          push: true
          tags: ghcr.io/yourorg/finmodel-api:${{ github.sha }}

      - name: Build and push Worker image
        uses: docker/build-push-action@v4
        with:
          context: .
          file: Dockerfile.worker
          push: true
          tags: ghcr.io/yourorg/finmodel-worker:${{ github.sha }}

  deploy-staging:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/staging'
    environment: staging
    steps:
      - name: Deploy to staging
        run: |
          # Update Kubernetes deployment
          kubectl set image deployment/finmodel-api \
            api=ghcr.io/yourorg/finmodel-api:${{ github.sha }} \
            --namespace=finmodel-staging

          # Wait for rollout
          kubectl rollout status deployment/finmodel-api \
            --namespace=finmodel-staging

  deploy-production:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    environment: production
    steps:
      - name: Manual approval required
        uses: trstringer/manual-approval@v1
        with:
          approvers: engineering-leads

      - name: Deploy to production
        run: |
          # Blue-green deployment
          kubectl apply -f k8s/production/deployment-green.yaml

          # Wait for health check
          sleep 30

          # Switch traffic
          kubectl patch service finmodel-api \
            -p '{"spec":{"selector":{"version":"green"}}}'

          # Wait and verify
          sleep 60

          # Delete old blue deployment
          kubectl delete deployment finmodel-api-blue
```

### Deployment Strategies

**1. Rolling Update (Default)**
- Gradually replace old pods with new ones
- Zero downtime
- Easy rollback

**2. Blue-Green**
- Run two identical environments
- Switch traffic atomically
- Instant rollback
- Higher cost (2x resources during deployment)

**3. Canary**
- Deploy to small % of traffic first
- Monitor metrics
- Gradually increase %
- Rollback if issues detected

```yaml
# Canary with Flagger (example)
apiVersion: flagger.app/v1beta1
kind: Canary
metadata:
  name: finmodel-api
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: finmodel-api
  service:
    port: 80
  analysis:
    interval: 1m
    threshold: 5
    maxWeight: 50
    stepWeight: 10
    metrics:
    - name: request-success-rate
      thresholdRange:
        min: 99
    - name: request-duration
      thresholdRange:
        max: 500
```

---

## Database Migrations

### Migration Workflow

```bash
# Create new migration
alembic revision -m "add_xyz_table"

# Edit migration file
# apps/api/app/db/migrations/versions/0006_add_xyz.py

# Apply migration (development)
alembic upgrade head

# Apply migration (production)
# Via deployment pipeline or manual:
kubectl exec -it finmodel-api-xxx -- alembic upgrade head
```

### Migration Best Practices

1. **Always test migrations in staging first**
2. **Make migrations reversible** (provide `downgrade()`)
3. **Large data migrations**: run as background job, not blocking deployment
4. **Breaking schema changes**: use multi-step deployment
   - Step 1: Add new column (optional)
   - Step 2: Write to both old and new columns
   - Step 3: Backfill data
   - Step 4: Switch reads to new column
   - Step 5: Drop old column

### Zero-Downtime Migration Example

```python
# Bad: Breaks running code
def upgrade():
    op.drop_column('runs', 'old_status')
    op.add_column('runs', sa.Column('new_status', sa.String(50)))

# Good: Multi-step
# Migration 1
def upgrade():
    op.add_column('runs', sa.Column('new_status', sa.String(50), nullable=True))

# Deploy code that writes to both columns

# Migration 2 (later)
def upgrade():
    # Backfill
    op.execute("UPDATE runs SET new_status = old_status WHERE new_status IS NULL")
    op.alter_column('runs', 'new_status', nullable=False)

# Deploy code that reads from new_status

# Migration 3 (even later)
def upgrade():
    op.drop_column('runs', 'old_status')
```

---

## Backup & Disaster Recovery

### Backup Strategy

**Database:**
- **Automated daily backups** (Supabase handles this)
- **Point-in-time recovery** (PITR) - 7 days
- **Manual snapshots** before major changes
- **Off-site backup** to S3 (for extra safety)
- **Retention:** 7 daily, 4 weekly, 12 monthly

```bash
# Manual backup
pg_dump -h prod-db.supabase.co -U postgres -d finmodel \
  | gzip > backup_$(date +%Y%m%d).sql.gz

# Upload to S3
aws s3 cp backup_$(date +%Y%m%d).sql.gz \
  s3://finmodel-backups/database/
```

**Artifact Storage (Supabase Storage):**
- **Versioning enabled** (objects not truly deleted)
- **Cross-region replication** (optional for production)
- **Backup to S3** (weekly sync)

```bash
# Sync Supabase Storage to S3 backup
rclone sync supabase:finmodel-artifacts s3:finmodel-backup/artifacts
```

**Configuration & Secrets:**
- **Version controlled** (except secrets)
- **Secrets backed up** in AWS Secrets Manager (versioned)

### Recovery Objectives

| Component | RTO (Recovery Time) | RPO (Data Loss) |
|---|---|---|
| API Service | 5 minutes | 0 (stateless) |
| Database | 15 minutes | <1 hour (PITR) |
| Artifact Storage | 30 minutes | <24 hours (daily backup) |
| Full System | 1 hour | <1 hour |

### Disaster Recovery Procedures

**Scenario 1: Database Corruption**
```bash
# 1. Identify last good point-in-time
# 2. Restore from PITR
supabase db restore --timestamp "2026-02-11T09:00:00Z"

# 3. Verify data integrity
psql -h restored-db -U postgres -c "SELECT COUNT(*) FROM model_baselines"

# 4. Update DNS/connection string to restored DB
# 5. Monitor for issues
```

**Scenario 2: Region Outage**
```bash
# If using multi-region:
# 1. Failover DNS to secondary region
# 2. Promote read-replica to primary
# 3. Redirect traffic

# If single region:
# 1. Deploy to new region from backups
# 2. Restore database from S3 backup
# 3. Restore artifacts from S3 backup
# 4. Update DNS
```

**Scenario 3: Ransomware / Data Deletion**
```bash
# 1. Immediately revoke all API keys and credentials
# 2. Assess scope of damage
# 3. Restore from immutable backup (S3 with versioning)
# 4. Rebuild system in clean environment
# 5. Rotate all secrets
# 6. Audit access logs
```

### Disaster Recovery Testing

**Schedule:** Quarterly DR drill

**Checklist:**
- [ ] Restore database from backup
- [ ] Restore artifacts from S3
- [ ] Deploy application to clean environment
- [ ] Verify end-to-end functionality
- [ ] Document time to recovery
- [ ] Identify and fix gaps

---

## Monitoring & Alerting (Reference)

See [OBSERVABILITY_SPEC.md](./OBSERVABILITY_SPEC.md) for details.

**Key integration points:**
- Prometheus metrics exposed at `/metrics`
- Structured logs to CloudWatch / Datadog
- Health checks at `/api/v1/health/*`
- Alerting via PagerDuty for critical issues

---

## Operational Runbooks

### Runbook: High Memory Usage

**Symptoms:** Memory usage >85%, OOM kills

**Investigation:**
```bash
# Check pod memory
kubectl top pods -n finmodel

# Check for memory leaks
kubectl exec -it finmodel-api-xxx -- python -m memory_profiler

# Review recent changes
git log --since="2 days ago"
```

**Remediation:**
1. Restart affected pods (quick fix)
2. Scale up resources (medium-term)
3. Fix memory leak in code (long-term)

### Runbook: Database Connection Pool Exhausted

**Symptoms:** `ERR_STOR_CONNECTION_FAILED` errors, 503s

**Investigation:**
```bash
# Check active connections
SELECT count(*) FROM pg_stat_activity WHERE datname = 'finmodel';

# Check pool metrics
curl http://finmodel-api/metrics | grep db_connection_pool
```

**Remediation:**
1. Increase pool size (config change)
2. Investigate slow queries holding connections
3. Add connection timeout

### Runbook: All LLM Providers Failing

**Symptoms:** `ERR_LLM_ALL_PROVIDERS_FAILED` errors

**Investigation:**
1. Check provider status pages (Anthropic, OpenAI)
2. Review error logs for specific errors
3. Test API keys manually

**Remediation:**
1. If provider outage: enable graceful degradation (allow manual draft editing)
2. If key issue: rotate API keys
3. If rate limit: adjust routing policy or upgrade plan

---

## Scaling Guide

### Vertical Scaling (Scale Up)

Increase resources per pod:
```yaml
resources:
  requests:
    cpu: 1000m → 2000m
    memory: 2Gi → 4Gi
  limits:
    cpu: 2000m → 4000m
    memory: 4Gi → 8Gi
```

**When:** Single-pod performance is bottleneck

### Horizontal Scaling (Scale Out)

Increase number of pods:
```bash
kubectl scale deployment finmodel-api --replicas=10
```

**When:** Total throughput is bottleneck

### Database Scaling

**Read Replicas:** For read-heavy workloads
```
1 Primary (writes) + 2 Read Replicas (reads)
```

**Connection Pooling:** Use PgBouncer
```
API (100 connections) → PgBouncer (10 connections) → Database
```

**Vertical Scaling:** Increase database instance size

### Cache Scaling

**Redis Cluster:** For high cache volume
```
3 master nodes, 3 replicas = 6 total nodes
```

---

## Cost Optimization

### Right-Sizing

- Monitor actual resource usage
- Adjust requests/limits based on P95
- Use burstable instances for variable load

### Auto-Scaling

```yaml
HorizontalPodAutoscaler:
  minReplicas: 2  # Cost floor
  maxReplicas: 10  # Cost ceiling
  targetCPU: 70%
```

### Spot Instances

Use for non-critical workloads:
- Development environment
- Background workers (with graceful shutdown)

### Reserved Instances

For production stable baseline:
- Reserve 2 API pods (always running)
- Use spot/on-demand for auto-scale

### Storage Tiering

- Hot data (active baselines): SSD
- Warm data (recent archives): HDD
- Cold data (>90 days): S3 Glacier

---

## Deployment Checklist

### Pre-Deployment
- [ ] All tests passing (unit, integration, E2E)
- [ ] Staging deployment successful
- [ ] Database migrations tested
- [ ] Secrets rotated (if needed)
- [ ] Monitoring dashboard reviewed
- [ ] On-call engineer notified

### Deployment
- [ ] Deploy during low-traffic window
- [ ] Monitor metrics in real-time
- [ ] Run smoke tests post-deployment
- [ ] Verify health checks green
- [ ] Check error rates (<1%)

### Post-Deployment
- [ ] Monitor for 1 hour
- [ ] Review logs for anomalies
- [ ] Verify key user flows
- [ ] Update status page
- [ ] Document any issues

### Rollback Criteria
- Error rate >5% for 5 minutes
- Critical functionality broken
- Database migration failed
- Security vulnerability introduced
