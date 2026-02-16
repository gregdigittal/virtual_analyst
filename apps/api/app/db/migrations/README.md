# Database migrations

Run migrations in order against your Postgres database.

## Order

1. **Baseline (required first)**  
   - `0001_init.sql` — tenants, users, draft_sessions, model_baselines, model_changesets, ventures, venture_artifacts, runs, run_artifacts  
   - `0002_functions_and_rls.sql` — `current_tenant_id()`, `generate_id()`, RLS on all baseline tables  

2. **Pending (0008–0040)**  
   - **Preferred:** Run **`APPLY_ALL_MIGRATIONS.sql`** once — it applies all migrations 0008 through 0040 in order.  
   - Alternative: Run **`RUN_ALL_PENDING_MIGRATIONS.sql`** (through 0028), then `0029` through `0040` in numeric order.

## Example

```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/finmodel_dev"

psql "$DATABASE_URL" -f apps/api/app/db/migrations/0001_init.sql
psql "$DATABASE_URL" -f apps/api/app/db/migrations/0002_functions_and_rls.sql
psql "$DATABASE_URL" -f apps/api/app/db/migrations/RUN_ALL_PENDING_MIGRATIONS.sql
```

## Supabase

Enable Auth and Storage in the Supabase project; configure env vars (`DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`) per `.env.example`.
