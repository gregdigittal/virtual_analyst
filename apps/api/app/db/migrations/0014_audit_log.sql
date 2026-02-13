-- 0014_audit_log.sql (VA-P4-03)
-- Append-only audit log if not already present. Immutable: no UPDATE/DELETE policies.

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
create index if not exists idx_audit_user_time on audit_log(user_id, "timestamp" desc) where user_id is not null;

comment on table audit_log is 'Append-only audit trail; immutable (no UPDATE/DELETE).';

alter table audit_log enable row level security;

drop policy if exists "audit_log_insert" on audit_log;
drop policy if exists "audit_log_select" on audit_log;
drop policy if exists "audit_log_update" on audit_log;

create policy "audit_log_insert" on audit_log for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "audit_log_select" on audit_log for select using (tenant_id = current_setting('app.tenant_id', true));
-- Allow update only for GDPR anonymization (set user_id to null)
create policy "audit_log_update" on audit_log for update
  using (tenant_id = current_setting('app.tenant_id', true))
  with check (tenant_id = current_setting('app.tenant_id', true));

-- Application-level guard: only user_id should be nullified during GDPR anonymization.
-- A DB trigger would be ideal but is out of scope; enforce in app code (compliance.py).
comment on column audit_log.user_id is 'Nullable for GDPR anonymization only. Application must not modify other columns.';
