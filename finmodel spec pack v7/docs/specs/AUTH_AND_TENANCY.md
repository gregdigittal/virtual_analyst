# Auth & Multi-Tenancy Specification
**Date:** 2026-02-08

## Auth Provider: Supabase Auth
- Email/password login (primary)
- Magic link (optional, for investor access)
- OAuth2: Google, Microsoft (Phase 4+ for enterprise SSO)
- JWT tokens issued by Supabase; verified by FastAPI middleware

## JWT Middleware (FastAPI)
```python
# Every authenticated request:
# 1. Extract JWT from Authorization: Bearer <token>
# 2. Verify signature with Supabase JWT secret
# 3. Extract user_id and tenant_id from claims
# 4. Attach to request state: request.state.user_id, request.state.tenant_id
# 5. All downstream queries filter by tenant_id
```

Custom JWT claims (set via Supabase Auth hook or RPC):
```json
{
  "sub": "u_001",
  "tenant_id": "t_001",
  "role": "analyst",
  "email": "analyst@example.com"
}
```

## Roles and Permissions

### Role Hierarchy
| Role | Description |
|---|---|
| `owner` | Tenant owner. Full access. Can manage billing, users, integrations. |
| `admin` | Can manage users, baselines, runs, integrations. Cannot manage billing. |
| `analyst` | Can create drafts, runs, changesets, memos. Cannot manage users or integrations. |
| `investor` | Read-only. Can view baselines, runs, statements, memos. Cannot create or modify anything. |

### Permission Matrix
| Resource | owner | admin | analyst | investor |
|---|---|---|---|---|
| Tenants (update) | ✓ | ✗ | ✗ | ✗ |
| Users (CRUD) | ✓ | ✓ | ✗ | ✗ |
| Baselines (read) | ✓ | ✓ | ✓ | ✓ |
| Baselines (create/archive) | ✓ | ✓ | ✓ | ✗ |
| Draft Sessions (CRUD) | ✓ | ✓ | ✓ | ✗ |
| Draft Chat (send) | ✓ | ✓ | ✓ | ✗ |
| Commit (execute) | ✓ | ✓ | ✓* | ✗ |
| Changesets (CRUD) | ✓ | ✓ | ✓ | ✗ |
| Runs (create) | ✓ | ✓ | ✓ | ✗ |
| Runs (read) | ✓ | ✓ | ✓ | ✓ |
| Scenarios (CRUD) | ✓ | ✓ | ✓ | ✗ |
| Ventures (CRUD) | ✓ | ✓ | ✓ | ✗ |
| Integrations (CRUD) | ✓ | ✓ | ✗ | ✗ |
| Billing (read) | ✓ | ✓ | ✗ | ✗ |
| Billing (manage) | ✓ | ✗ | ✗ | ✗ |
| Memos (generate) | ✓ | ✓ | ✓ | ✗ |
| Memos (read) | ✓ | ✓ | ✓ | ✓ |
| Excel Push | Per can_push_roles config | | | |
| Excel Pull | ✓ | ✓ | ✓ | ✓ |

\*Analyst commit may require admin approval in enterprise tier (future feature).

### Permission Enforcement
Two layers:
1. **API middleware** — checks role against permission matrix before route handler executes
2. **Supabase RLS** — all tables with tenant_id have policies ensuring row-level isolation

```python
# FastAPI dependency
def require_role(*allowed_roles):
    def checker(request: Request):
        if request.state.role not in allowed_roles:
            raise HTTPException(403, "Insufficient permissions")
    return Depends(checker)

# Usage
@router.post("/api/v1/baselines")
async def create_baseline(request: Request, _=require_role("owner", "admin", "analyst")):
    ...
```

## Row-Level Security (RLS)

### Policy Pattern
Every table with `tenant_id` gets these policies:

```sql
-- Enable RLS
alter table {table} enable row level security;

-- Select: users can only see their tenant's rows
create policy "{table}_select" on {table}
  for select using (
    tenant_id = current_setting('app.tenant_id', true)
  );

-- Insert: users can only insert into their tenant
create policy "{table}_insert" on {table}
  for insert with check (
    tenant_id = current_setting('app.tenant_id', true)
  );

-- Update: users can only update their tenant's rows
create policy "{table}_update" on {table}
  for update using (
    tenant_id = current_setting('app.tenant_id', true)
  );

-- Delete: users can only delete their tenant's rows
create policy "{table}_delete" on {table}
  for delete using (
    tenant_id = current_setting('app.tenant_id', true)
  );
```

### Setting Tenant Context
On every API request, before any DB query:
```python
async def set_tenant_context(db: AsyncSession, tenant_id: str):
    await db.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))
```

This ensures RLS policies filter correctly even if application code has a bug.

## Storage Bucket Isolation
Supabase Storage buckets are per-tenant:
- Bucket name: `tenant-{tenant_id}`
- Storage policies: only authenticated users with matching tenant_id can read/write
- Artifact paths within bucket: `{artifact_type}/{artifact_id}/{version}.json`

## Tenant Provisioning
When a new tenant is created:
1. Insert into `tenants` table
2. Create Supabase Storage bucket
3. Create initial user (owner role)
4. Create default billing subscription (Starter plan, or trial)
5. Seed default routing policy
6. Seed default venture template catalog reference

## Session Management
- JWT expiry: 1 hour
- Refresh token: 7 days
- On token refresh: re-verify user status (not deactivated, tenant active)
- Concurrent sessions: unlimited (stateless JWT)
