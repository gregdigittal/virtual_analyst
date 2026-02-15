# Round 9 — Post-DB-Fix Review

> **Context**: Reviewed all code changes since Round 8 — Cursor's implementation of all 7 R8 fixes (4 modified files, 5 new migration files). All R8 fixes verified correct. Found 1 LOW documentation mismatch.
>
> Apply the fix below.

---

## R9-01  LOW — `RUN_ALL_PENDING_MIGRATIONS.sql` header claims 0008–0031 but only contains 0008–0028

**File**: `apps/api/app/db/migrations/RUN_ALL_PENDING_MIGRATIONS.sql`

**Problem**: The file header on line 2 was updated to say "0008 through 0031", but only migration 0028 was actually appended. Migrations 0029, 0030, and 0031 are NOT in this file. Anyone following the header would believe the file is complete when it is not.

Since `APPLY_ALL_MIGRATIONS.sql` is now the preferred single-file path (and correctly contains 0008–0031), the simplest fix is to correct the header to reflect the actual content.

**Fix**: Change line 2 from:

```sql
-- Virtual Analyst — Pending migrations (0008 through 0031)
```

To:

```sql
-- Virtual Analyst — Pending migrations (0008 through 0028)
```

Also update line 3 to clarify the scope:

```sql
-- Run in order against your database. Skip any you have already applied.
```

Replace with:

```sql
-- For migrations 0008-0028 only. For the full set (0008-0031), use APPLY_ALL_MIGRATIONS.sql instead.
```

---

## Verification Checklist — All R8 Fixes Confirmed

The following R8 fixes were reviewed and verified as correctly implemented. No changes needed.

| Fix | File(s) | Verified |
|-----|---------|----------|
| R8-01 Remove `::uuid` cast | `apps/api/app/routers/notifications.py` lines 79, 84 | OK |
| R8-02 Copy `budget_periods` in clone | `apps/api/app/routers/budgets.py` lines 874–894 | OK |
| R8-03 Drop audit_log UPDATE policy + GDPR function | `0028_audit_log_restrict_update.sql` | OK |
| R8-04 Standardize all RLS to `current_tenant_id()` | `0029_standardize_rls_function.sql` — all 30 tables | OK |
| R8-05 Add DELETE policies to core tables | `0030_core_delete_policies.sql` — 6 tables + bonus UPDATE on venture_artifacts/run_artifacts | OK |
| R8-06 Document billing_plans intentional no-RLS | `APPLY_ALL_MIGRATIONS.sql` lines 187–188 | OK |
| R8-07 Add UPDATE policies to comments/document_attachments | `0031_comments_docs_update_policies.sql` | OK |
| GET DIAGNOSTICS syntax fix | `0028`, `APPLY_ALL_MIGRATIONS.sql`, `RUN_ALL_PENDING_MIGRATIONS.sql` — `ROW_COUNT` (no parens) | OK |

## RLS Coverage Summary — 40 Tables Verified

All RLS policies now consistently use `current_tenant_id()`. Coverage is complete:

- **Full CRUD (S/I/U/D)**: 30 tables
- **Intentionally restricted**: audit_log (append-only), excel_sync_events (append-only), llm_call_logs (immutable), llm_routing_policies (system-managed), billing_subscriptions (no DELETE), usage_meters (no DELETE), canonical_sync_snapshots (no UPDATE), tenants (SELECT+UPDATE only)
- **No RLS (intentional)**: billing_plans (global catalog, documented in R8-06)
