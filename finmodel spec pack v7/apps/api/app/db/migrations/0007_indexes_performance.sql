-- 0007_indexes_performance.sql
-- Indexes for list-baselines and list-runs per PERFORMANCE_SPEC (<50ms P95).
-- List baselines: WHERE tenant_id = $1 ORDER BY created_at DESC
-- List runs: WHERE tenant_id = $1 ORDER BY created_at DESC

create index if not exists idx_model_baselines_tenant_created
  on model_baselines(tenant_id, created_at desc);

create index if not exists idx_runs_tenant_created
  on runs(tenant_id, created_at desc);
