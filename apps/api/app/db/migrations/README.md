# Database migrations

Run migrations in order against your Postgres database.

## Order

1. **Baseline (required first)**  
   - `0001_init.sql` — tenants, users, draft_sessions, model_baselines, model_changesets, ventures, venture_artifacts, runs, run_artifacts  
   - `0002_functions_and_rls.sql` — `current_tenant_id()`, `generate_id()`, RLS on all baseline tables  

2. **Pending (0008–0027)**  
   - Either run **`RUN_ALL_PENDING_MIGRATIONS.sql`** in one go, or run `0008_notifications.sql` through `0027_notifications_id_text.sql` in numeric order.

## Example

```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/finmodel_dev"

psql "$DATABASE_URL" -f apps/api/app/db/migrations/0001_init.sql
psql "$DATABASE_URL" -f apps/api/app/db/migrations/0002_functions_and_rls.sql
psql "$DATABASE_URL" -f apps/api/app/db/migrations/RUN_ALL_PENDING_MIGRATIONS.sql
```

## Supabase

Enable Auth and Storage in the Supabase project; configure env vars (`DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`) per `.env.example`.
