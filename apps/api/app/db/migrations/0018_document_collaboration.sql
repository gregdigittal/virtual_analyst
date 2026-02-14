-- VA-P5-04: Document management + collaboration (attachments, comments)

-- ============================================================
-- DOCUMENT ATTACHMENTS
-- ============================================================
create table if not exists document_attachments (
  tenant_id text not null references tenants(id) on delete cascade,
  document_id text not null,
  entity_type text not null,
  entity_id text not null,
  filename text not null,
  content_type text not null default 'application/octet-stream',
  file_size bigint not null default 0,
  created_at timestamptz not null default now(),
  created_by text references users(id) on delete set null,
  primary key (tenant_id, document_id)
);
alter table document_attachments add column if not exists file_size bigint not null default 0;
create index if not exists idx_document_attachments_entity on document_attachments(tenant_id, entity_type, entity_id);

-- ============================================================
-- COMMENTS
-- ============================================================
create table if not exists comments (
  tenant_id text not null references tenants(id) on delete cascade,
  comment_id text not null,
  entity_type text not null,
  entity_id text not null,
  parent_comment_id text,
  body text not null,
  created_at timestamptz not null default now(),
  created_by text references users(id) on delete set null,
  primary key (tenant_id, comment_id),
  foreign key (tenant_id, parent_comment_id) references comments(tenant_id, comment_id) on delete cascade
);
create index if not exists idx_comments_entity on comments(tenant_id, entity_type, entity_id);
create index if not exists idx_comments_created on comments(tenant_id, created_at desc);

-- ============================================================
-- RLS
-- ============================================================
alter table document_attachments enable row level security;
drop policy if exists "document_attachments_select" on document_attachments;
drop policy if exists "document_attachments_insert" on document_attachments;
drop policy if exists "document_attachments_delete" on document_attachments;
create policy "document_attachments_select" on document_attachments for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "document_attachments_insert" on document_attachments for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "document_attachments_delete" on document_attachments for delete using (tenant_id = current_setting('app.tenant_id', true));

alter table comments enable row level security;
drop policy if exists "comments_select" on comments;
drop policy if exists "comments_insert" on comments;
drop policy if exists "comments_delete" on comments;
create policy "comments_select" on comments for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "comments_insert" on comments for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "comments_delete" on comments for delete using (tenant_id = current_setting('app.tenant_id', true));
