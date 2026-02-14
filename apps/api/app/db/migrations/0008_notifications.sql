-- 0008_notifications.sql
-- In-app notifications for key events (draft ready, run complete, etc.)

create table if not exists notifications (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null references tenants(id) on delete cascade,
  user_id text references users(id) on delete cascade,
  type text not null,
  title text not null,
  body text,
  entity_type text,
  entity_id text,
  read_at timestamptz,
  created_at timestamptz not null default now()
);

create index if not exists idx_notifications_tenant_unread on notifications(tenant_id, read_at) where read_at is null;
create index if not exists idx_notifications_tenant_created on notifications(tenant_id, created_at desc);
create index if not exists idx_notifications_user_unread on notifications(tenant_id, user_id, read_at) where read_at is null;

-- RLS: scope notifications to current tenant
alter table notifications enable row level security;
drop policy if exists "notifications_select" on notifications;
create policy "notifications_select" on notifications for select
  using (tenant_id = current_setting('app.tenant_id', true));
drop policy if exists "notifications_insert" on notifications;
create policy "notifications_insert" on notifications for insert
  with check (tenant_id = current_setting('app.tenant_id', true));
drop policy if exists "notifications_update" on notifications;
create policy "notifications_update" on notifications for update
  using (tenant_id = current_setting('app.tenant_id', true));
drop policy if exists "notifications_delete" on notifications;
create policy "notifications_delete" on notifications for delete
  using (tenant_id = current_setting('app.tenant_id', true));
