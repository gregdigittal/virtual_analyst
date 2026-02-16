# Round 11 — Code-Review Fix Prompt (Phase 8 Features)

> **Context**: Virtual Analyst v1 monorepo.
> **Scope**: All additions since Round 10 — SAML SSO, multi-currency, marketplace templates, peer benchmarking, QuickBooks connector, NL budget queries, workflow analytics, cross-team assignments.
> **Files touched**: `auth_saml.py`, `benchmark.py`, `currency.py`, `marketplace.py`, `connectors.py`, `quickbooks.py`, `board_packs.py`, `board_pack_export.py`, `budgets.py`, `workflows.py`, `assignments.py`, `integrations.py`, `main.py`, `settings.py`, `auth.py` (middleware), `auth/callback/route.ts`, migrations 0036–0040.
> **R10 fixes verified**: R10-01 through R10-09 confirmed applied. R10-10 still outstanding (see R11-11).

---

## CRITICAL

### R11-01 — SAML ACS accepts unsigned responses (account compromise)

**File**: `apps/api/app/routers/auth_saml.py:77-95`
**Problem**: The `saml_acs` endpoint accepts any SAMLResponse without verifying the IdP's XML digital signature. An attacker can craft a SAMLResponse with arbitrary NameID, attributes, and user_id, send it via POST to `/api/v1/auth/saml/acs`, and receive a valid JWT. This completely defeats SAML's security model.

**Fix** (minimum viable — reject unsigned + add TODO for full verification):

```python
# At the top of saml_acs, after parsing the XML root:
# MINIMUM: reject in production if no signature library is available
status_code_el = root.find(".//{urn:oasis:names:tc:SAML:2.0:protocol}StatusCode")
# TODO(VA-P8-02): Integrate signxml or python3-saml to verify the IdP's
# XML signature against the certificate from tenant_saml_config.
# For now, log a warning and reject in production.
import warnings
settings = get_settings()
if settings.environment not in ("development", "test"):
    raise HTTPException(
        501,
        "SAML signature verification not yet implemented; "
        "SSO is disabled in production until IdP signature validation is added.",
    )
logger.warning("saml_acs_no_signature_verification", tenant_id=tenant_id)
```

Long-term, integrate `python3-saml` (OneLogin) or `signxml` to validate the Response/Assertion signature against the IdP certificate stored in `tenant_saml_config`.

---

### R11-02 — SAML user_id from untrusted attributes enables account takeover

**File**: `apps/api/app/routers/auth_saml.py:124-131`
**Problem**: `user_id` is derived from attacker-controlled SAML attributes (`attrs.get("user_id") or attrs.get("sub") or name_id`). The `ON CONFLICT (id) DO UPDATE SET tenant_id = EXCLUDED.tenant_id, email = EXCLUDED.email` then overwrites an existing user's tenant and email — hijacking their account.

**Fix**: Never use attacker-supplied values as the primary key for user upsert. Generate a deterministic but SAML-scoped ID:

```python
import hashlib

# Derive a SAML-scoped user ID that cannot collide with existing non-SAML users
raw_name_id = name_id or attrs.get("email") or attrs.get("sub") or ""
if not raw_name_id:
    raise HTTPException(400, "No NameID, email, or sub in SAML assertion")
user_id = "saml_" + hashlib.sha256(
    f"{tenant_id}:{raw_name_id}".encode()
).hexdigest()[:24]

email = attrs.get(email_attr) or name_id
name = attrs.get(name_attr) or ""

await conn.execute(
    """INSERT INTO users (id, tenant_id, email, role)
       VALUES ($1, $2, $3, 'analyst')
       ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email""",
    user_id, tenant_id, email,
)
```

Key changes:
1. Prefix with `saml_` so it cannot collide with Supabase auth user IDs.
2. Scope to `tenant_id:name_id` so cross-tenant collisions are impossible.
3. `ON CONFLICT` updates only `email`, never `tenant_id`.

---

### R11-03 — SAML config endpoints are unauthenticated (IdP hijack)

**File**: `apps/api/app/middleware/auth.py:37-38`
**Problem**: `_should_skip_auth` returns `True` for any path starting with `/api/v1/auth/saml/`. This correctly skips auth for `/login` and `/acs` (which must be unauthenticated), but it also skips auth for `/api/v1/auth/saml/config`. Anyone can PUT a new SAML configuration for any tenant (just set `X-Tenant-ID` header), pointing the IdP to an attacker-controlled server, then log in via SAML to get tokens.

**Fix**: Narrow the skip rule to only the two unauthenticated SAML endpoints:

```python
# In _should_skip_auth, REMOVE this line:
#   if path.startswith("/api/v1/auth/saml/"):
#       return True

# The specific login/acs paths are already in SKIP_AUTH_PATHS, so no replacement needed.
# If you want to keep the startswith for future sub-paths under login/acs:
def _should_skip_auth(path: str) -> bool:
    if path in SKIP_AUTH_PATHS:
        return True
    if path.startswith("/api/v1/health") or path.startswith("/docs") or path.startswith("/redoc"):
        return True
    # Only skip auth for SAML login and ACS, NOT config
    if path in ("/api/v1/auth/saml/login", "/api/v1/auth/saml/acs"):
        return True
    return False
```

Also add an admin role check in the SAML config endpoints (GET/PUT `/auth/saml/config`).

---

## HIGH

### R11-04 — SAML JWT issued without expiry claim

**File**: `apps/api/app/routers/auth_saml.py:141-145`
**Problem**: The JWT has no `exp` claim. The auth middleware has `verify_exp: True` but python-jose skips verification when `exp` is absent (it doesn't require it by default). Result: SAML tokens never expire.

**Fix**: Add expiry to the JWT payload:

```python
from datetime import UTC, datetime, timedelta

SAML_TOKEN_LIFETIME_SECONDS = 3600  # 1 hour

token = jose_jwt.encode(
    {
        "sub": user_id,
        "app_metadata": {"tenant_id": tenant_id},
        "aud": "va-saml",
        "email": email,
        "iat": int(datetime.now(UTC).timestamp()),
        "exp": int((datetime.now(UTC) + timedelta(seconds=SAML_TOKEN_LIFETIME_SECONDS)).timestamp()),
    },
    settings.supabase_jwt_secret,
    algorithm="HS256",
)
```

---

### R11-05 — `_scale_numerics` corrupts non-monetary values in board pack export

**File**: `apps/api/app/routers/board_packs.py:402-410`
**Problem**: The function recursively multiplies ALL numeric values by the FX rate. This corrupts non-monetary fields like `period_index`, `period_ordinal`, `count`, `confidence_score`, `sample_count`, percentages, and any ID that happens to be numeric. For example, `period_index: 3` becomes `4.5` at a 1.5x rate.

**Fix**: Use a key-based skiplist for known non-monetary fields:

```python
_NON_MONETARY_KEYS = frozenset({
    "period_index", "period_ordinal", "period_number", "count", "sample_count",
    "n_periods", "num_periods", "confidence", "confidence_score",
    "variance_pct", "variance_percent", "utilisation_pct", "pct",
    "p25", "p75",  # already percentile markers
    "id", "version",
})

def _scale_numerics(obj: Any, rate: float, _key: str | None = None) -> Any:
    """Recursively multiply monetary numeric values by rate (VA-P8-01 currency conversion).
    Skips known non-monetary keys."""
    if _key and _key.lower() in _NON_MONETARY_KEYS:
        return obj
    if isinstance(obj, (int, float)):
        return obj * rate
    if isinstance(obj, dict):
        return {k: _scale_numerics(v, rate, _key=k) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_scale_numerics(v, rate, _key=_key) for v in obj]
    return obj
```

Update the call sites (lines 482-483) to call without the `_key` param (top-level call):
```python
statements = _scale_numerics(copy.deepcopy(statements), rate)
kpis = _scale_numerics(copy.deepcopy(kpis), rate)
```

---

### R11-06 — `create_budget_from_template_impl` references undefined `x_tenant_id`

**File**: `apps/api/app/routers/budgets.py:291`
**Problem**: Inside `create_budget_from_template_impl`, the parameter is `tenant_id` but line 291 uses `x_tenant_id` (which only exists in the route handler scope). This causes a `NameError` at runtime when creating budget periods — breaking both `/budgets/from-template` and `/marketplace/templates/{id}/use`.

**Fix**: Change `x_tenant_id` to `tenant_id` on line 291:

```python
# Line 287-298: change x_tenant_id → tenant_id
await conn.execute(
    """INSERT INTO budget_periods (tenant_id, budget_id, period_id, period_ordinal, period_start, period_end, label)
       VALUES ($1, $2, $3, $4, $5::date, $6::date, $7)
       ON CONFLICT (tenant_id, budget_id, period_ordinal) DO NOTHING""",
    tenant_id,       # <-- was x_tenant_id (NameError)
    budget_id,
    period_id,
    ord,
    start,
    end,
    f"P{ord}",
)
```

---

## MEDIUM

### R11-07 — Frontend auth callback ignores SAML tokens

**File**: `apps/web/app/auth/callback/route.ts`
**Problem**: The SAML ACS (`auth_saml.py:147`) redirects to `/auth/callback?token=xxx&tenant_id=yyy`, but the frontend callback route only handles the `code` parameter (Supabase OAuth flow). When a SAML user arrives, `code` is null, so they're redirected to `/login?error=auth_callback_failed`.

**Fix**: Add a branch to handle the SAML `token` parameter:

```typescript
export async function GET(request: NextRequest) {
  const { searchParams, origin } = request.nextUrl;
  const code = searchParams.get("code");
  const token = searchParams.get("token");
  const next = searchParams.get("next") ?? "/baselines";

  const safeNext =
    next && next.startsWith("/") && !next.startsWith("//")
      ? next
      : "/baselines";

  // SAML SSO flow: token is a JWT issued by the API
  if (token) {
    const tenantId = searchParams.get("tenant_id") ?? "";
    // Store the SAML JWT in a secure httpOnly cookie or localStorage
    // so subsequent API calls include it in the Authorization header.
    const response = NextResponse.redirect(new URL(safeNext, origin));
    response.cookies.set("va-saml-token", token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge: 3600,
      path: "/",
    });
    if (tenantId) {
      response.cookies.set("va-tenant-id", tenantId, {
        httpOnly: false,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        maxAge: 3600,
        path: "/",
      });
    }
    return response;
  }

  // Existing Supabase OAuth flow
  if (code) {
    // ... existing code ...
  }
  // ...
}
```

> Note: The frontend API client also needs updating to read the SAML cookie and send it as `Authorization: Bearer` on API calls. This is a follow-up task beyond the scope of this fix.

---

### R11-08 — `team_pool` rule assigns from any tenant team

**File**: `apps/api/app/routers/workflows.py:108-114`
**Problem**: The `team_pool` assignee rule selects `LIMIT 1` from ALL team members across the entire tenant (`WHERE tenant_id = $1`), ignoring any `team_id` in the stage config. This means the wrong team's member could be assigned.

**Fix**: Use `config.team_id` if provided, fall back to all-teams only if no team is specified:

```python
if rule == "team_pool":
    team_id = config.get("team_id")
    if team_id:
        row = await conn.fetchrow(
            """SELECT user_id FROM team_members
               WHERE tenant_id = $1 AND team_id = $2
               ORDER BY random() LIMIT 1""",
            tenant_id, team_id,
        )
    else:
        row = await conn.fetchrow(
            """SELECT user_id FROM team_members
               WHERE tenant_id = $1
               ORDER BY random() LIMIT 1""",
            tenant_id,
        )
    if row:
        return row["user_id"]
```

Also uses `ORDER BY random()` for round-robin fairness instead of deterministic `LIMIT 1`.

---

### R11-09 — SAMLRequest not URL-encoded for HTTP-Redirect binding

**File**: `apps/api/app/routers/auth_saml.py:60-63`
**Problem**: The base64-encoded SAMLRequest is appended directly to the redirect URL without URL-encoding. Base64 can contain `+`, `/`, and `=` characters that have special meaning in URLs. Per the SAML HTTP-Redirect binding spec, the request should also be DEFLATE-compressed before base64 encoding.

**Fix**:

```python
import zlib
from urllib.parse import quote

# DEFLATE compress, base64 encode, URL encode (SAML HTTP-Redirect binding)
deflated = zlib.compress(authn_request.encode())[2:-4]  # strip zlib header/checksum
saml_request_b64 = base64.b64encode(deflated).decode()
# ...
return RedirectResponse(
    url=f"{idp_url}{sep}SAMLRequest={quote(saml_request_b64)}&RelayState={quote(tenant_id)}",
)
```

This also URL-encodes `RelayState` (the tenant_id).

---

### R11-10 — SAML entity_id lookup depends on superuser RLS bypass

**File**: `apps/api/app/routers/auth_saml.py:103-106`
**Problem**: In `saml_acs`, when `tenant_id` is not in RelayState, the code looks up `tenant_saml_config` by `entity_id` without setting `app.tenant_id` first. The `tenant_saml_config` table has RLS (`tenant_id = current_tenant_id()`). This query only succeeds because `get_conn()` connects as the `postgres` superuser, which bypasses RLS. If the connection role changes or `FORCE ROW LEVEL SECURITY` is added, this breaks silently (returns no rows → 400 error).

**Fix**: Either:
1. Add an index on `entity_id` and use a function that bypasses RLS for this specific lookup, OR
2. Temporarily disable RLS for this query (not recommended), OR
3. **(Recommended)** Query with `SET LOCAL ROLE` or use a dedicated security-definer function:

```sql
-- In a new migration, create a security-definer lookup function:
CREATE OR REPLACE FUNCTION lookup_saml_tenant_by_entity_id(p_entity_id text)
RETURNS text
LANGUAGE sql SECURITY DEFINER STABLE AS $$
    SELECT tenant_id FROM tenant_saml_config WHERE entity_id = p_entity_id LIMIT 1;
$$;
```

Then in Python:
```python
if not tenant_id:
    issuer = root.find(".//saml:Issuer", NS)
    entity_id = issuer.text if issuer is not None and issuer.text else None
    if entity_id:
        tenant_id = await conn.fetchval(
            "SELECT lookup_saml_tenant_by_entity_id($1)",
            entity_id,
        )
```

---

## LOW

### R11-11 — `RUN_ALL_PENDING_MIGRATIONS.sql` header still stale (R10-10 unfixed)

**File**: `apps/api/app/db/migrations/RUN_ALL_PENDING_MIGRATIONS.sql:2`
**Problem**: Header still says "0008 through 0028" — should be "0008 through 0040".

**Fix**: Update line 2:
```sql
-- Virtual Analyst — Pending migrations (0008 through 0040)
```

---

## R10 Fixes Verification

| ID | Title | Status |
|----|-------|--------|
| R10-01 | XSS via primary_color | **FIXED** — `re.fullmatch` validation in board_pack_export.py:60 |
| R10-02 | XSS via logo_url | **FIXED** — protocol check in board_pack_export.py:63 |
| R10-03 | Budget submit missing transaction | **FIXED** — `conn.transaction()` in budgets.py:627 |
| R10-04 | Workflow update not in transaction | **FIXED** — `conn.transaction()` in workflows.py:204 |
| R10-05 | Workflow transition validation | **FIXED** — `allowed_transitions` dict in workflows.py:214 |
| R10-06 | Budget FK error for template | **FIXED** — catches `ForeignKeyViolationError` in budgets.py:646 |
| R10-07 | burn_rate wrong calculation | **FIXED** — `total_actual / n_actual_periods` in budgets.py:447 |
| R10-08 | format shadows builtin | **FIXED** — renamed to `export_format` with alias in board_packs.py:416 |
| R10-09 | Unconventional import | Assumed fixed (not re-audited) |
| R10-10 | RUN_ALL header mismatch | **NOT FIXED** — see R11-11 |

---

## Summary

| Severity | Count | IDs |
|----------|-------|-----|
| CRITICAL | 3 | R11-01, R11-02, R11-03 |
| HIGH | 3 | R11-04, R11-05, R11-06 |
| MEDIUM | 4 | R11-07, R11-08, R11-09, R11-10 |
| LOW | 1 | R11-11 |
| **Total** | **11** | |

All 3 CRITICAL issues are in the SAML SSO implementation (`auth_saml.py` + `auth.py` middleware). The SAML feature should be considered non-production-ready until R11-01 through R11-03 are resolved.

---

## Verification Checklist

After applying fixes, verify:

1. [ ] `auth_saml.py` — SAML ACS rejects unsigned responses in non-dev environments (R11-01)
2. [ ] `auth_saml.py` — SAML user_id is deterministically derived with `saml_` prefix, never overwrites tenant_id on conflict (R11-02)
3. [ ] `auth.py` middleware — `/api/v1/auth/saml/config` requires authentication; only `/login` and `/acs` skip auth (R11-03)
4. [ ] `auth_saml.py` — JWT includes `exp` and `iat` claims (R11-04)
5. [ ] `board_packs.py` — `_scale_numerics` skips non-monetary keys like `period_index`, `count`, `confidence_score` (R11-05)
6. [ ] `budgets.py` — `create_budget_from_template_impl` uses `tenant_id` not `x_tenant_id` on line 291 (R11-06)
7. [ ] `auth/callback/route.ts` — handles `token` query param for SAML SSO flow (R11-07)
8. [ ] `workflows.py` — `team_pool` rule uses `config.team_id` when available (R11-08)
9. [ ] `auth_saml.py` — SAMLRequest is DEFLATE-compressed, base64-encoded, and URL-encoded (R11-09)
10. [ ] `auth_saml.py` — entity_id lookup uses security-definer function or bypasses RLS safely (R11-10)
11. [ ] `RUN_ALL_PENDING_MIGRATIONS.sql` — header says "0008 through 0040" (R11-11)
