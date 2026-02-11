# Performance & Scalability Specification
**Date:** 2026-02-11

## Overview
FinModel is designed for fast, responsive financial modeling with concurrent multi-tenant usage. This document defines performance targets, optimization strategies, and scalability approach.

## Performance Targets (SLAs)

### API Response Times (Target: P95)

| Endpoint Category | P50 | P95 | P99 | Timeout |
|---|---|---|---|---|
| Authentication | 50ms | 150ms | 300ms | 2s |
| List operations (baselines, runs, drafts) | 100ms | 300ms | 500ms | 5s |
| Read single resource | 50ms | 200ms | 400ms | 3s |
| Create/Update (non-compute) | 150ms | 400ms | 800ms | 10s |
| Engine - Deterministic run (12mo) | 200ms | 500ms | 1s | 30s |
| Engine - Deterministic run (60mo) | 500ms | 1.5s | 3s | 60s |
| Monte Carlo - Quick (100 sims) | 2s | 5s | 8s | 30s |
| Monte Carlo - Standard (1k sims) | 8s | 20s | 30s | 120s |
| Monte Carlo - Full (10k sims) | 60s | 150s | 240s | 600s |
| LLM chat (draft) | 2s | 8s | 15s | 30s |
| Memo generation | 3s | 10s | 20s | 60s |
| ERP sync | 5s | 15s | 30s | 120s |

### Throughput Targets

| Metric | Target | Measured Over |
|---|---|---|
| Concurrent users per instance | 100+ | N/A |
| API requests per second (total) | 500+ | Per app instance |
| Deterministic runs per minute | 120+ | Per app instance |
| MC runs (1k sims) per minute | 10+ | Per app instance |
| LLM calls per minute | 50+ | Tenant-level rate limit |
| Database queries per second | 1000+ | Database level |

### Database Query Performance

| Query Type | P95 Latency | Max Rows | Index Required |
|---|---|---|---|
| Baseline by ID | <10ms | 1 | PK index |
| List baselines (tenant) | <50ms | 100 | tenant_id + created_at |
| Run by ID | <10ms | 1 | PK index |
| List runs (baseline) | <50ms | 1000 | baseline_id + created_at |
| Artifact load from storage | <200ms | N/A | Supabase Storage |
| Full-text search (memos) | <500ms | 100 | GIN index |

## Engine Performance Optimization

### Calculation Graph Optimization

```python
# Complexity Limits (enforced at validation)
MAX_BLUEPRINT_NODES = 500
MAX_BLUEPRINT_EDGES = 1000
MAX_FORMULAS = 1000
MAX_HORIZON_MONTHS = 120
MAX_FORMULA_DEPTH = 10  # Nested function calls

# Performance Tracking
@dataclass
class EnginePerformanceMetrics:
    graph_build_ms: int
    topo_sort_ms: int
    time_loop_ms: int
    statement_gen_ms: int
    total_execution_ms: int
    nodes_evaluated: int
    formulas_executed: int
```

### Vectorization Strategy

Use NumPy for time-series operations:

```python
# Instead of loop
# for t in range(horizon):
#     revenue[t] = price * quantity[t]

# Vectorized
import numpy as np
revenue = price * quantity  # Element-wise multiplication

# Cumulative operations
cumulative_capex = np.cumsum(capex_schedule)
```

### Expression Evaluation Caching

```python
# Cache compiled expression ASTs
@lru_cache(maxsize=1000)
def compile_formula(expression: str) -> AST:
    return parse_expression(expression)

# Memoize repeated calculations within same run
@lru_cache(maxsize=500)
def evaluate_constant_expression(expr_hash: str, **kwargs):
    return eval_ast(cached_ast, kwargs)
```

### Monte Carlo Optimization

```python
# Parallel simulation with ProcessPoolExecutor
from concurrent.futures import ProcessPoolExecutor
import numpy as np

def run_simulation(model_config, seed, sim_id):
    """Single simulation (can be pickled for multiprocessing)"""
    rng = np.random.default_rng(seed + sim_id)
    sampled_assumptions = sample_distributions(model_config, rng)
    return run_engine(model_config, sampled_assumptions)

async def monte_carlo_parallel(model_config, num_sims, seed):
    """Parallel MC execution"""
    with ProcessPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(run_simulation, model_config, seed, i)
            for i in range(num_sims)
        ]
        results = [f.result() for f in futures]
    return aggregate_results(results)

# Optimization: Pre-allocate result arrays
results = np.zeros((num_sims, horizon_months, num_metrics))
```

### Background Job Queue for Heavy Operations

```python
# Use Celery or similar for async execution
from celery import Celery

@celery_app.task
def execute_mc_run(run_id: str, model_config: dict, num_sims: int, seed: int):
    """Execute MC run asynchronously"""
    try:
        results = monte_carlo_parallel(model_config, num_sims, seed)
        await update_run_status(run_id, "succeeded", results)
    except Exception as e:
        await update_run_status(run_id, "failed", error=str(e))
        raise

# API endpoint returns immediately
@router.post("/api/v1/runs")
async def create_run(run_input: CreateRunInput):
    run = await create_run_record(run_input)

    if run_input.mc_enabled and run_input.num_simulations > 1000:
        # Heavy MC: queue as background job
        execute_mc_run.delay(run.run_id, run_input.model_config, ...)
        return {"run_id": run.run_id, "status": "queued"}
    else:
        # Light run: synchronous
        results = await run_engine_sync(run_input)
        return {"run_id": run.run_id, "status": "succeeded", "results": results}
```

## Database Optimization

### Indexing Strategy

```sql
-- Tenant-scoped queries (most common)
CREATE INDEX idx_baselines_tenant_created ON model_baselines(tenant_id, created_at DESC);
CREATE INDEX idx_runs_baseline_created ON runs(baseline_id, created_at DESC);
CREATE INDEX idx_drafts_tenant_status ON draft_sessions(tenant_id, status, created_at DESC);

-- Lookup by ID (implicit primary key indexes)
-- PK indexes: model_baselines(baseline_id), runs(run_id), draft_sessions(draft_session_id)

-- Status filtering
CREATE INDEX idx_runs_status ON runs(status) WHERE status IN ('queued', 'running');

-- Full-text search (memos)
CREATE INDEX idx_memos_search ON memo_packs USING GIN(to_tsvector('english', content));

-- Composite indexes for common joins
CREATE INDEX idx_runs_tenant_baseline ON runs(tenant_id, baseline_id, created_at DESC);
```

### Connection Pooling

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Connection pool configuration
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,           # Base connections
    max_overflow=10,        # Additional on-demand
    pool_timeout=30,        # Wait for connection
    pool_recycle=3600,      # Recycle after 1h
    pool_pre_ping=True,     # Verify connection health
    echo=False,             # Disable SQL logging in prod
)

SessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)
```

### Query Optimization Patterns

```python
# Use select_related / joinedload to avoid N+1
from sqlalchemy.orm import selectinload

async def get_baseline_with_runs(baseline_id: str):
    query = (
        select(ModelBaseline)
        .options(selectinload(ModelBaseline.runs))
        .where(ModelBaseline.baseline_id == baseline_id)
    )
    result = await session.execute(query)
    return result.scalar_one()

# Pagination for large lists
async def list_runs(baseline_id: str, offset: int = 0, limit: int = 50):
    query = (
        select(Run)
        .where(Run.baseline_id == baseline_id)
        .order_by(Run.created_at.desc())
        .offset(offset)
        .limit(min(limit, 100))  # Cap at 100
    )
    result = await session.execute(query)
    return result.scalars().all()

# Use COUNT efficiently
async def count_runs(baseline_id: str) -> int:
    query = select(func.count()).select_from(Run).where(Run.baseline_id == baseline_id)
    result = await session.execute(query)
    return result.scalar_one()
```

### Read Replicas

```python
# Write to primary
async def create_baseline(baseline: ModelBaseline):
    async with SessionLocal() as session:  # Primary DB
        session.add(baseline)
        await session.commit()
        return baseline

# Read from replica
async def get_baseline(baseline_id: str):
    async with ReadReplicaSession() as session:  # Read replica
        query = select(ModelBaseline).where(...)
        result = await session.execute(query)
        return result.scalar_one_or_none()
```

## Caching Strategy

### Cache Layers

1. **Application Cache** (Redis): API responses, compiled formulas
2. **Database Query Cache**: Postgres shared_buffers
3. **CDN Cache**: Static assets (frontend)
4. **Browser Cache**: API responses with ETags

### Redis Cache Configuration

```python
from redis.asyncio import Redis
from functools import wraps
import json

redis_client = Redis(
    host=REDIS_HOST,
    port=6379,
    db=0,
    decode_responses=True,
    max_connections=50
)

def cache(ttl: int = 300):
    """Cache decorator with TTL in seconds"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{hash((args, frozenset(kwargs.items())))}"
            cached = await redis_client.get(cache_key)

            if cached:
                return json.loads(cached)

            result = await func(*args, **kwargs)
            await redis_client.setex(cache_key, ttl, json.dumps(result))
            return result
        return wrapper
    return decorator

# Usage
@cache(ttl=600)  # 10 minutes
async def get_baseline_summary(baseline_id: str):
    # Expensive query
    ...
```

### Cache Invalidation

```python
# Invalidate on write
async def update_baseline(baseline_id: str, updates: dict):
    await db.update(baseline_id, updates)
    await redis_client.delete(f"get_baseline_summary:{baseline_id}")
    await redis_client.delete(f"list_runs:{baseline_id}")

# Cache tags for bulk invalidation
async def create_run(baseline_id: str, run_data: dict):
    run = await db.create_run(run_data)
    # Invalidate all caches tagged with baseline_id
    await invalidate_cache_tag(f"baseline:{baseline_id}")
    return run
```

### Cache Warming

```python
# Pre-populate cache for frequently accessed data
async def warm_cache_for_tenant(tenant_id: str):
    baselines = await db.get_active_baselines(tenant_id)
    for baseline in baselines:
        await cache_baseline_summary(baseline.baseline_id)
        await cache_recent_runs(baseline.baseline_id)
```

## API Rate Limiting

### Rate Limit Configuration

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# Default limits
DEFAULT_RATE_LIMIT = "100/minute"
LLM_RATE_LIMIT = "20/minute"      # Per tenant
MC_RATE_LIMIT = "10/minute"       # Per tenant
SYNC_RATE_LIMIT = "5/minute"      # Per tenant

# Apply to routes
@router.post("/api/v1/drafts/{id}/chat")
@limiter.limit(LLM_RATE_LIMIT)
async def chat(request: Request, id: str, message: str):
    ...

# Tenant-based limiting
def get_tenant_id(request: Request) -> str:
    return request.state.tenant_id

tenant_limiter = Limiter(key_func=get_tenant_id)

@router.post("/api/v1/runs")
@tenant_limiter.limit("50/minute")  # Per tenant
async def create_run(request: Request, run_input: CreateRunInput):
    ...
```

### Plan-Based Limits

```python
async def enforce_plan_limits(tenant_id: str, operation: str):
    subscription = await get_subscription(tenant_id)
    usage = await get_current_usage(tenant_id)

    limits = subscription.plan.limits

    if operation == "llm_call":
        if usage.llm_tokens_monthly >= limits.llm_tokens_monthly:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "ERR_LLM_QUOTA_EXCEEDED",
                    "message": f"Monthly LLM token limit reached",
                    "current": usage.llm_tokens_monthly,
                    "limit": limits.llm_tokens_monthly
                }
            )

    elif operation == "mc_run":
        if usage.mc_simulations_monthly >= limits.mc_simulations_monthly:
            raise HTTPException(status_code=429, ...)
```

## Storage Performance

### Artifact Storage Optimization

```python
# Compression for large artifacts
import gzip
import json

async def save_artifact_compressed(tenant_id: str, artifact: dict):
    json_bytes = json.dumps(artifact).encode('utf-8')

    if len(json_bytes) > 100_000:  # >100KB
        compressed = gzip.compress(json_bytes, compresslevel=6)
        await storage.upload(path, compressed, content_type="application/gzip")
    else:
        await storage.upload(path, json_bytes, content_type="application/json")

# Parallel uploads for multi-artifact operations
from asyncio import gather

async def save_run_artifacts(run_id: str, artifacts: dict):
    await gather(
        save_artifact(run_id, "statements", artifacts["statements"]),
        save_artifact(run_id, "kpis", artifacts["kpis"]),
        save_artifact(run_id, "mc_results", artifacts["mc_results"])
    )
```

### Presigned URLs for Large Downloads

```python
# Avoid proxying large files through API
@router.get("/api/v1/memos/{id}/download")
async def download_memo(id: str, format: str):
    memo = await get_memo(id)
    artifact_path = f"memos/{id}/output.{format}"

    # Generate presigned URL (valid for 5 minutes)
    presigned_url = await storage.create_presigned_url(
        artifact_path,
        expires_in=300
    )

    return {"download_url": presigned_url}
```

## LLM Performance Optimization

### Request Batching

```python
# Batch multiple LLM requests when possible
async def batch_llm_requests(requests: list[LLMRequest]) -> list[LLMResponse]:
    # Group by provider and model
    grouped = group_by(requests, lambda r: (r.provider, r.model))

    responses = []
    for (provider, model), batch in grouped.items():
        # Provider-specific batching
        if provider.supports_batch:
            batch_response = await provider.batch_complete(batch)
            responses.extend(batch_response)
        else:
            # Parallel individual requests
            batch_responses = await gather(*[provider.complete(r) for r in batch])
            responses.extend(batch_responses)

    return responses
```

### Response Streaming

```python
# Stream LLM responses for better UX
from fastapi.responses import StreamingResponse

@router.post("/api/v1/drafts/{id}/chat")
async def chat_stream(id: str, message: str):
    async def generate():
        async for chunk in llm_provider.stream_complete(message):
            yield f"data: {json.dumps(chunk)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

## Horizontal Scaling

### Stateless API Design

All API instances are stateless:
- No in-memory session state
- Session data in Redis or database
- No local file storage (use Supabase Storage)
- No sticky sessions required

### Load Balancer Configuration

```yaml
# Example ALB configuration
HealthCheck:
  Path: /api/v1/health
  Interval: 30
  Timeout: 5
  HealthyThreshold: 2
  UnhealthyThreshold: 3

TargetGroup:
  DeregistrationDelay: 30  # Drain connections
  Stickiness: false        # No session affinity needed

AutoScaling:
  MinInstances: 2
  MaxInstances: 10
  TargetCPU: 70%
  TargetMemory: 80%
  ScaleUpCooldown: 120s
  ScaleDownCooldown: 300s
```

### Database Scaling

```
Primary (writes)
   ↓
Read Replica 1 ←→ API Instances (reads)
Read Replica 2 ←→ API Instances (reads)

Connection Pool per API Instance: 20 connections
Total connections with 5 API instances: 100
Database max_connections: 200 (50% headroom)
```

## Performance Monitoring

### Metrics Collection

```python
from prometheus_client import Counter, Histogram, Gauge

# API metrics
api_requests_total = Counter(
    "api_requests_total",
    "Total API requests",
    ["method", "endpoint", "status"]
)

api_request_duration = Histogram(
    "api_request_duration_seconds",
    "API request duration",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1, 2, 5, 10, 30]
)

# Engine metrics
engine_execution_duration = Histogram(
    "engine_execution_duration_seconds",
    "Engine execution time",
    ["template", "horizon_months"],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60]
)

active_runs = Gauge("active_runs", "Currently executing runs")

# Middleware to track
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start

    api_requests_total.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()

    api_request_duration.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)

    return response
```

### Performance Dashboard

Key metrics to display:
- API P50/P95/P99 latency by endpoint
- Error rate (errors/min, errors by type)
- Throughput (requests/sec, runs/min)
- Engine execution time distribution
- LLM call latency and success rate
- Database connection pool utilization
- Cache hit rate
- Background job queue depth

### Performance Testing

```python
# Load test with Locust
from locust import HttpUser, task, between

class FinModelUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        # Login
        response = self.client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "password"
        })
        self.token = response.json()["access_token"]
        self.client.headers["Authorization"] = f"Bearer {self.token}"

    @task(3)
    def list_baselines(self):
        self.client.get("/api/v1/baselines")

    @task(2)
    def get_baseline(self):
        self.client.get("/api/v1/baselines/bl_001")

    @task(1)
    def create_run(self):
        self.client.post("/api/v1/runs", json={
            "baseline_id": "bl_001",
            "mc_enabled": False
        })

# Run: locust -f load_test.py --users 100 --spawn-rate 10
```

## Optimization Checklist

### Phase 1
- [ ] Database indexes on all foreign keys
- [ ] Connection pooling configured
- [ ] API response time logging
- [ ] Engine execution profiling
- [ ] Query optimization for N+1 issues

### Phase 2
- [ ] Redis cache for LLM routing policies
- [ ] LLM request timeout and retry
- [ ] Background job queue for heavy LLM tasks

### Phase 3
- [ ] Async MC execution with progress tracking
- [ ] NumPy vectorization for time-series
- [ ] Parallel simulation execution

### Phase 4
- [ ] ERP sync rate limiting
- [ ] Plan-based usage enforcement
- [ ] Billing usage aggregation optimization

### Phase 5
- [ ] Presigned URLs for large downloads
- [ ] Artifact compression for archives
- [ ] Memo generation streaming

## Performance Regression Prevention

### Automated Performance Tests in CI

```yaml
# .github/workflows/performance.yml
performance-test:
  - Run baseline performance suite
  - Compare against previous build
  - Fail if P95 latency regressed >20%
  - Fail if throughput decreased >10%
```

### Performance Budget

```json
{
  "budgets": [
    {"endpoint": "/api/v1/baselines", "p95_ms": 300},
    {"endpoint": "/api/v1/runs", "p95_ms": 500},
    {"endpoint": "/api/v1/drafts/{id}/chat", "p95_ms": 8000},
    {"engine": "deterministic_12mo", "p95_ms": 500},
    {"engine": "mc_1k_sims", "p95_ms": 20000}
  ]
}
```
