# Feature B (Organization Hierarchy) – DB changes and SQL scripts

## Summary

Feature B adds **one new migration**, **0045_org_structures.sql**. No changes are required to existing tables. All new objects are in this migration.

### New objects (migration 0045)

| Object | Description |
|--------|-------------|
| **org_structures** | Top-level group (tenant, org_id, group_name, reporting_currency, status, consolidation_method, eliminate_intercompany, minority_interest_treatment, created_at, created_by, updated_at) |
| **org_entities** | Entities in a group (tenant, org_id, entity_id, name, entity_type, currency, country_iso, tax fields, is_root, baseline_id, status) |
| **org_ownership_links** | Parent–child ownership (tenant, org_id, parent_entity_id, child_entity_id, ownership_pct, voting_pct, consolidation_method, effective_date) |
| **org_intercompany_links** | Intercompany links (tenant, org_id, link_id, from_entity_id, to_entity_id, link_type, description, driver_ref, amount_or_rate, frequency, withholding_tax_applicable) |
| **consolidated_runs** | Run queue and results (tenant_id, consolidated_run_id, org_id, status, created_by, entity_run_ids, consolidation_adjustments_json, fx_rates_used_json, error_message, created_at, completed_at) |

All tables:

- Reference `tenants(id)` (and optionally `users(id)` where needed).
- Use RLS with `current_tenant_id()` (from migration 0002).
- Have appropriate indexes and constraints.

No other schema changes were introduced. The existing **fx_rates** table (from migration 0036) is used for consolidation FX when the full run flow is implemented.

---

## Option 1: Apply only migration 0045

If migrations 0001–0044 are already applied and you only need to add Feature B:

```bash
# From project root, against your target DB (set DATABASE_URL or use psql -f)
psql "$DATABASE_URL" -f apps/api/app/db/migrations/0045_org_structures.sql
```

Or run the contents of **0045_org_structures.sql** in your SQL client.

---

## Option 2: Apply all pending migrations (0008 through 0045)

If you use the combined “pending” script that includes 0008–0045:

```bash
psql "$DATABASE_URL" -f apps/api/app/db/migrations/RUN_ALL_PENDING_MIGRATIONS.sql
```

---

## Option 3: Full apply (all migrations from scratch)

To apply the entire migration history including 0045:

```bash
psql "$DATABASE_URL" -f apps/api/app/db/migrations/APPLY_ALL_MIGRATIONS.sql
```

**Prerequisites:** Migrations 0001–0002 must be applicable (tenants, users, `current_tenant_id()`). If you already have a DB with earlier migrations applied, use Option 1 or 2 instead.

---

## Verification

After applying 0045 (or the full/pending script), you can verify:

```sql
-- Expect 5 new tables
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('org_structures', 'org_entities', 'org_ownership_links', 'org_intercompany_links', 'consolidated_runs')
ORDER BY table_name;
```

You should see all five tables. RLS is enabled on each; ensure your session sets `current_tenant_id()` (or equivalent) when testing tenant-scoped access.
