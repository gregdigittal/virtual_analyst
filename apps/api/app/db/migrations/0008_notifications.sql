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
