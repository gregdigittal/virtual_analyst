# Observability & Monitoring Specification
**Date:** 2026-02-11

## Overview
FinModel implements comprehensive observability through structured logging, metrics collection, distributed tracing, and proactive alerting. Every component is instrumented for debugging, performance analysis, and operational health monitoring.

## The Three Pillars

### 1. Logs (What happened)
- Structured JSON logs with correlation IDs
- Centralized log aggregation
- Searchable by tenant, user, operation, error code

### 2. Metrics (How much / how fast)
- Time-series data (counters, gauges, histograms)
- Real-time dashboards
- Alert thresholds

### 3. Traces (Where time was spent)
- Distributed tracing across services
- Request flow visualization
- Performance bottleneck identification

---

## Structured Logging

### Log Format

Every log entry uses this JSON structure:

```json
{
  "timestamp": "2026-02-11T10:30:45.123Z",
  "level": "INFO",
  "service": "api",
  "component": "engine",
  "message": "Engine execution completed",
  "correlation_id": "req_abc123xyz",
  "trace_id": "trace_001",
  "span_id": "span_042",
  "tenant_id": "t_001",
  "user_id": "u_042",
  "operation": "run_engine",
  "duration_ms": 247,
  "context": {
    "baseline_id": "bl_001",
    "run_id": "run_123",
    "horizon_months": 12,
    "num_nodes": 87,
    "mc_enabled": false
  },
  "tags": ["engine", "deterministic"],
  "error": null
}
```

### Log Levels

| Level | Usage | Examples |
|---|---|---|
| **DEBUG** | Detailed diagnostic (dev only) | Variable values, algorithm steps |
| **INFO** | Normal operations | Run started, API request received |
| **WARNING** | Unexpected but handled | Integrity check warnings, slow queries |
| **ERROR** | Operation failed | Validation failed, LLM timeout |
| **CRITICAL** | System failure | Database down, all providers failed |

### Logging by Component

```python
import structlog
from contextvars import ContextVar

# Context variables for correlation
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default=None)
tenant_id_var: ContextVar[str] = ContextVar("tenant_id", default=None)

# Configure structlog
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger()

# Bind context at request start
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    correlation_id_var.set(correlation_id)

    if hasattr(request.state, "tenant_id"):
        tenant_id_var.set(request.state.tenant_id)

    # Bind to all logs in this context
    structlog.contextvars.bind_contextvars(
        correlation_id=correlation_id,
        tenant_id=request.state.tenant_id if hasattr(request.state, "tenant_id") else None,
        user_id=request.state.user_id if hasattr(request.state, "user_id") else None
    )

    response = await call_next(request)
    return response

# Usage in application code
async def execute_run(run_id: str, model_config: dict):
    log = logger.bind(
        operation="execute_run",
        run_id=run_id,
        baseline_id=model_config["baseline_id"]
    )

    log.info("Starting run execution")

    try:
        start = time.time()
        result = await engine.run(model_config)
        duration_ms = int((time.time() - start) * 1000)

        log.info(
            "Run execution completed",
            duration_ms=duration_ms,
            num_periods=result["num_periods"],
            tags=["engine", "success"]
        )
        return result

    except Exception as e:
        log.error(
            "Run execution failed",
            error_type=type(e).__name__,
            error_message=str(e),
            stack_trace=traceback.format_exc(),
            tags=["engine", "failure"]
        )
        raise
```

### Log Aggregation

**Stack:** CloudWatch Logs / Elasticsearch / Datadog / Grafana Loki

**Configuration:**
```yaml
log_aggregation:
  destination: cloudwatch  # or elasticsearch, datadog
  retention_days: 30
  archive_to_s3: true
  archive_retention_days: 90

  filters:
    # Don't log sensitive data
    exclude_patterns:
      - "password"
      - "api_key"
      - "secret"
      - "token"

  # Sampling (optional, for very high volume)
  sampling:
    error_logs: 100%      # Never sample errors
    warning_logs: 100%
    info_logs: 10%        # Sample INFO in production
    debug_logs: 0%        # Never send DEBUG to aggregation
```

### Log Searching

Common queries:
```
# All errors for a tenant
level:ERROR AND tenant_id:t_001

# Slow operations
duration_ms:>1000

# LLM failures
component:llm AND level:ERROR

# Trace a specific request
correlation_id:req_abc123xyz

# Engine execution times
operation:run_engine | stats avg(duration_ms), p95(duration_ms)
```

---

## Metrics Collection

### Metrics Stack

**Tools:** Prometheus + Grafana (or CloudWatch / Datadog)

### Metric Categories

#### 1. API Metrics

```python
from prometheus_client import Counter, Histogram, Gauge, Info

# Request counters
api_requests_total = Counter(
    "api_requests_total",
    "Total API requests",
    ["method", "endpoint", "status_code", "tenant_id"]
)

# Latency histograms
api_request_duration_seconds = Histogram(
    "api_request_duration_seconds",
    "API request duration",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60]
)

# Active requests
api_requests_active = Gauge(
    "api_requests_active",
    "Currently active API requests"
)

# Error rate
api_errors_total = Counter(
    "api_errors_total",
    "Total API errors",
    ["endpoint", "error_code", "severity"]
)

# Middleware to collect
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    api_requests_active.inc()
    start = time.time()

    try:
        response = await call_next(request)
        status = response.status_code
    except Exception as e:
        status = 500
        api_errors_total.labels(
            endpoint=request.url.path,
            error_code=getattr(e, "code", "ERR_SYS_INTERNAL_ERROR"),
            severity="ERROR"
        ).inc()
        raise
    finally:
        duration = time.time() - start
        api_requests_active.dec()

        api_requests_total.labels(
            method=request.method,
            endpoint=request.url.path,
            status_code=status,
            tenant_id=getattr(request.state, "tenant_id", "unknown")
        ).inc()

        api_request_duration_seconds.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)

    return response
```

#### 2. Engine Metrics

```python
# Engine execution
engine_executions_total = Counter(
    "engine_executions_total",
    "Total engine executions",
    ["template", "mc_enabled", "status"]
)

engine_execution_duration_seconds = Histogram(
    "engine_execution_duration_seconds",
    "Engine execution time",
    ["template", "horizon_months", "mc_enabled"],
    buckets=[0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60, 120, 300]
)

engine_nodes_evaluated = Histogram(
    "engine_nodes_evaluated",
    "Number of nodes evaluated per run",
    buckets=[10, 50, 100, 200, 500, 1000]
)

# Monte Carlo specific
mc_simulations_total = Counter(
    "mc_simulations_total",
    "Total MC simulations executed"
)

mc_simulation_duration_seconds = Histogram(
    "mc_simulation_duration_seconds",
    "MC simulation time",
    ["num_simulations"],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600]
)

# Usage in engine
async def run_engine(model_config: dict, mc_config: dict = None):
    start = time.time()
    mc_enabled = mc_config is not None

    try:
        result = await execute_engine(model_config, mc_config)

        engine_executions_total.labels(
            template=model_config.get("template_id", "unknown"),
            mc_enabled=mc_enabled,
            status="success"
        ).inc()

        duration = time.time() - start
        engine_execution_duration_seconds.labels(
            template=model_config.get("template_id"),
            horizon_months=model_config["metadata"]["horizon_months"],
            mc_enabled=mc_enabled
        ).observe(duration)

        engine_nodes_evaluated.observe(result["nodes_evaluated"])

        return result

    except Exception as e:
        engine_executions_total.labels(
            template=model_config.get("template_id", "unknown"),
            mc_enabled=mc_enabled,
            status="failure"
        ).inc()
        raise
```

#### 3. LLM Metrics

```python
llm_calls_total = Counter(
    "llm_calls_total",
    "Total LLM API calls",
    ["provider", "model", "task_label", "status"]
)

llm_call_duration_seconds = Histogram(
    "llm_call_duration_seconds",
    "LLM call latency",
    ["provider", "model"],
    buckets=[0.5, 1, 2, 5, 10, 15, 30, 60]
)

llm_tokens_total = Counter(
    "llm_tokens_total",
    "Total tokens consumed",
    ["provider", "model", "token_type"]  # token_type: prompt, completion
)

llm_cost_usd_total = Counter(
    "llm_cost_usd_total",
    "Estimated LLM cost in USD",
    ["provider", "model", "tenant_id"]
)

llm_provider_errors_total = Counter(
    "llm_provider_errors_total",
    "LLM provider errors",
    ["provider", "error_type"]
)

# After LLM call
def record_llm_metrics(response: LLMResponse, task_label: str, status: str):
    llm_calls_total.labels(
        provider=response.provider,
        model=response.model,
        task_label=task_label,
        status=status
    ).inc()

    llm_call_duration_seconds.labels(
        provider=response.provider,
        model=response.model
    ).observe(response.latency_ms / 1000)

    llm_tokens_total.labels(
        provider=response.provider,
        model=response.model,
        token_type="prompt"
    ).inc(response.tokens.prompt_tokens)

    llm_tokens_total.labels(
        provider=response.provider,
        model=response.model,
        token_type="completion"
    ).inc(response.tokens.completion_tokens)

    llm_cost_usd_total.labels(
        provider=response.provider,
        model=response.model,
        tenant_id=response.tenant_id
    ).inc(response.cost_estimate_usd)
```

#### 4. Database Metrics

```python
db_queries_total = Counter(
    "db_queries_total",
    "Total database queries",
    ["operation", "table"]
)

db_query_duration_seconds = Histogram(
    "db_query_duration_seconds",
    "Database query duration",
    ["operation", "table"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5]
)

db_connections_active = Gauge(
    "db_connections_active",
    "Active database connections"
)

db_connection_pool_size = Gauge(
    "db_connection_pool_size",
    "Connection pool size"
)

db_connection_pool_overflow = Gauge(
    "db_connection_pool_overflow",
    "Connection pool overflow count"
)

# SQLAlchemy event listeners
from sqlalchemy import event

@event.listens_for(engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._query_start_time = time.time()

@event.listens_for(engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    duration = time.time() - context._query_start_time

    # Extract table name (simplified)
    table = extract_table_name(statement)
    operation = extract_operation(statement)  # SELECT, INSERT, UPDATE, DELETE

    db_queries_total.labels(operation=operation, table=table).inc()
    db_query_duration_seconds.labels(operation=operation, table=table).observe(duration)

# Pool metrics
@app.on_event("startup")
async def monitor_connection_pool():
    async def collect_pool_metrics():
        while True:
            pool = engine.pool
            db_connections_active.set(pool.checkedout())
            db_connection_pool_size.set(pool.size())
            db_connection_pool_overflow.set(pool.overflow())
            await asyncio.sleep(10)

    asyncio.create_task(collect_pool_metrics())
```

#### 5. Business Metrics

```python
# User activity
active_users_daily = Gauge(
    "active_users_daily",
    "Daily active users",
    ["tenant_id"]
)

drafts_created_total = Counter(
    "drafts_created_total",
    "Total draft sessions created",
    ["tenant_id", "template"]
)

baselines_committed_total = Counter(
    "baselines_committed_total",
    "Total baselines committed",
    ["tenant_id"]
)

runs_executed_total = Counter(
    "runs_executed_total",
    "Total runs executed",
    ["tenant_id", "mc_enabled"]
)

# Revenue-related
billable_usage_total = Counter(
    "billable_usage_total",
    "Billable usage events",
    ["tenant_id", "usage_type", "plan"]
)

# Usage type: llm_tokens, mc_simulations, erp_syncs, storage_gb
```

#### 6. System Metrics

```python
# Provided by node_exporter or CloudWatch
# - CPU utilization
# - Memory usage
# - Disk I/O
# - Network traffic
# - Container/pod status (if k8s)

# Application-level system metrics
background_jobs_active = Gauge(
    "background_jobs_active",
    "Currently executing background jobs",
    ["job_type"]
)

background_jobs_queued = Gauge(
    "background_jobs_queued",
    "Jobs in queue",
    ["job_type"]
)

cache_hits_total = Counter(
    "cache_hits_total",
    "Cache hits",
    ["cache_type"]  # redis, local
)

cache_misses_total = Counter(
    "cache_misses_total",
    "Cache misses",
    ["cache_type"]
)

# Cache hit rate (computed in Grafana or AlertManager)
# rate(cache_hits_total) / (rate(cache_hits_total) + rate(cache_misses_total))
```

### Metrics Exposure

```python
# Expose metrics endpoint
from prometheus_client import make_asgi_app

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Secure metrics endpoint (internal only)
@app.middleware("http")
async def protect_metrics(request: Request, call_next):
    if request.url.path.startswith("/metrics"):
        # Only allow from internal IPs or with auth token
        if not is_internal_request(request):
            return JSONResponse(status_code=403, content={"error": "Forbidden"})

    return await call_next(request)
```

---

## Distributed Tracing

### OpenTelemetry Setup

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor

# Configure tracer
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

# Export to Jaeger / Tempo / Datadog
otlp_exporter = OTLPSpanExporter(endpoint="http://jaeger:4317")
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# Auto-instrument frameworks
FastAPIInstrumentor.instrument_app(app)
SQLAlchemyInstrumentor().instrument(engine=engine)
RedisInstrumentor().instrument()

# Manual instrumentation for critical paths
async def execute_run(run_id: str, model_config: dict):
    with tracer.start_as_current_span("execute_run") as span:
        span.set_attribute("run_id", run_id)
        span.set_attribute("baseline_id", model_config["baseline_id"])
        span.set_attribute("horizon_months", model_config["metadata"]["horizon_months"])

        # Child span
        with tracer.start_as_current_span("build_graph"):
            graph = build_calculation_graph(model_config["driver_blueprint"])
            span.set_attribute("num_nodes", len(graph.nodes))

        with tracer.start_as_current_span("execute_time_loop"):
            results = execute_time_series(graph, model_config)

        with tracer.start_as_current_span("generate_statements"):
            statements = generate_statements(results)

        return statements
```

### Trace Context Propagation

```python
# Automatically propagated via HTTP headers
# W3C Trace Context: traceparent, tracestate

# For background jobs, explicitly pass trace context
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

propagator = TraceContextTextMapPropagator()

# When queuing job
def enqueue_mc_run(run_id: str, model_config: dict):
    carrier = {}
    propagator.inject(carrier)  # Extract current trace context

    celery_task.delay(
        run_id=run_id,
        model_config=model_config,
        trace_context=carrier  # Pass to worker
    )

# In worker
@celery_app.task
def execute_mc_run(run_id: str, model_config: dict, trace_context: dict):
    ctx = propagator.extract(carrier=trace_context)  # Restore context
    with tracer.start_as_current_span("execute_mc_run", context=ctx):
        ...
```

### Trace Sampling

```python
# Sample traces based on volume (avoid overwhelming backend)
from opentelemetry.sdk.trace.sampling import ParentBasedTraceIdRatioBased

# Sample 10% of traces in production
sampler = ParentBasedTraceIdRatioBased(0.1)

# But always sample errors
from opentelemetry.sdk.trace.sampling import ALWAYS_ON

class ErrorAwaresampler:
    def should_sample(self, context, trace_id, name, attributes=None, links=None):
        # Always sample if error
        if attributes and attributes.get("error"):
            return ALWAYS_ON.should_sample(...)
        # Otherwise use ratio-based
        return ParentBasedTraceIdRatioBased(0.1).should_sample(...)
```

---

## Dashboards

### 1. API Health Dashboard

**Panels:**
- Request rate (req/sec) - line chart
- Error rate (%) - line chart with threshold
- P50/P95/P99 latency - multi-line chart
- Requests by endpoint - bar chart
- Errors by code - pie chart
- Active requests - gauge

### 2. Engine Performance Dashboard

**Panels:**
- Run executions/min - line chart
- Execution time distribution - histogram
- MC simulation time - line chart
- Balance sheet errors - counter
- Engine errors by type - bar chart

### 3. LLM Operations Dashboard

**Panels:**
- LLM calls/min by provider - stacked area
- LLM latency by provider - multi-line
- Token usage (prompt vs completion) - stacked bar
- Estimated cost/hour - line chart
- LLM errors by provider - stacked bar
- Provider routing decisions - pie chart

### 4. Database Performance Dashboard

**Panels:**
- Query rate by operation - stacked area
- Query latency P95 - line chart
- Connection pool utilization - gauge
- Slow queries (>100ms) - table
- RLS policy enforcement - counter

### 5. Business Metrics Dashboard

**Panels:**
- Daily active users - line chart
- Drafts created/day - line chart
- Baselines committed/day - line chart
- Runs executed/day - bar chart
- Usage by tenant (top 10) - bar chart
- Plan distribution - pie chart

### 6. System Health Dashboard

**Panels:**
- CPU utilization - line chart
- Memory usage - line chart
- Disk I/O - line chart
- Network throughput - line chart
- Background job queue depth - line chart
- Cache hit rate - line chart

---

## Alerting

### Alert Rules

```yaml
# Prometheus AlertManager rules
groups:
  - name: api_health
    interval: 1m
    rules:
      - alert: HighErrorRate
        expr: rate(api_errors_total[5m]) / rate(api_requests_total[5m]) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High API error rate ({{ $value }}%)"

      - alert: CriticalErrorRate
        expr: rate(api_errors_total[5m]) / rate(api_requests_total[5m]) > 0.10
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Critical API error rate ({{ $value }}%)"

      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(api_request_duration_seconds_bucket[5m])) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "API P95 latency >2s"

      - alert: APIDown
        expr: up{job="api"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "API instance down"

  - name: database
    interval: 1m
    rules:
      - alert: DatabaseConnectionPoolExhausted
        expr: db_connection_pool_overflow > 5
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Database connection pool near capacity"

      - alert: SlowQueries
        expr: histogram_quantile(0.95, rate(db_query_duration_seconds_bucket[5m])) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Slow database queries detected"

  - name: llm_providers
    interval: 1m
    rules:
      - alert: AllLLMProvidersFailing
        expr: sum(rate(llm_provider_errors_total[5m])) / sum(rate(llm_calls_total[5m])) > 0.95
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "All LLM providers failing"

      - alert: HighLLMCost
        expr: rate(llm_cost_usd_total[1h]) > 100
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "LLM costs exceeding budget (>$100/hour)"

  - name: engine
    interval: 1m
    rules:
      - alert: HighEngineFailureRate
        expr: rate(engine_executions_total{status="failure"}[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High engine failure rate"

      - alert: EngineTimeout
        expr: increase(engine_execution_duration_seconds_count{le="60"}[5m]) / increase(engine_execution_duration_seconds_count[5m]) < 0.95
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: ">5% of engine executions timing out"
```

### Alert Routing

```yaml
# AlertManager config
route:
  receiver: slack-general
  group_by: ['alertname', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h

  routes:
    - match:
        severity: critical
      receiver: pagerduty-oncall
      continue: true

    - match:
        severity: critical
      receiver: slack-critical

    - match:
        severity: warning
      receiver: slack-warnings

receivers:
  - name: slack-general
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/XXX'
        channel: '#alerts'

  - name: slack-critical
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/XXX'
        channel: '#critical-alerts'

  - name: slack-warnings
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/XXX'
        channel: '#warnings'

  - name: pagerduty-oncall
    pagerduty_configs:
      - service_key: 'XXX'
```

---

## Health Checks

### Liveness Probe

```python
@app.get("/api/v1/health/live")
async def liveness():
    """Is the service running?"""
    return {"status": "ok"}
```

### Readiness Probe

```python
@app.get("/api/v1/health/ready")
async def readiness():
    """Is the service ready to accept traffic?"""
    checks = {}

    # Check database
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"

    # Check Redis
    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {str(e)}"

    # Check storage
    try:
        await storage.health_check()
        checks["storage"] = "ok"
    except Exception as e:
        checks["storage"] = f"error: {str(e)}"

    all_ok = all(v == "ok" for v in checks.values())
    status_code = 200 if all_ok else 503

    return JSONResponse(
        status_code=status_code,
        content={"status": "ok" if all_ok else "degraded", "checks": checks}
    )
```

### Startup Probe

```python
@app.get("/api/v1/health/startup")
async def startup():
    """Has the service completed initialization?"""
    checks = {
        "migrations_applied": await check_migrations(),
        "cache_warmed": await check_cache_warmed(),
        "connections_established": await check_connections()
    }

    all_ok = all(checks.values())
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "ok" if all_ok else "initializing", "checks": checks}
    )
```

---

## Observability Checklist

### Phase 0
- [ ] Structured logging configured
- [ ] Correlation IDs in all logs
- [ ] Basic metrics (API requests, errors)
- [ ] Health check endpoints
- [ ] Log aggregation setup

### Phase 1
- [ ] Engine execution metrics
- [ ] Database query metrics
- [ ] Dashboard for API health
- [ ] Alert rules for critical errors

### Phase 2
- [ ] LLM call metrics (latency, tokens, cost)
- [ ] Distributed tracing for LLM flows
- [ ] Alert for LLM provider failures
- [ ] Dashboard for LLM operations

### Phase 3
- [ ] MC simulation metrics
- [ ] Background job metrics
- [ ] Trace MC execution paths
- [ ] Alert for MC timeouts

### Phase 4
- [ ] Integration sync metrics
- [ ] Billing/usage metrics
- [ ] Dashboard for business metrics
- [ ] Alert for quota exceeded

### Phase 5
- [ ] Excel sync metrics
- [ ] Memo generation metrics
- [ ] Full end-to-end trace (draft → commit → run → memo)
