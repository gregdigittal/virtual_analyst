-- VA-P8-08: Peer comparison (opt-in, anonymous aggregates). VA-P8-09 uses same aggregates for board pack benchmark.

create table if not exists tenant_benchmark_opt_in (
  tenant_id text not null references tenants(id) on delete cascade,
  industry_segment text not null default 'general',
  size_segment text not null default 'general',
  opted_in_at timestamptz not null default now(),
  primary key (tenant_id)
);

create table if not exists benchmark_aggregates (
  id text primary key default ('bag_' || substr(md5(random()::text), 1, 12)),
  segment_key text not null,
  metric_name text not null,
  median_value numeric not null,
  p25_value numeric,
  p75_value numeric,
  sample_count integer not null default 0,
  computed_at timestamptz not null default now(),
  unique (segment_key, metric_name)
);
create index if not exists idx_benchmark_aggregates_segment on benchmark_aggregates(segment_key, metric_name);

-- No RLS on benchmark_aggregates (read-only shared data). tenant_benchmark_opt_in is per-tenant.
alter table tenant_benchmark_opt_in enable row level security;
drop policy if exists "tenant_benchmark_opt_in_select" on tenant_benchmark_opt_in;
drop policy if exists "tenant_benchmark_opt_in_insert" on tenant_benchmark_opt_in;
drop policy if exists "tenant_benchmark_opt_in_update" on tenant_benchmark_opt_in;
drop policy if exists "tenant_benchmark_opt_in_delete" on tenant_benchmark_opt_in;
create policy "tenant_benchmark_opt_in_select" on tenant_benchmark_opt_in for select using (tenant_id = current_tenant_id());
create policy "tenant_benchmark_opt_in_insert" on tenant_benchmark_opt_in for insert with check (tenant_id = current_tenant_id());
create policy "tenant_benchmark_opt_in_update" on tenant_benchmark_opt_in for update using (tenant_id = current_tenant_id());
create policy "tenant_benchmark_opt_in_delete" on tenant_benchmark_opt_in for delete using (tenant_id = current_tenant_id());
