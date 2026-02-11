# Error Handling Specification
**Date:** 2026-02-11

## Overview
FinModel uses a structured error handling approach with consistent error codes, user-friendly messages, and comprehensive logging. Every error is classified, logged, and handled appropriately based on its severity and recoverability.

## Error Taxonomy

### Error Categories
| Category | Prefix | Description | User Impact |
|---|---|---|---|
| Validation | `ERR_VAL_` | Input validation failures | Fix input, retry |
| Engine | `ERR_ENG_` | Calculation engine errors | Model issue, needs correction |
| Storage | `ERR_STOR_` | Storage/database errors | Transient or config issue |
| LLM | `ERR_LLM_` | LLM provider errors | Retry or fallback |
| Auth | `ERR_AUTH_` | Authentication/authorization | Login or permission issue |
| Integration | `ERR_INT_` | External integration errors | Config or provider issue |
| System | `ERR_SYS_` | System-level errors | Infrastructure issue |

### Severity Levels
- **CRITICAL**: System unusable, immediate action required
- **ERROR**: Operation failed, user cannot proceed
- **WARNING**: Operation succeeded with issues
- **INFO**: Informational, no action needed

## Error Response Envelope

All API error responses use this structure:

```json
{
  "error": {
    "code": "ERR_VAL_SCHEMA_INVALID",
    "message": "Model configuration validation failed",
    "details": "Field 'assumptions.revenue_streams[0].price' is required but missing",
    "severity": "ERROR",
    "user_message": "Please provide a price for the first revenue stream",
    "correlation_id": "req_abc123xyz",
    "timestamp": "2026-02-11T10:30:00Z",
    "retry_after": null,
    "help_url": "https://docs.finmodel.app/errors/ERR_VAL_SCHEMA_INVALID"
  },
  "meta": {
    "request_id": "req_abc123xyz",
    "timestamp": "2026-02-11T10:30:00Z"
  }
}
```

## Error Code Catalog

### Validation Errors (ERR_VAL_*)

| Code | HTTP | Description | Retry? |
|---|---|---|---|
| ERR_VAL_SCHEMA_INVALID | 422 | JSON Schema validation failed | No |
| ERR_VAL_REQUIRED_FIELD | 422 | Required field missing | No |
| ERR_VAL_TYPE_MISMATCH | 422 | Field type incorrect | No |
| ERR_VAL_RANGE_EXCEEDED | 422 | Value outside allowed range | No |
| ERR_VAL_ENUM_INVALID | 422 | Value not in allowed enum | No |
| ERR_VAL_PATH_INVALID | 422 | JSON path does not exist in schema | No |

### Engine Errors (ERR_ENG_*)

| Code | HTTP | Description | Retry? |
|---|---|---|---|
| ERR_ENG_CYCLE_DETECTED | 422 | Circular dependency in blueprint | No |
| ERR_ENG_FORMULA_INVALID | 422 | Formula syntax error | No |
| ERR_ENG_NODE_MISSING | 422 | Referenced node not found | No |
| ERR_ENG_DIVIDE_BY_ZERO | 500 | Division by zero in calculation | No |
| ERR_ENG_TIMEOUT | 504 | Engine execution timeout | Yes |
| ERR_ENG_COMPLEXITY_LIMIT | 422 | Model exceeds complexity limits | No |
| ERR_ENG_BALANCE_FAIL | 500 | Balance sheet does not balance | No |

### Storage Errors (ERR_STOR_*)

| Code | HTTP | Description | Retry? |
|---|---|---|---|
| ERR_STOR_NOT_FOUND | 404 | Artifact not found | No |
| ERR_STOR_ALREADY_EXISTS | 409 | Artifact already exists | No |
| ERR_STOR_QUOTA_EXCEEDED | 507 | Storage quota exceeded | No |
| ERR_STOR_CONNECTION_FAILED | 503 | Cannot connect to storage | Yes |
| ERR_STOR_WRITE_FAILED | 500 | Write operation failed | Yes |
| ERR_STOR_READ_FAILED | 500 | Read operation failed | Yes |

### LLM Errors (ERR_LLM_*)

| Code | HTTP | Description | Retry? |
|---|---|---|---|
| ERR_LLM_RATE_LIMIT | 429 | Rate limit exceeded | Yes (after delay) |
| ERR_LLM_QUOTA_EXCEEDED | 429 | Token quota exceeded | No |
| ERR_LLM_PROVIDER_ERROR | 503 | Provider API error | Yes |
| ERR_LLM_TIMEOUT | 504 | LLM request timeout | Yes |
| ERR_LLM_INVALID_RESPONSE | 500 | LLM returned invalid JSON | Yes |
| ERR_LLM_CONTENT_FILTER | 400 | Content filtered by provider | No |
| ERR_LLM_ALL_PROVIDERS_FAILED | 503 | All providers failed | Yes (manual) |

### Auth Errors (ERR_AUTH_*)

| Code | HTTP | Description | Retry? |
|---|---|---|---|
| ERR_AUTH_INVALID_TOKEN | 401 | JWT invalid or expired | No |
| ERR_AUTH_MISSING_TOKEN | 401 | Authorization header missing | No |
| ERR_AUTH_INSUFFICIENT_PERMISSIONS | 403 | User lacks required permissions | No |
| ERR_AUTH_TENANT_INACTIVE | 403 | Tenant account suspended | No |
| ERR_AUTH_USER_DEACTIVATED | 403 | User account deactivated | No |

### Integration Errors (ERR_INT_*)

| Code | HTTP | Description | Retry? |
|---|---|---|---|
| ERR_INT_CONNECTION_FAILED | 503 | Cannot connect to ERP | Yes |
| ERR_INT_AUTH_FAILED | 401 | ERP authentication failed | No |
| ERR_INT_SYNC_FAILED | 500 | Sync operation failed | Yes |
| ERR_INT_RATE_LIMIT | 429 | ERP rate limit hit | Yes (after delay) |
| ERR_INT_MAPPING_FAILED | 422 | Cannot map ERP data to canonical | No |

### System Errors (ERR_SYS_*)

| Code | HTTP | Description | Retry? |
|---|---|---|---|
| ERR_SYS_DATABASE_ERROR | 500 | Database operation failed | Yes |
| ERR_SYS_INTERNAL_ERROR | 500 | Unexpected internal error | Yes |
| ERR_SYS_DEPENDENCY_UNAVAILABLE | 503 | Required dependency unavailable | Yes |
| ERR_SYS_CONFIGURATION_ERROR | 500 | System misconfigured | No |

## Retry Strategy

### Automatic Retry Configuration
```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Transient errors (storage, network)
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((ConnectionError, TimeoutError))
)
async def retryable_operation():
    ...

# LLM provider calls
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type((ProviderError, TimeoutError))
)
async def llm_call():
    ...
```

### User-Triggered Retry
For certain errors, provide "Retry" button in UI:
- LLM provider failures (after fallback exhausted)
- Transient network errors
- Storage connection errors
- Engine timeout (user can increase timeout)

### Retry Headers
Include in 429 responses:
```
Retry-After: 60
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1707650400
```

## Circuit Breaker Pattern

For external dependencies (LLM providers, ERP integrations):

```python
from circuitbreaker import circuit

@circuit(failure_threshold=5, recovery_timeout=60, expected_exception=ProviderError)
async def call_llm_provider():
    ...
```

**States:**
- **CLOSED**: Normal operation
- **OPEN**: Too many failures, block calls for recovery_timeout
- **HALF_OPEN**: Test one call, if success → CLOSED, if fail → OPEN

## Graceful Degradation

### LLM Service Down
- Fall back to manual assumption entry
- Show warning: "AI assistant temporarily unavailable"
- Queue draft chat messages for later processing
- Allow draft editing without LLM proposals

### Database Read Replica Down
- Fall back to primary database
- Log performance degradation
- Alert operations team

### Storage Provider Slow
- Increase timeout
- Enable caching layer
- Return cached data with staleness indicator

## Error Logging

### Structured Log Format
```json
{
  "timestamp": "2026-02-11T10:30:00.123Z",
  "level": "ERROR",
  "error_code": "ERR_ENG_TIMEOUT",
  "message": "Engine execution timeout after 30s",
  "correlation_id": "req_abc123",
  "tenant_id": "t_001",
  "user_id": "u_042",
  "context": {
    "baseline_id": "bl_001",
    "run_id": "run_123",
    "horizon_months": 60,
    "num_nodes": 347
  },
  "stack_trace": "...",
  "severity": "ERROR"
}
```

### Log Levels
- **DEBUG**: Detailed diagnostic info (disabled in prod)
- **INFO**: Routine operations (run started, completed)
- **WARNING**: Unexpected but handled (integrity check warnings)
- **ERROR**: Operation failed (user cannot proceed)
- **CRITICAL**: System failure (database down, all LLM providers failed)

### Log Aggregation
- All logs sent to centralized system (CloudWatch, Datadog, Elasticsearch)
- Correlation ID links all logs for a single request
- Searchable by: tenant_id, user_id, error_code, timeframe
- Retention: 30 days hot, 90 days archive

## User Error Messages

### Principles
1. **Be specific**: "Price must be greater than 0" not "Invalid input"
2. **Be actionable**: Tell user what to do
3. **Be respectful**: Avoid "user error" language
4. **Provide context**: Include affected field/resource
5. **Link to help**: Provide documentation URL when applicable

### Examples

**Bad:**
```
Error: Validation failed
```

**Good:**
```
Model configuration is incomplete
• Revenue stream #1 is missing a price
• Working capital settings require AR days (currently not set)

Please complete these fields and try again.
```

**Bad:**
```
Error 500: Internal server error
```

**Good:**
```
We're having trouble saving your model right now

This is likely a temporary issue. Please try again in a moment.
If the problem continues, contact support@finmodel.app with reference ID: req_abc123
```

## Error Handling by Layer

### API Layer (FastAPI)
```python
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "ERR_VAL_SCHEMA_INVALID",
                "message": "Validation failed",
                "details": str(exc),
                "severity": "ERROR",
                "user_message": format_validation_message(exc),
                "correlation_id": request.state.request_id,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            },
            "meta": {
                "request_id": request.state.request_id,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        }
    )
```

### Service Layer
- Catch specific exceptions, wrap with domain error types
- Add business context to error
- Log error with full context
- Raise wrapped exception up to API layer

### Engine Layer
- Validate inputs before execution
- Catch calculation errors (divide by zero, overflow)
- Provide detailed error location (node_id, formula_id, period)
- Never silently fail

### Storage Layer
- Wrap provider errors with domain errors
- Distinguish transient vs. permanent failures
- Include storage path in error context
- Implement automatic retry for transient errors

## Dead Letter Queue

For operations that can be retried later:

```python
# Failed LLM calls
if all_providers_failed:
    await dlq.enqueue({
        "operation": "llm_call",
        "draft_session_id": draft_id,
        "message": user_message,
        "retry_count": 0,
        "max_retries": 5
    })
```

**DLQ Processing:**
- Background worker processes DLQ every 5 minutes
- Exponential backoff: 5m, 15m, 45m, 2h, 6h
- After max retries, notify user and mark as failed
- User can manually retry from UI

## Monitoring & Alerting

### Error Rate Metrics
- Total errors / minute (all types)
- Errors by code (top 10)
- Errors by tenant (detect abuse)
- Error rate by endpoint

### Alert Thresholds
| Condition | Severity | Action |
|---|---|---|
| Error rate > 5% for 5 minutes | WARNING | Log, notify Slack |
| Error rate > 10% for 5 minutes | CRITICAL | Page on-call |
| Specific error > 100/min | WARNING | Investigate |
| Database errors > 10/min | CRITICAL | Check DB health |
| All LLM providers down | CRITICAL | Page on-call + status page |

### Error Dashboards
- Real-time error rate (1h, 24h, 7d)
- Error breakdown by category
- Top 10 error codes
- Error rate by tenant (detect outliers)
- Mean time to recovery (MTTR)

## Testing Error Handling

### Unit Tests
```python
def test_engine_handles_divide_by_zero():
    with pytest.raises(EngineError) as exc_info:
        engine.execute(model_with_zero_denominator)
    assert exc_info.value.code == "ERR_ENG_DIVIDE_BY_ZERO"
    assert "revenue" in exc_info.value.context["formula"]

def test_validation_error_has_user_message():
    with pytest.raises(ValidationError) as exc_info:
        validate_model_config(invalid_config)
    assert exc_info.value.user_message is not None
    assert len(exc_info.value.user_message) > 0
```

### Integration Tests
```python
async def test_storage_retry_on_transient_error(mock_storage):
    mock_storage.side_effect = [ConnectionError(), ConnectionError(), {"success": True}]
    result = await storage.save_artifact(...)
    assert result["success"]
    assert mock_storage.call_count == 3  # Retried twice
```

### Chaos Tests
```python
async def test_llm_all_providers_fail():
    # Simulate all providers down
    with mock_all_llm_providers_failing():
        response = await client.post("/api/v1/drafts/ds_001/chat", ...)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "ERR_LLM_ALL_PROVIDERS_FAILED"
```

## Rollback & Recovery

### Failed Migration
```bash
# Rollback script
./scripts/rollback_migration.sh 0004

# Recovery checklist:
# 1. Restore database from backup
# 2. Replay WAL to point-in-time before migration
# 3. Verify data integrity
# 4. Restart application with previous version
```

### Data Corruption
```python
# Artifact integrity check
async def verify_artifact_integrity(tenant_id, artifact_id):
    artifact = await load_artifact(tenant_id, artifact_id)
    schema = get_schema(artifact["artifact_type"])

    try:
        validate(artifact, schema)
        return {"valid": True}
    except ValidationError as e:
        await log_corruption(tenant_id, artifact_id, str(e))
        # Attempt to restore from previous version
        return await restore_from_backup(tenant_id, artifact_id)
```

## Future Enhancements (Post-v1)

- AI-powered error suggestions ("Did you mean...?")
- Error analytics dashboard for admins
- Automated error pattern detection
- Self-healing for common errors
- Error-driven alerting to users before failure
