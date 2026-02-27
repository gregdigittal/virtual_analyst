-- 0056_afs_analytics.sql — AFS Phase 5: analytics snapshots

create table if not exists afs_analytics (
  tenant_id text not null references tenants(id) on delete cascade,
  analytics_id text not null,
  engagement_id text not null,
  computed_at timestamptz not null default now(),
  ratios_json jsonb not null default '{}'::jsonb,
  trends_json jsonb not null default '[]'::jsonb,
  benchmark_comparison_json jsonb not null default '{}'::jsonb,
  anomalies_json jsonb not null default '[]'::jsonb,
  commentary_json jsonb,
  going_concern_json jsonb,
  industry_segment text,
  status text not null check (status in ('computed','stale','error')) default 'computed',
  error_message text,
  computed_by text references users(id) on delete set null,
  primary key (tenant_id, analytics_id),
  foreign key (tenant_id, engagement_id) references afs_engagements(tenant_id, engagement_id) on delete cascade
);
create index if not exists idx_afs_analytics_engagement on afs_analytics(tenant_id, engagement_id);

-- RLS
alter table afs_analytics enable row level security;
drop policy if exists "afs_analytics_select" on afs_analytics;
drop policy if exists "afs_analytics_insert" on afs_analytics;
drop policy if exists "afs_analytics_update" on afs_analytics;
drop policy if exists "afs_analytics_delete" on afs_analytics;
create policy "afs_analytics_select" on afs_analytics for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_analytics_insert" on afs_analytics for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_analytics_update" on afs_analytics for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_analytics_delete" on afs_analytics for delete using (tenant_id = current_setting('app.tenant_id', true));
