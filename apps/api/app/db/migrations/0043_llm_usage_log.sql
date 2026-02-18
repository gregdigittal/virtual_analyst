-- FIX-C03: Persist LLM usage for metering (survives restarts, no data loss).

create table if not exists llm_usage_log (
    id bigint generated always as identity primary key,
    tenant_id text not null references tenants(id) on delete cascade,
    provider text not null default 'unknown',
    tokens_total int not null default 0,
    calls int not null default 1,
    estimated_usd numeric(12, 6) not null default 0,
    period text not null default to_char(now(), 'YYYY-MM'),
    created_at timestamptz not null default now()
);

create index if not exists idx_llm_usage_log_tenant_period on llm_usage_log(tenant_id, period);
comment on table llm_usage_log is 'One row per LLM call for usage metering; aggregated by get_usage()';

alter table llm_usage_log enable row level security;
drop policy if exists llm_usage_log_select on llm_usage_log;
drop policy if exists llm_usage_log_insert on llm_usage_log;
create policy llm_usage_log_select on llm_usage_log
    for select using (tenant_id = current_tenant_id());
create policy llm_usage_log_insert on llm_usage_log
    for insert with check (tenant_id = current_tenant_id());
-- Intentionally no UPDATE/DELETE policies: llm_usage_log is append-only
