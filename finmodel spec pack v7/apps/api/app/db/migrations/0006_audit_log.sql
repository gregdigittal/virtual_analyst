-- 0006_audit_log.sql
-- Append-only audit log for baseline/run events (Phase 1).
-- RLS: only INSERT allowed; no UPDATE/DELETE policies.

create table if not exists audit_log (
  audit_event_id text primary key,
  tenant_id text not null,
  user_id text,
  event_type text not null,
  event_category text not null,
  "timestamp" timestamptz not null default now(),
  resource_type text not null,
  resource_id text not null,
  event_data jsonb not null default '{}',
  checksum text not null
);

create index if not exists idx_audit_tenant_time on audit_log(tenant_id, "timestamp" desc);
create index if not exists idx_audit_event_type on audit_log(event_type, "timestamp" desc);
create index if not exists idx_audit_resource on audit_log(resource_type, resource_id);

comment on table audit_log is 'Append-only audit trail for baseline and run events';

-- RLS: allow only INSERT (append-only). No UPDATE/DELETE policies.
alter table audit_log enable row level security;

create policy "audit_log_insert" on audit_log
  for insert with check (true);

-- Optional: allow select by tenant for future admin/export (use same as other tables: current_tenant_id()).
-- For Phase 1 we rely on service role or no SELECT policy; API does not read audit_log yet.
create policy "audit_log_select" on audit_log
  for select using (tenant_id = current_setting('app.tenant_id', true));
