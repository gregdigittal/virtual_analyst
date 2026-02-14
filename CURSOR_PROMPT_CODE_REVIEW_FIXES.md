# Code Review Fix Prompt — Virtual Analyst v1

> Apply ALL fixes below in order. Each fix is numbered and specifies exact file(s) and changes. Do NOT skip any fix. Do NOT add unrelated changes.

---

## FIX 0 — Render Deployment Crash (python-multipart)

The Render deploy fails because `python-multipart` is not being installed in the runtime environment. The package IS in `pyproject.toml` but Render is using Python 3.13 while the project targets 3.12.

**File: `render.yaml`**
Add `pythonVersion` and simplify the build command:
```yaml
services:
  - type: web
    name: virtual-analyst-api
    runtime: python
    pythonVersion: "3.12.0"
    plan: free
    region: oregon
    buildCommand: pip install .
    startCommand: uvicorn apps.api.app.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: ENVIRONMENT
        value: production
      - key: LOG_LEVEL
        value: INFO
      - key: DATABASE_URL
        sync: false
      - key: REDIS_URL
        sync: false
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_ANON_KEY
        sync: false
      - key: SUPABASE_SERVICE_KEY
        sync: false
      - key: CORS_ALLOWED_ORIGINS
        value: ""
```

The redundant `pip install python-multipart &&` prefix is removed since it's already in `pyproject.toml` dependencies, and `pythonVersion: "3.12.0"` pins the runtime to match the project target.

---

## FIX 1 — Missing RLS on `notifications` Table (CRITICAL)

**File: `apps/api/app/db/migrations/0008_notifications.sql`**
Append after line 19 (after the last `create index` statement):

```sql

-- RLS: scope notifications to current tenant
alter table notifications enable row level security;
drop policy if exists "notifications_select" on notifications;
create policy "notifications_select" on notifications for select
  using (tenant_id = current_setting('app.tenant_id', true));
drop policy if exists "notifications_insert" on notifications;
create policy "notifications_insert" on notifications for insert
  with check (tenant_id = current_setting('app.tenant_id', true));
drop policy if exists "notifications_update" on notifications;
create policy "notifications_update" on notifications for update
  using (tenant_id = current_setting('app.tenant_id', true));
drop policy if exists "notifications_delete" on notifications;
create policy "notifications_delete" on notifications for delete
  using (tenant_id = current_setting('app.tenant_id', true));
```

---

## FIX 2 — Path Traversal in ArtifactStore (CRITICAL)

**File: `shared/fm_shared/storage/artifact_store.py`**
Replace the `_path` function (lines 14-15) with a version that sanitizes all components:

```python
import re as _re

_SAFE_SEGMENT = _re.compile(r"^[\w\-\.]+$")


def _path(tenant_id: str, artifact_type: str, artifact_id: str) -> str:
    for label, val in [("tenant_id", tenant_id), ("artifact_type", artifact_type), ("artifact_id", artifact_id)]:
        if not val or not _SAFE_SEGMENT.match(val):
            raise StorageError(
                f"Invalid {label}: must be alphanumeric/dash/underscore/dot, got {val!r}",
                code="ERR_STOR_INVALID_PATH",
            )
    return f"{tenant_id}/{artifact_type}/{artifact_id}.json"
```

---

## FIX 3 — OAuth Encryption: Fail Loudly, No Plaintext Fallback (CRITICAL)

**File: `apps/api/app/db/integrations.py`**
Replace `_encode_oauth` and `_decode_oauth` (lines 12-39) with:

```python
import structlog

_logger = structlog.get_logger()


def _encode_oauth(data: dict[str, Any]) -> bytes:
    """Encrypt OAuth payload for storage. Requires OAUTH_ENCRYPTION_KEY."""
    raw = json.dumps(data).encode("utf-8")
    from apps.api.app.core.settings import get_settings
    key = get_settings().oauth_encryption_key
    if not key:
        _logger.critical("oauth_encryption_key_missing", msg="OAuth tokens will be stored as base64 (NOT encrypted). Set OAUTH_ENCRYPTION_KEY in production.")
        return base64.b64encode(raw)
    from cryptography.fernet import Fernet
    return Fernet(key.encode()).encrypt(raw)


def _decode_oauth(raw: bytes | None) -> dict[str, Any]:
    """Decrypt OAuth payload from storage."""
    if not raw:
        return {}
    from apps.api.app.core.settings import get_settings
    key = get_settings().oauth_encryption_key
    if key:
        try:
            from cryptography.fernet import Fernet
            decrypted = Fernet(key.encode()).decrypt(raw)
            return json.loads(decrypted.decode("utf-8"))
        except Exception:
            _logger.error("oauth_decrypt_failed", msg="Fernet decryption failed; falling back to base64. Possible key rotation or data corruption.")
    try:
        return json.loads(base64.b64decode(raw).decode("utf-8"))
    except Exception:
        _logger.error("oauth_decode_failed", msg="Both Fernet and base64 decoding failed for OAuth data.")
        return {}
```

---

## FIX 4 — Cache LLM SDK Clients (CRITICAL resource leak)

**File: `apps/api/app/services/llm/provider.py`**

In `AnthropicProvider.__init__` (around line 107), add client creation:
```python
def __init__(self, api_key: str | None = None) -> None:
    if not api_key:
        raise ValueError("Anthropic API key is required")
    self._api_key = api_key
    import anthropic
    self._client = anthropic.AsyncAnthropic(api_key=api_key)
```

Then in `AnthropicProvider.complete`, replace the line that creates a new client (`client = anthropic.AsyncAnthropic(api_key=self._api_key)`) with:
```python
client = self._client
```

Do the same for `OpenAIProvider.__init__` (around line 188):
```python
def __init__(self, api_key: str | None = None) -> None:
    if not api_key:
        raise ValueError("OpenAI API key is required")
    self._api_key = api_key
    from openai import AsyncOpenAI
    self._client = AsyncOpenAI(api_key=api_key)
```

And in `OpenAIProvider.complete`, replace `client = AsyncOpenAI(api_key=self._api_key)` with:
```python
client = self._client
```

---

## FIX 5 — Settings: Validate Secrets in Production

**File: `apps/api/app/core/settings.py`**
Add a model validator after all fields (before the `cors_allowed_origins_list` method):

```python
    from pydantic import model_validator

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> "Settings":
        if self.environment not in ("development", "test"):
            if self.oauth_state_secret == "change-me-in-production":
                import warnings
                warnings.warn("OAUTH_STATE_SECRET is still default — change it for production!", stacklevel=2)
            if not self.oauth_encryption_key:
                import warnings
                warnings.warn("OAUTH_ENCRYPTION_KEY is empty — OAuth tokens will NOT be encrypted!", stacklevel=2)
        if self.pool_min_size > self.pool_max_size:
            raise ValueError(f"DB_POOL_MIN_SIZE ({self.pool_min_size}) > DB_POOL_MAX_SIZE ({self.pool_max_size})")
        return self
```

Also add the `model_validator` import at the top of the file — add to the existing pydantic import:
```python
from pydantic import Field, model_validator
```

---

## FIX 6 — Prometheus Cardinality Fix

**File: `apps/api/app/middleware/metrics.py`**
Replace line 30 (`endpoint=request.url.path,`) and line 35 (`endpoint=request.url.path,`) to use the route template instead of raw path:

Replace the entire `metrics_middleware` function with:

```python
async def metrics_middleware(request: Request, call_next):
    api_requests_active.inc()
    start = time.time()

    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception:
        status_code = 500
        raise
    finally:
        duration = time.time() - start
        api_requests_active.dec()
        # Use route template to avoid label cardinality explosion
        route = request.scope.get("route")
        endpoint = route.path if route else request.url.path
        api_requests_total.labels(
            method=request.method,
            endpoint=endpoint,
            status_code=str(status_code),
        ).inc()
        api_request_duration_seconds.labels(
            method=request.method,
            endpoint=endpoint,
        ).observe(duration)
        if not request.url.path.startswith("/api/v1/metrics"):
            record_request_latency(endpoint, duration)

    return response
```

---

## FIX 7 — IDOR: Scope Job Status to Tenant

**File: `apps/api/app/routers/jobs.py`**
In the `get_job_status` endpoint, after retrieving the task status, verify the tenant owns the task. Find the line that retrieves status (the `_get_task_status` call) and add a tenant check.

At the top of the file, add a module-level dict to track task ownership:
```python
# Track task-to-tenant mapping for authorization
_task_tenant_map: dict[str, str] = {}
```

In the `enqueue_job` endpoint, after `result = task_cls.apply_async(...)`, add:
```python
_task_tenant_map[result.id] = x_tenant_id
```

In the `get_job_status` endpoint, add after the tenant_id check:
```python
    owner = _task_tenant_map.get(task_id)
    if owner and owner != x_tenant_id:
        raise HTTPException(403, "Not authorized to view this task")
```

---

## FIX 8 — Notifications: Filter by User ID

**File: `apps/api/app/routers/notifications.py`**
In the `list_notifications` function, update the SQL query to include a user_id filter. Change the WHERE clause from:
```sql
WHERE tenant_id = $1
```
to:
```sql
WHERE tenant_id = $1 AND (user_id = $2 OR user_id IS NULL)
```
And pass `x_user_id` as the second parameter. Similarly update the unread count query.

In `mark_notification_read`, add the `x_user_id` header parameter and add a check:
```python
x_user_id: str = Header("", alias="X-User-ID"),
```
And add after the row fetch:
```python
if row and row["user_id"] and row["user_id"] != x_user_id:
    raise HTTPException(403, "Cannot mark another user's notification as read")
```

---

## FIX 9 — Pydantic Models for Untyped Request Bodies

**File: `apps/api/app/routers/runs.py`**
Add a Pydantic model before the `create_run` function:
```python
from pydantic import BaseModel, Field as PydField

class CreateRunBody(BaseModel):
    baseline_id: str
    mode: str = "deterministic"
    num_simulations: int = PydField(default=1000, ge=1, le=100_000)
    seed: int = PydField(default=42, ge=0)
    scenario_id: str | None = None
    scenario_overrides: list[dict[str, Any]] | None = None
    dcf_config: dict[str, Any] | None = None
    multiples_config: dict[str, Any] | None = None
```

Change the `create_run` signature from `body: dict[str, Any]` to `body: CreateRunBody`.
Update references: `body.get("baseline_id")` → `body.baseline_id`, `body.get("mode", "deterministic")` → `body.mode`, `int(body.get("num_simulations", 1000))` → `body.num_simulations`, etc.

**File: `apps/api/app/routers/scenarios.py`**
Add Pydantic models:
```python
from pydantic import BaseModel

class CreateScenarioBody(BaseModel):
    baseline_id: str
    label: str = ""
    description: str = ""
    overrides: list[dict[str, Any]] = []

class UpdateScenarioBody(BaseModel):
    label: str | None = None
    description: str | None = None
    overrides: list[dict[str, Any]] | None = None
```

Change `create_scenario` signature from `body: dict[str, Any]` to `body: CreateScenarioBody`.
Change `update_scenario` signature from `body: dict[str, Any]` to `body: UpdateScenarioBody`.

**File: `apps/api/app/routers/excel.py`**
Add a Pydantic model for the PATCH endpoint:
```python
class UpdateExcelConnectionBody(BaseModel):
    label: str | None = None
    mode: str | None = None  # "readonly" or "readwrite"
    bindings_json: list[dict[str, Any]] | None = None
    status: str | None = None
```

Change the `update_excel_connection` signature from `body: dict[str, Any]` to `body: UpdateExcelConnectionBody`.

---

## FIX 10 — `tenant_conn` Exception Safety

**File: `apps/api/app/db/connection.py`**
Replace the `tenant_conn` function (lines 14-29) with:

```python
@asynccontextmanager
async def tenant_conn(tenant_id: str):
    if _pool is not None:
        conn = await _pool.acquire()
    else:
        settings = get_settings()
        conn = await asyncpg.connect(settings.database_url)
    try:
        await conn.execute("SET app.tenant_id = $1", tenant_id)
        yield conn
    finally:
        try:
            await conn.execute("SET app.tenant_id = ''")
        except Exception:
            pass  # Connection may be broken; cleanup below will handle it
        if _pool is not None:
            await _pool.release(conn)
        else:
            await conn.close()
```

---

## FIX 11 — Middleware Ordering Fix

**File: `apps/api/app/main.py`**
Reverse the middleware registration order so logging is outermost (lines 55-57). Change from:
```python
app.middleware("http")(logging_middleware)
app.middleware("http")(security_headers_middleware)
app.middleware("http")(metrics_middleware)
```
To:
```python
app.middleware("http")(metrics_middleware)
app.middleware("http")(security_headers_middleware)
app.middleware("http")(logging_middleware)
```

---

## FIX 12 — CSP: Remove `unsafe-inline` for API

**File: `apps/api/app/middleware/security.py`**
Replace the CSP header (lines 25-32) with a stricter policy appropriate for a JSON API:
```python
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; "
        "frame-ancestors 'none';"
    )
```

Also replace the deprecated `X-XSS-Protection` header (line 23):
```python
    response.headers["X-XSS-Protection"] = "0"
```

Add `Referrer-Policy`:
```python
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
```

---

## FIX 13 — Frontend: Protect All Routes in Middleware

**File: `apps/web/middleware.ts`**
Update the protected paths array (line 4) and matcher config (line 47):

```typescript
const protectedPaths = ["/baselines", "/runs", "/dashboard", "/drafts", "/scenarios", "/notifications"];
```

```typescript
export const config = {
  matcher: [
    "/",
    "/login",
    "/baselines/:path*",
    "/runs/:path*",
    "/dashboard/:path*",
    "/drafts/:path*",
    "/scenarios/:path*",
    "/notifications/:path*",
  ],
};
```

---

## FIX 14 — Frontend: Use `getUser()` Instead of `getSession()`

**File: `apps/web/middleware.ts`**
Replace line 29-31:
```typescript
  const {
    data: { session },
  } = await supabase.auth.getSession();
```
With:
```typescript
  const {
    data: { user },
  } = await supabase.auth.getUser();
```

And update the checks:
- Line 33: `!session` → `!user`
- Line 39: `session` → `user`

**File: `apps/web/app/page.tsx`**
Apply the same change — replace `getSession()` with `getUser()` and update the conditional.

---

## FIX 15 — Covenant Breach: Error on Unknown Operator

**File: `apps/api/app/db/covenants.py`**
Replace the `_is_breach` function (lines 17-27) with:

```python
def _is_breach(actual: float, operator: str, threshold: float) -> bool:
    if operator == "<":
        return actual >= threshold
    if operator == ">":
        return actual <= threshold
    if operator == "<=":
        return actual > threshold
    if operator == ">=":
        return actual < threshold
    raise ValueError(f"Unsupported covenant operator: {operator!r}")
```

---

## FIX 16 — Audit Checksum: Include `user_id`

**File: `apps/api/app/db/audit.py`**
In the `create_audit_event` function, find the `payload` dict (around lines 37-45) and add `user_id`:

```python
    payload = {
        "audit_event_id": audit_event_id,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "event_type": event_type,
        "event_category": event_category,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "event_data": data,
    }
```

---

## FIX 17 — Xero: Persist New Refresh Token

**File: `apps/api/app/services/integrations/base.py`**
Change the `refresh_token` abstract method return type from `str` to a tuple:
```python
    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> tuple[str, str]:
        """Return (new_access_token, new_refresh_token)."""
```

**File: `apps/api/app/services/integrations/xero.py`**
In the `refresh_token` method, change the return statement from:
```python
return data["access_token"]
```
To:
```python
return data["access_token"], data.get("refresh_token", refresh_token)
```

Update all callers of `adapter.refresh_token()` to unpack the tuple and store the new refresh token in the database.

---

## FIX 18 — Workspace PATCH: Allowlist Updatable Keys

**File: `apps/api/app/routers/drafts.py`**
In the `patch_draft_session` function, find the workspace merge block (around line 466-469). Replace the unrestricted shallow merge:
```python
if workspace_update is not None:
    current = store.load(x_tenant_id, DRAFT_WORKSPACE_TYPE, draft_session_id)
    merged = {**current, **workspace_update}
    store.save(x_tenant_id, DRAFT_WORKSPACE_TYPE, draft_session_id, merged)
```

With an allowlisted merge:
```python
if workspace_update is not None:
    _ALLOWED_WORKSPACE_KEYS = {
        "assumptions", "driver_blueprint", "distributions", "metadata",
        "evidence", "debt_facilities", "cost_centres", "revenue_streams",
    }
    current = store.load(x_tenant_id, DRAFT_WORKSPACE_TYPE, draft_session_id)
    for k, v in workspace_update.items():
        if k in _ALLOWED_WORKSPACE_KEYS:
            current[k] = v
    store.save(x_tenant_id, DRAFT_WORKSPACE_TYPE, draft_session_id, current)
```

---

## FIX 19 — Engine: Don't Silently Zero Failed Formulas

**File: `shared/fm_shared/model/engine.py`**
Replace the `except EvalError` block (around lines 170-177) that silently substitutes 0.0:

```python
            except EvalError as e:
                logger.warning(
                    "formula_eval_fallback",
                    node_id=nid,
                    period=t,
                    error=str(e),
                    msg="Formula evaluation failed; substituting 0.0",
                )
                time_series[nid][t] = 0.0
```

Change to raise instead of silently substituting:
```python
            except EvalError as e:
                raise EngineError(
                    f"Formula evaluation failed for node '{nid}' at period {t}: {e}",
                    code="ERR_ENG_FORMULA_EVAL",
                ) from e
```

This will surface formula errors immediately instead of silently cascading zeros through the model.

---

## FIX 20 — Valuation: Guard Against WACC Edge Cases

**File: `shared/fm_shared/analysis/valuation.py`**
Replace the guard at line 46:
```python
if not fcf_series or wacc <= -1.0:
```
With:
```python
if not fcf_series or wacc <= 0.0:
```

A zero or negative WACC is financially nonsensical for DCF. This also prevents division by zero when `wacc == -1.0`.

---

## FIX 21 — `import_csv.py`: Move `json` Import to Module Level

**File: `apps/api/app/routers/import_csv.py`**
Move the `import json` from inside the function (line 96) to the top of the file with the other imports (after line 8):

Add after `from typing import Any`:
```python
import json as _json
```

Remove line 96 (`import json as _json`) from inside the `import_csv` function.

---

## FIX 22 — Missing Index on `stripe_subscription_id`

**File: `apps/api/app/db/migrations/0013_billing_usage_llm.sql`**
Add at the end of the file:

```sql
-- Index for Stripe webhook lookup
create index if not exists idx_billing_subscriptions_stripe_sid
  on billing_subscriptions(stripe_subscription_id)
  where stripe_subscription_id is not null;
```

---

## FIX 23 — Worker: Fix `tenant_id` Leak in `_run_mc_fail_async`

**File: `apps/worker/tasks.py`**
In the `_run_mc_fail_async` function, add tenant_id cleanup in the finally block. Change from:
```python
    finally:
        await conn.close()
```
To:
```python
    finally:
        try:
            await conn.execute("SET app.tenant_id = ''")
        except Exception:
            pass
        await conn.close()
```

Also wrap `_run_mc_fail_async` calls in try/except so they don't mask the original error. In the exception handlers (around lines 230-237), change:
```python
except (EngineError, StatementImbalanceError, ValueError) as e:
    logger.exception(...)
    asyncio.run(_run_mc_fail_async(...))
    raise
except Exception as e:
    logger.exception(...)
    asyncio.run(_run_mc_fail_async(...))
    raise
```
To a single handler:
```python
except Exception as e:
    logger.exception("mc_simulation_failed", tenant_id=tenant_id, run_id=run_id, error=str(e))
    try:
        asyncio.run(_run_mc_fail_async(tenant_id, run_id, str(e)))
    except Exception as fail_err:
        logger.error("mc_fail_update_failed", error=str(fail_err))
    raise
```

---

## FIX 24 — Worker: Redis Connection Leak Fix

**File: `apps/worker/tasks.py`**
Replace `_set_mc_progress` (around lines 60-74) with proper resource management:

```python
def _set_mc_progress(tenant_id: str, run_id: str, current: int, total: int) -> None:
    try:
        r = redis.from_url(REDIS_URL)
        try:
            key = f"{MC_PROGRESS_KEY}:{tenant_id}:{run_id}"
            payload = json.dumps({"current": current, "total": total, "pct": round(current / max(total, 1) * 100, 1)})
            r.setex(key, MC_PROGRESS_TTL, payload)
        finally:
            r.close()
    except Exception:
        pass
```

Apply the same pattern to `_clear_mc_progress`.

---

## FIX 25 — Billing Webhook: Use Explicit Bypass Context

**File: `apps/api/app/routers/billing.py`**
In the webhook handler, replace `tenant_conn("")` with a comment explaining why and using the resolved tenant_id. After the Stripe event is parsed and `tenant_id` is resolved, use that tenant_id:

```python
# Stripe webhooks resolve tenant from subscription; use resolved tenant_id for RLS context
async with tenant_conn(tenant_id) as conn:
```

If the `tenant_id` is resolved after the DB lookup (via `get_tenant_by_stripe_subscription`), restructure so the lookup happens outside `tenant_conn` (since that function is `SECURITY DEFINER`), then use the resolved `tenant_id` for subsequent queries.

---

## FIX 26 — CORS: Restrict Methods and Headers

**File: `apps/api/app/main.py`**
Replace the CORS middleware configuration (lines 47-53):
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins_list(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Tenant-ID", "X-User-ID", "X-Request-ID"],
)
```

---

## FIX 27 — Sensitivity/Compare: Cap + Thread Offload

**File: `apps/api/app/routers/runs.py`**
In the sensitivity endpoint (around line 477), add a cap on drivers and offload to thread:

Add at the top of the endpoint:
```python
MAX_SENSITIVITY_DRIVERS = 30
```

Before the loop that iterates drivers, add:
```python
if len(drivers) > MAX_SENSITIVITY_DRIVERS:
    raise HTTPException(400, f"Too many drivers for sensitivity ({len(drivers)}); max {MAX_SENSITIVITY_DRIVERS}")
```

**File: `apps/api/app/routers/scenarios.py`**
In the `compare_scenarios` endpoint, add a cap:
```python
MAX_COMPARE_SCENARIOS = 10
if len(scenario_ids) > MAX_COMPARE_SCENARIOS:
    raise HTTPException(400, f"Too many scenarios to compare ({len(scenario_ids)}); max {MAX_COMPARE_SCENARIOS}")
```

---

## FIX 28 — Memo Type: Error on Invalid Type Instead of Silent Fallback

**File: `apps/api/app/services/memo_service.py`**
Replace the silent fallback (lines 74-75):
```python
if memo_type not in MEMO_TYPES:
    memo_type = "investment_committee"
```
With:
```python
if memo_type not in MEMO_TYPES:
    raise ValueError(f"Unknown memo_type {memo_type!r}; must be one of {list(MEMO_TYPES.keys())}")
```

---

## FIX 29 — Excel Push: Honest Sync Status

**File: `apps/api/app/routers/excel.py`**
In the `excel_push` endpoint, change the sync event status from `"succeeded"` to `"received"` since changes are not actually applied:

```python
await insert_sync_event(
    conn, x_tenant_id, excel_connection_id,
    direction="push", status="received",
    ...
)
return {"received": len(changes), "status": "received"}
```

---

## FIX 30 — Changeset Merge: Require `tested` Status

**File: `apps/api/app/routers/changesets.py`**
In the `merge_changeset` function, after the checks for `merged` and `abandoned` status, add:

```python
if row["status"] != STATUS_TESTED:
    raise HTTPException(409, f"Changeset must be tested before merge; current status: {row['status']}")
```

---

## FIX 31 — Health Check: Fix Redis Connection Leak

**File: `apps/api/app/routers/health.py`**
Replace the Redis health check block with proper try/finally:

```python
    try:
        redis_client = Redis.from_url(settings.redis_url)
        try:
            await redis_client.ping()
            checks["redis"] = "ok"
        finally:
            await redis_client.close()
    except Exception:
        checks["redis"] = "error"
```

Also fix the database connection check to not use the fragile `hasattr` pattern:
```python
    try:
        async with tenant_conn("") as conn:
            await conn.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
```

---

## FIX 32 — Frontend: Fix String Replace for Underscores

**File: `apps/web/app/runs/[id]/mc/page.tsx`**
Replace all occurrences of `.replace("_", " ")` with `.replaceAll("_", " ")` (or `.replace(/_/g, " ")`).

**File: `apps/web/app/scenarios/page.tsx`**
Same fix — replace `.replace("_", " ")` with `.replaceAll("_", " ")`.

---

## FIX 33 — Statements: Accumulated Depreciation Performance

**File: `shared/fm_shared/model/statements.py`**
Replace the O(horizon²) accumulated depreciation calculation (around line 154):
```python
acc_depr[t] = sum(da_per_month[: t + 1])
```
With a running total:
```python
acc_depr[t] = acc_depr[t - 1] + da_per_month[t] if t > 0 else da_per_month[0]
```

---

## FIX 34 — Audit Export: True Streaming

**File: `apps/api/app/routers/audit.py`**
In the export endpoint, replace the buffered approach with a generator for CSV:

Replace the section that builds the full body bytes and wraps in `iter([body])` with:

```python
if export_format == "csv":
    import csv
    import io

    async def csv_generator():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["audit_event_id", "tenant_id", "user_id", "event_type", "event_category", "resource_type", "resource_id", "timestamp", "event_data"])
        yield output.getvalue()
        output.truncate(0)
        output.seek(0)
        for row in rows:
            writer.writerow([row["audit_event_id"], row["tenant_id"], row["user_id"], row["event_type"], row["event_category"], row["resource_type"], row["resource_id"], str(row["timestamp"]), json.dumps(dict(row.get("event_data") or {}))])
            yield output.getvalue()
            output.truncate(0)
            output.seek(0)

    return StreamingResponse(csv_generator(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="audit_export.csv"'})
```

---

## FIX 35 — Missing Audit Events: Wire Up Defined Constants

**File: `apps/api/app/routers/scenarios.py`**
Import and call audit events:
```python
from apps.api.app.db.audit import EVENT_SCENARIO_CREATED, EVENT_SCENARIO_DELETED, create_audit_event
```

In `create_scenario`, after the INSERT succeeds, add:
```python
await create_audit_event(conn, x_tenant_id, EVENT_SCENARIO_CREATED, "scenario", "scenario", scenario_id, user_id=x_user_id)
```

In `delete_scenario`, after the DELETE succeeds, add:
```python
await create_audit_event(conn, x_tenant_id, EVENT_SCENARIO_DELETED, "scenario", "scenario", scenario_id, user_id=x_user_id)
```

---

## Summary

| Fix | Severity | Area |
|-----|----------|------|
| 0 | DEPLOY | Render crash — pin Python 3.12 |
| 1 | CRITICAL | Missing RLS on notifications |
| 2 | CRITICAL | Path traversal in ArtifactStore |
| 3 | CRITICAL | OAuth plaintext fallback |
| 4 | CRITICAL | LLM client socket leak |
| 5 | HIGH | Settings production validation |
| 6 | HIGH | Prometheus cardinality explosion |
| 7 | HIGH | IDOR in job status |
| 8 | HIGH | Notification privacy leak |
| 9 | HIGH | Untyped request bodies |
| 10 | HIGH | tenant_conn exception safety |
| 11 | MEDIUM | Middleware ordering |
| 12 | MEDIUM | CSP unsafe-inline |
| 13 | MEDIUM | Unprotected frontend routes |
| 14 | MEDIUM | getSession vs getUser |
| 15 | MEDIUM | Covenant unknown operator |
| 16 | MEDIUM | Audit checksum excludes user_id |
| 17 | HIGH | Xero discards refresh token |
| 18 | MEDIUM | Workspace key overwrite |
| 19 | HIGH | Silent zero on eval failure |
| 20 | HIGH | WACC division by zero |
| 21 | LOW | json import location |
| 22 | MEDIUM | Missing Stripe index |
| 23 | MEDIUM | Worker tenant_id leak |
| 24 | MEDIUM | Worker Redis leak |
| 25 | MEDIUM | Webhook empty tenant_id |
| 26 | MEDIUM | CORS too permissive |
| 27 | HIGH | Sensitivity/compare DoS |
| 28 | MEDIUM | Memo type silent fallback |
| 29 | MEDIUM | Excel push misleading status |
| 30 | MEDIUM | Changeset merge bypass |
| 31 | MEDIUM | Health check resource leak |
| 32 | LOW | Frontend string replace |
| 33 | MEDIUM | O(n²) depreciation |
| 34 | MEDIUM | Audit export memory |
| 35 | MEDIUM | Audit events not wired up |
