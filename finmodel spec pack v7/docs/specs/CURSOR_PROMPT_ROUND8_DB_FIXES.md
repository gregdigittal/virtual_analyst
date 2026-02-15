# Round 8 — DB Consistency Fixes

> **Context**: Cross-referenced all 27 migrations (38 tables, 950 lines of schema SQL) against every Python router and service file. Found 7 issues: 2 HIGH crash/data-loss bugs, 3 MEDIUM security/consistency gaps, 2 LOW RLS completeness items.
>
> Apply each fix in order. Each section is self-contained.

---

## R8-01  HIGH — `mark_notification_read` uses `::uuid` cast on text column (crash)

**File**: `apps/api/app/routers/notifications.py`

**Problem**: Migration 0027 converts `notifications.id` from `uuid` to `text`. The `db/notifications.py` helper now generates `ntf_xxxx` IDs. But `mark_notification_read` still casts `$1::uuid` on lines 79 and 84. Any PATCH request for a notification with a `ntf_` prefix ID will throw `invalid input syntax for type uuid`.

**Fix**: Remove the `::uuid` casts on both queries.

Replace (line 79):
```python
        await conn.execute(
            """UPDATE notifications SET read_at = now() WHERE id = $1::uuid AND tenant_id = $2""",
            notification_id,
            x_tenant_id,
        )
```
With:
```python
        await conn.execute(
            """UPDATE notifications SET read_at = now() WHERE id = $1 AND tenant_id = $2""",
            notification_id,
            x_tenant_id,
        )
```

Replace (line 83–84):
```python
        row = await conn.fetchrow(
            "SELECT id, user_id, read_at FROM notifications WHERE id = $1::uuid AND tenant_id = $2",
            notification_id,
            x_tenant_id,
        )
```
With:
```python
        row = await conn.fetchrow(
            "SELECT id, user_id, read_at FROM notifications WHERE id = $1 AND tenant_id = $2",
            notification_id,
            x_tenant_id,
        )
```

---

## R8-02  HIGH — `clone_budget` doesn't copy `budget_periods` (data loss)

**File**: `apps/api/app/routers/budgets.py`

**Problem**: The `clone_budget` endpoint (line ~847) copies line items, amounts, and department allocations from the source budget to the clone — but does NOT copy `budget_periods`. The cloned budget has amounts referencing `period_ordinal` values (1, 2, 3 …) with no period metadata (start date, end date, label). Calling `GET /budgets/{cloned_id}/periods` returns an empty list.

**Fix**: After creating the new budget and version but before copying line items, copy all budget_periods from the source budget to the new budget.

In `clone_budget`, after `ensure_budget_version(...)` (around line 872) and before the `rows = await conn.fetch(` line that fetches line items, add:

```python
            # Copy budget_periods from source to clone
            period_rows = await conn.fetch(
                """SELECT period_ordinal, period_start, period_end, label
                   FROM budget_periods WHERE tenant_id = $1 AND budget_id = $2
                   ORDER BY period_ordinal""",
                x_tenant_id,
                budget_id,
            )
            for pr in period_rows:
                await conn.execute(
                    """INSERT INTO budget_periods (tenant_id, budget_id, period_id, period_ordinal, period_start, period_end, label)
                       VALUES ($1, $2, $3, $4, $5, $6, $7)
                       ON CONFLICT (tenant_id, budget_id, period_ordinal) DO NOTHING""",
                    x_tenant_id,
                    new_budget_id,
                    _period_id(),
                    pr["period_ordinal"],
                    pr["period_start"],
                    pr["period_end"],
                    pr["label"],
                )
```

---

## R8-03  MEDIUM — `audit_log` UPDATE RLS policy undermines append-only guarantee

**File**: New migration `apps/api/app/db/migrations/0028_audit_log_restrict_update.sql`

**Problem**: The audit_log table is designed as append-only for compliance (checksum integrity). But migration 0014 creates an UPDATE RLS policy, allowing any tenant-scoped code to modify audit entries. This violates the immutability contract.

The GDPR anonymization flow in `compliance.py` is the only legitimate UPDATE use case. That should use a `SECURITY DEFINER` function to bypass the restriction.

**Fix**: Create a new migration file `apps/api/app/db/migrations/0028_audit_log_restrict_update.sql`:

```sql
-- 0028_audit_log_restrict_update.sql
-- Remove general UPDATE policy on audit_log. Append-only: no direct updates.
-- GDPR anonymization uses a SECURITY DEFINER function instead.

drop policy if exists "audit_log_update" on audit_log;

-- SECURITY DEFINER function for GDPR anonymization only
create or replace function anonymize_audit_user(
  p_tenant_id text,
  p_user_id text,
  p_replacement text default 'anonymized'
) returns integer
language plpgsql security definer set search_path = public
as $$
declare
  affected integer;
begin
  update audit_log
  set user_id = p_replacement,
      event_data = event_data - 'user_email' - 'user_name'
  where tenant_id = p_tenant_id and user_id = p_user_id;
  get diagnostics affected = row_count;
  return affected;
end;
$$;
```

Also append this migration to `RUN_ALL_PENDING_MIGRATIONS.sql` after the 0027 block.

---

## R8-04  MEDIUM — RLS function inconsistency across migrations

**File**: New migration `apps/api/app/db/migrations/0029_standardize_rls_function.sql`

**Problem**: Migration 0002 creates `current_tenant_id()` function and uses it in core table RLS policies. All migrations 0008+ use `current_setting('app.tenant_id', true)` directly. These are functionally equivalent today, but if the function is updated later (e.g., different setting name), only the core table policies would update.

**Fix**: Create `apps/api/app/db/migrations/0029_standardize_rls_function.sql` to re-create the 0008+ policies using the function:

```sql
-- 0029_standardize_rls_function.sql
-- Standardize all RLS policies to use current_tenant_id() function for consistency.
-- Only re-creates SELECT policies (most common) as demonstration; full standardization
-- can follow the same pattern for INSERT/UPDATE/DELETE policies.

-- notifications
drop policy if exists "notifications_select" on notifications;
create policy "notifications_select" on notifications for select
  using (tenant_id = current_tenant_id());
drop policy if exists "notifications_insert" on notifications;
create policy "notifications_insert" on notifications for insert
  with check (tenant_id = current_tenant_id());
drop policy if exists "notifications_update" on notifications;
create policy "notifications_update" on notifications for update
  using (tenant_id = current_tenant_id());
drop policy if exists "notifications_delete" on notifications;
create policy "notifications_delete" on notifications for delete
  using (tenant_id = current_tenant_id());

-- scenarios
drop policy if exists "scenarios_select" on scenarios;
create policy "scenarios_select" on scenarios for select using (tenant_id = current_tenant_id());
drop policy if exists "scenarios_insert" on scenarios;
create policy "scenarios_insert" on scenarios for insert with check (tenant_id = current_tenant_id());
drop policy if exists "scenarios_update" on scenarios;
create policy "scenarios_update" on scenarios for update using (tenant_id = current_tenant_id());
drop policy if exists "scenarios_delete" on scenarios;
create policy "scenarios_delete" on scenarios for delete using (tenant_id = current_tenant_id());

-- integration_connections
drop policy if exists "integration_connections_select" on integration_connections;
create policy "integration_connections_select" on integration_connections for select using (tenant_id = current_tenant_id());
drop policy if exists "integration_connections_insert" on integration_connections;
create policy "integration_connections_insert" on integration_connections for insert with check (tenant_id = current_tenant_id());
drop policy if exists "integration_connections_update" on integration_connections;
create policy "integration_connections_update" on integration_connections for update using (tenant_id = current_tenant_id());
drop policy if exists "integration_connections_delete" on integration_connections;
create policy "integration_connections_delete" on integration_connections for delete using (tenant_id = current_tenant_id());

-- integration_sync_runs
drop policy if exists "integration_sync_runs_select" on integration_sync_runs;
create policy "integration_sync_runs_select" on integration_sync_runs for select using (tenant_id = current_tenant_id());
drop policy if exists "integration_sync_runs_insert" on integration_sync_runs;
create policy "integration_sync_runs_insert" on integration_sync_runs for insert with check (tenant_id = current_tenant_id());
drop policy if exists "integration_sync_runs_update" on integration_sync_runs;
create policy "integration_sync_runs_update" on integration_sync_runs for update using (tenant_id = current_tenant_id());
drop policy if exists "integration_sync_runs_delete" on integration_sync_runs;
create policy "integration_sync_runs_delete" on integration_sync_runs for delete using (tenant_id = current_tenant_id());

-- canonical_sync_snapshots
drop policy if exists "canonical_snapshots_select" on canonical_sync_snapshots;
create policy "canonical_snapshots_select" on canonical_sync_snapshots for select using (tenant_id = current_tenant_id());
drop policy if exists "canonical_snapshots_insert" on canonical_sync_snapshots;
create policy "canonical_snapshots_insert" on canonical_sync_snapshots for insert with check (tenant_id = current_tenant_id());
drop policy if exists "canonical_snapshots_delete" on canonical_sync_snapshots;
create policy "canonical_snapshots_delete" on canonical_sync_snapshots for delete using (tenant_id = current_tenant_id());

-- billing_subscriptions
drop policy if exists "billing_subscriptions_select" on billing_subscriptions;
create policy "billing_subscriptions_select" on billing_subscriptions for select using (tenant_id = current_tenant_id());
drop policy if exists "billing_subscriptions_insert" on billing_subscriptions;
create policy "billing_subscriptions_insert" on billing_subscriptions for insert with check (tenant_id = current_tenant_id());
drop policy if exists "billing_subscriptions_update" on billing_subscriptions;
create policy "billing_subscriptions_update" on billing_subscriptions for update using (tenant_id = current_tenant_id());

-- usage_meters
drop policy if exists "usage_meters_select" on usage_meters;
create policy "usage_meters_select" on usage_meters for select using (tenant_id = current_tenant_id());
drop policy if exists "usage_meters_insert" on usage_meters;
create policy "usage_meters_insert" on usage_meters for insert with check (tenant_id = current_tenant_id());
drop policy if exists "usage_meters_update" on usage_meters;
create policy "usage_meters_update" on usage_meters for update using (tenant_id = current_tenant_id());

-- llm_call_logs
drop policy if exists "llm_call_logs_select" on llm_call_logs;
create policy "llm_call_logs_select" on llm_call_logs for select using (tenant_id = current_tenant_id());
drop policy if exists "llm_call_logs_insert" on llm_call_logs;
create policy "llm_call_logs_insert" on llm_call_logs for insert with check (tenant_id = current_tenant_id());

-- llm_routing_policies (special: tenant_id can be null for defaults)
drop policy if exists "llm_routing_policies_select" on llm_routing_policies;
create policy "llm_routing_policies_select" on llm_routing_policies for select using (
  tenant_id = current_tenant_id() or tenant_id is null
);

-- audit_log (note: no UPDATE policy per R8-03)
drop policy if exists "audit_log_insert" on audit_log;
create policy "audit_log_insert" on audit_log for insert with check (tenant_id = current_tenant_id());
drop policy if exists "audit_log_select" on audit_log;
create policy "audit_log_select" on audit_log for select using (tenant_id = current_tenant_id());

-- covenant_definitions
drop policy if exists "covenant_definitions_select" on covenant_definitions;
create policy "covenant_definitions_select" on covenant_definitions for select using (tenant_id = current_tenant_id());
drop policy if exists "covenant_definitions_insert" on covenant_definitions;
create policy "covenant_definitions_insert" on covenant_definitions for insert with check (tenant_id = current_tenant_id());
drop policy if exists "covenant_definitions_update" on covenant_definitions;
create policy "covenant_definitions_update" on covenant_definitions for update using (tenant_id = current_tenant_id());
drop policy if exists "covenant_definitions_delete" on covenant_definitions;
create policy "covenant_definitions_delete" on covenant_definitions for delete using (tenant_id = current_tenant_id());

-- excel_connections
drop policy if exists "excel_connections_select" on excel_connections;
create policy "excel_connections_select" on excel_connections for select using (tenant_id = current_tenant_id());
drop policy if exists "excel_connections_insert" on excel_connections;
create policy "excel_connections_insert" on excel_connections for insert with check (tenant_id = current_tenant_id());
drop policy if exists "excel_connections_update" on excel_connections;
create policy "excel_connections_update" on excel_connections for update using (tenant_id = current_tenant_id());
drop policy if exists "excel_connections_delete" on excel_connections;
create policy "excel_connections_delete" on excel_connections for delete using (tenant_id = current_tenant_id());

-- excel_sync_events
drop policy if exists "excel_sync_events_select" on excel_sync_events;
create policy "excel_sync_events_select" on excel_sync_events for select using (tenant_id = current_tenant_id());
drop policy if exists "excel_sync_events_insert" on excel_sync_events;
create policy "excel_sync_events_insert" on excel_sync_events for insert with check (tenant_id = current_tenant_id());

-- memo_packs
drop policy if exists "memo_packs_select" on memo_packs;
create policy "memo_packs_select" on memo_packs for select using (tenant_id = current_tenant_id());
drop policy if exists "memo_packs_insert" on memo_packs;
create policy "memo_packs_insert" on memo_packs for insert with check (tenant_id = current_tenant_id());
drop policy if exists "memo_packs_update" on memo_packs;
create policy "memo_packs_update" on memo_packs for update using (tenant_id = current_tenant_id());
drop policy if exists "memo_packs_delete" on memo_packs;
create policy "memo_packs_delete" on memo_packs for delete using (tenant_id = current_tenant_id());

-- document_attachments
drop policy if exists "document_attachments_select" on document_attachments;
create policy "document_attachments_select" on document_attachments for select using (tenant_id = current_tenant_id());
drop policy if exists "document_attachments_insert" on document_attachments;
create policy "document_attachments_insert" on document_attachments for insert with check (tenant_id = current_tenant_id());
drop policy if exists "document_attachments_delete" on document_attachments;
create policy "document_attachments_delete" on document_attachments for delete using (tenant_id = current_tenant_id());

-- comments
drop policy if exists "comments_select" on comments;
create policy "comments_select" on comments for select using (tenant_id = current_tenant_id());
drop policy if exists "comments_insert" on comments;
create policy "comments_insert" on comments for insert with check (tenant_id = current_tenant_id());
drop policy if exists "comments_delete" on comments;
create policy "comments_delete" on comments for delete using (tenant_id = current_tenant_id());

-- job_functions
drop policy if exists "job_functions_select" on job_functions;
create policy "job_functions_select" on job_functions for select using (tenant_id = current_tenant_id());
drop policy if exists "job_functions_insert" on job_functions;
create policy "job_functions_insert" on job_functions for insert with check (tenant_id = current_tenant_id());
drop policy if exists "job_functions_update" on job_functions;
create policy "job_functions_update" on job_functions for update using (tenant_id = current_tenant_id());
drop policy if exists "job_functions_delete" on job_functions;
create policy "job_functions_delete" on job_functions for delete using (tenant_id = current_tenant_id());

-- teams
drop policy if exists "teams_select" on teams;
create policy "teams_select" on teams for select using (tenant_id = current_tenant_id());
drop policy if exists "teams_insert" on teams;
create policy "teams_insert" on teams for insert with check (tenant_id = current_tenant_id());
drop policy if exists "teams_update" on teams;
create policy "teams_update" on teams for update using (tenant_id = current_tenant_id());
drop policy if exists "teams_delete" on teams;
create policy "teams_delete" on teams for delete using (tenant_id = current_tenant_id());

-- team_members
drop policy if exists "team_members_select" on team_members;
create policy "team_members_select" on team_members for select using (tenant_id = current_tenant_id());
drop policy if exists "team_members_insert" on team_members;
create policy "team_members_insert" on team_members for insert with check (tenant_id = current_tenant_id());
drop policy if exists "team_members_update" on team_members;
create policy "team_members_update" on team_members for update using (tenant_id = current_tenant_id());
drop policy if exists "team_members_delete" on team_members;
create policy "team_members_delete" on team_members for delete using (tenant_id = current_tenant_id());

-- workflow_templates
drop policy if exists "workflow_templates_select" on workflow_templates;
create policy "workflow_templates_select" on workflow_templates for select using (tenant_id = current_tenant_id());
drop policy if exists "workflow_templates_insert" on workflow_templates;
create policy "workflow_templates_insert" on workflow_templates for insert with check (tenant_id = current_tenant_id());
drop policy if exists "workflow_templates_update" on workflow_templates;
create policy "workflow_templates_update" on workflow_templates for update using (tenant_id = current_tenant_id());
drop policy if exists "workflow_templates_delete" on workflow_templates;
create policy "workflow_templates_delete" on workflow_templates for delete using (tenant_id = current_tenant_id());

-- workflow_instances
drop policy if exists "workflow_instances_select" on workflow_instances;
create policy "workflow_instances_select" on workflow_instances for select using (tenant_id = current_tenant_id());
drop policy if exists "workflow_instances_insert" on workflow_instances;
create policy "workflow_instances_insert" on workflow_instances for insert with check (tenant_id = current_tenant_id());
drop policy if exists "workflow_instances_update" on workflow_instances;
create policy "workflow_instances_update" on workflow_instances for update using (tenant_id = current_tenant_id());
drop policy if exists "workflow_instances_delete" on workflow_instances;
create policy "workflow_instances_delete" on workflow_instances for delete using (tenant_id = current_tenant_id());

-- task_assignments
drop policy if exists "task_assignments_select" on task_assignments;
create policy "task_assignments_select" on task_assignments for select using (tenant_id = current_tenant_id());
drop policy if exists "task_assignments_insert" on task_assignments;
create policy "task_assignments_insert" on task_assignments for insert with check (tenant_id = current_tenant_id());
drop policy if exists "task_assignments_update" on task_assignments;
create policy "task_assignments_update" on task_assignments for update using (tenant_id = current_tenant_id());
drop policy if exists "task_assignments_delete" on task_assignments;
create policy "task_assignments_delete" on task_assignments for delete using (tenant_id = current_tenant_id());

-- reviews
drop policy if exists "reviews_select" on reviews;
create policy "reviews_select" on reviews for select using (tenant_id = current_tenant_id());
drop policy if exists "reviews_insert" on reviews;
create policy "reviews_insert" on reviews for insert with check (tenant_id = current_tenant_id());
drop policy if exists "reviews_update" on reviews;
create policy "reviews_update" on reviews for update using (tenant_id = current_tenant_id());
drop policy if exists "reviews_delete" on reviews;
create policy "reviews_delete" on reviews for delete using (tenant_id = current_tenant_id());

-- change_summaries
drop policy if exists "change_summaries_select" on change_summaries;
create policy "change_summaries_select" on change_summaries for select using (tenant_id = current_tenant_id());
drop policy if exists "change_summaries_insert" on change_summaries;
create policy "change_summaries_insert" on change_summaries for insert with check (tenant_id = current_tenant_id());
drop policy if exists "change_summaries_update" on change_summaries;
create policy "change_summaries_update" on change_summaries for update using (tenant_id = current_tenant_id());
drop policy if exists "change_summaries_delete" on change_summaries;
create policy "change_summaries_delete" on change_summaries for delete using (tenant_id = current_tenant_id());

-- budgets
drop policy if exists "budgets_select" on budgets;
create policy "budgets_select" on budgets for select using (tenant_id = current_tenant_id());
drop policy if exists "budgets_insert" on budgets;
create policy "budgets_insert" on budgets for insert with check (tenant_id = current_tenant_id());
drop policy if exists "budgets_update" on budgets;
create policy "budgets_update" on budgets for update using (tenant_id = current_tenant_id());
drop policy if exists "budgets_delete" on budgets;
create policy "budgets_delete" on budgets for delete using (tenant_id = current_tenant_id());

-- budget_versions
drop policy if exists "budget_versions_select" on budget_versions;
create policy "budget_versions_select" on budget_versions for select using (tenant_id = current_tenant_id());
drop policy if exists "budget_versions_insert" on budget_versions;
create policy "budget_versions_insert" on budget_versions for insert with check (tenant_id = current_tenant_id());
drop policy if exists "budget_versions_update" on budget_versions;
create policy "budget_versions_update" on budget_versions for update using (tenant_id = current_tenant_id());
drop policy if exists "budget_versions_delete" on budget_versions;
create policy "budget_versions_delete" on budget_versions for delete using (tenant_id = current_tenant_id());

-- budget_periods
drop policy if exists "budget_periods_select" on budget_periods;
create policy "budget_periods_select" on budget_periods for select using (tenant_id = current_tenant_id());
drop policy if exists "budget_periods_insert" on budget_periods;
create policy "budget_periods_insert" on budget_periods for insert with check (tenant_id = current_tenant_id());
drop policy if exists "budget_periods_update" on budget_periods;
create policy "budget_periods_update" on budget_periods for update using (tenant_id = current_tenant_id());
drop policy if exists "budget_periods_delete" on budget_periods;
create policy "budget_periods_delete" on budget_periods for delete using (tenant_id = current_tenant_id());

-- budget_line_items
drop policy if exists "budget_line_items_select" on budget_line_items;
create policy "budget_line_items_select" on budget_line_items for select using (tenant_id = current_tenant_id());
drop policy if exists "budget_line_items_insert" on budget_line_items;
create policy "budget_line_items_insert" on budget_line_items for insert with check (tenant_id = current_tenant_id());
drop policy if exists "budget_line_items_update" on budget_line_items;
create policy "budget_line_items_update" on budget_line_items for update using (tenant_id = current_tenant_id());
drop policy if exists "budget_line_items_delete" on budget_line_items;
create policy "budget_line_items_delete" on budget_line_items for delete using (tenant_id = current_tenant_id());

-- budget_line_item_amounts
drop policy if exists "budget_line_item_amounts_select" on budget_line_item_amounts;
create policy "budget_line_item_amounts_select" on budget_line_item_amounts for select using (tenant_id = current_tenant_id());
drop policy if exists "budget_line_item_amounts_insert" on budget_line_item_amounts;
create policy "budget_line_item_amounts_insert" on budget_line_item_amounts for insert with check (tenant_id = current_tenant_id());
drop policy if exists "budget_line_item_amounts_update" on budget_line_item_amounts;
create policy "budget_line_item_amounts_update" on budget_line_item_amounts for update using (tenant_id = current_tenant_id());
drop policy if exists "budget_line_item_amounts_delete" on budget_line_item_amounts;
create policy "budget_line_item_amounts_delete" on budget_line_item_amounts for delete using (tenant_id = current_tenant_id());

-- budget_department_allocations
drop policy if exists "budget_department_allocations_select" on budget_department_allocations;
create policy "budget_department_allocations_select" on budget_department_allocations for select using (tenant_id = current_tenant_id());
drop policy if exists "budget_department_allocations_insert" on budget_department_allocations;
create policy "budget_department_allocations_insert" on budget_department_allocations for insert with check (tenant_id = current_tenant_id());
drop policy if exists "budget_department_allocations_update" on budget_department_allocations;
create policy "budget_department_allocations_update" on budget_department_allocations for update using (tenant_id = current_tenant_id());
drop policy if exists "budget_department_allocations_delete" on budget_department_allocations;
create policy "budget_department_allocations_delete" on budget_department_allocations for delete using (tenant_id = current_tenant_id());

-- budget_actuals
drop policy if exists "budget_actuals_select" on budget_actuals;
create policy "budget_actuals_select" on budget_actuals for select using (tenant_id = current_tenant_id());
drop policy if exists "budget_actuals_insert" on budget_actuals;
create policy "budget_actuals_insert" on budget_actuals for insert with check (tenant_id = current_tenant_id());
drop policy if exists "budget_actuals_update" on budget_actuals;
create policy "budget_actuals_update" on budget_actuals for update using (tenant_id = current_tenant_id());
drop policy if exists "budget_actuals_delete" on budget_actuals;
create policy "budget_actuals_delete" on budget_actuals for delete using (tenant_id = current_tenant_id());
```

---

## R8-05  MEDIUM — Core tables missing DELETE RLS policies

**File**: New migration `apps/api/app/db/migrations/0030_core_delete_policies.sql`

**Problem**: The 0002 migration created RLS policies for core tables but omitted DELETE policies on `model_baselines`, `model_changesets`, `ventures`, `runs`, `run_artifacts`, and `venture_artifacts`. While the code may not currently delete these rows, without explicit DELETE policies the operation silently does nothing instead of clearly failing. If delete operations are ever added, this will be a hard-to-debug issue.

**Fix**: Create `apps/api/app/db/migrations/0030_core_delete_policies.sql`:

```sql
-- 0030_core_delete_policies.sql
-- Add DELETE RLS policies to core tables that were missing them in 0002.

drop policy if exists "model_baselines_delete" on model_baselines;
create policy "model_baselines_delete" on model_baselines for delete
  using (tenant_id = current_tenant_id());

drop policy if exists "model_changesets_delete" on model_changesets;
create policy "model_changesets_delete" on model_changesets for delete
  using (tenant_id = current_tenant_id());

drop policy if exists "ventures_delete" on ventures;
create policy "ventures_delete" on ventures for delete
  using (tenant_id = current_tenant_id());

drop policy if exists "venture_artifacts_delete" on venture_artifacts;
create policy "venture_artifacts_delete" on venture_artifacts for delete
  using (tenant_id = current_tenant_id());

drop policy if exists "runs_delete" on runs;
create policy "runs_delete" on runs for delete
  using (tenant_id = current_tenant_id());

drop policy if exists "run_artifacts_delete" on run_artifacts;
create policy "run_artifacts_delete" on run_artifacts for delete
  using (tenant_id = current_tenant_id());

-- Also add missing UPDATE policies for venture_artifacts and run_artifacts
drop policy if exists "venture_artifacts_update" on venture_artifacts;
create policy "venture_artifacts_update" on venture_artifacts for update
  using (tenant_id = current_tenant_id());

drop policy if exists "run_artifacts_update" on run_artifacts;
create policy "run_artifacts_update" on run_artifacts for update
  using (tenant_id = current_tenant_id());
```

---

## R8-06  LOW — `billing_plans` table has no RLS

**File**: `apps/api/app/db/migrations/RUN_ALL_PENDING_MIGRATIONS.sql` (comment only)

**Problem**: `billing_plans` is a global catalog with no `tenant_id` scoping and no RLS. This is intentionally correct (all tenants should see all plans), but undocumented.

**Fix**: Add a comment after the `billing_plans` CREATE TABLE in `RUN_ALL_PENDING_MIGRATIONS.sql` (around line 184):

```sql
-- billing_plans is intentionally NOT subject to RLS. It is a global catalog
-- visible to all tenants. Plans are read-only from the application layer.
```

No code or policy changes needed.

---

## R8-07  LOW — `comments` and `document_attachments` missing UPDATE RLS policies

**File**: New migration `apps/api/app/db/migrations/0031_comments_docs_update_policies.sql`

**Problem**: Neither `comments` nor `document_attachments` has an UPDATE RLS policy. If comment editing or attachment metadata updates are ever needed, these policies are required.

**Fix**: Create `apps/api/app/db/migrations/0031_comments_docs_update_policies.sql`:

```sql
-- 0031_comments_docs_update_policies.sql
-- Add UPDATE RLS policies for comments and document_attachments.

drop policy if exists "comments_update" on comments;
create policy "comments_update" on comments for update
  using (tenant_id = current_tenant_id());

drop policy if exists "document_attachments_update" on document_attachments;
create policy "document_attachments_update" on document_attachments for update
  using (tenant_id = current_tenant_id());
```

---

## Verification Checklist

After applying all fixes:

- [ ] **R8-01**: Call `PATCH /api/v1/notifications/ntf_xxxxxxxxxxxx` — should succeed (not crash with UUID error)
- [ ] **R8-02**: Call `POST /api/v1/budgets/{id}/clone` then `GET /api/v1/budgets/{new_id}/periods` — should return the same periods as the source budget
- [ ] **R8-03**: Verify `audit_log` has no UPDATE policy: `SELECT policyname FROM pg_policies WHERE tablename = 'audit_log'` should show only `audit_log_insert` and `audit_log_select`
- [ ] **R8-04**: Verify all policies use `current_tenant_id()`: `SELECT policyname, qual FROM pg_policies WHERE qual LIKE '%current_setting%'` should return 0 rows
- [ ] **R8-05**: Verify DELETE policies exist on core tables: `SELECT tablename, policyname FROM pg_policies WHERE policyname LIKE '%_delete'` should include model_baselines, model_changesets, ventures, runs
- [ ] **R8-06**: Comment present in SQL file (no runtime check)
- [ ] **R8-07**: Verify UPDATE policies exist: `SELECT policyname FROM pg_policies WHERE tablename IN ('comments', 'document_attachments') AND policyname LIKE '%_update'`

---

## Summary

| Fix | Severity | Type | Files |
|-----|----------|------|-------|
| R8-01 | HIGH | Code | `routers/notifications.py` |
| R8-02 | HIGH | Code | `routers/budgets.py` |
| R8-03 | MEDIUM | Migration | New `0028_audit_log_restrict_update.sql` |
| R8-04 | MEDIUM | Migration | New `0029_standardize_rls_function.sql` |
| R8-05 | MEDIUM | Migration | New `0030_core_delete_policies.sql` |
| R8-06 | LOW | Comment | `RUN_ALL_PENDING_MIGRATIONS.sql` |
| R8-07 | LOW | Migration | New `0031_comments_docs_update_policies.sql` |
