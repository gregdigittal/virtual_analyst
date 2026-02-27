-- 0054_afs_reviews_tax.sql — AFS Phase 3: reviews, review comments, tax computations, temporary differences

-- ============================================================
-- AFS_REVIEWS (review workflow stages and sign-offs)
-- ============================================================
create table if not exists afs_reviews (
  tenant_id text not null references tenants(id) on delete cascade,
  review_id text not null,
  engagement_id text not null,
  stage text not null check (stage in ('preparer_review','manager_review','partner_signoff')),
  status text not null check (status in ('pending','approved','rejected','changes_requested')) default 'pending',
  submitted_by text references users(id) on delete set null,
  submitted_at timestamptz not null default now(),
  reviewed_by text references users(id) on delete set null,
  reviewed_at timestamptz,
  comments text,
  primary key (tenant_id, review_id),
  foreign key (tenant_id, engagement_id) references afs_engagements(tenant_id, engagement_id) on delete cascade
);
create index if not exists idx_afs_reviews_engagement on afs_reviews(tenant_id, engagement_id);

-- ============================================================
-- AFS_REVIEW_COMMENTS (threaded comments per review)
-- ============================================================
create table if not exists afs_review_comments (
  tenant_id text not null references tenants(id) on delete cascade,
  comment_id text not null,
  review_id text not null,
  section_id text,
  parent_comment_id text,
  body text not null,
  resolved boolean not null default false,
  created_by text references users(id) on delete set null,
  created_at timestamptz not null default now(),
  primary key (tenant_id, comment_id),
  foreign key (tenant_id, review_id) references afs_reviews(tenant_id, review_id) on delete cascade,
  foreign key (tenant_id, section_id) references afs_sections(tenant_id, section_id) on delete set null,
  foreign key (tenant_id, parent_comment_id) references afs_review_comments(tenant_id, comment_id) on delete set null
);
create index if not exists idx_afs_review_comments_review on afs_review_comments(tenant_id, review_id);

-- ============================================================
-- AFS_TAX_COMPUTATIONS (tax computation per entity)
-- ============================================================
create table if not exists afs_tax_computations (
  tenant_id text not null references tenants(id) on delete cascade,
  computation_id text not null,
  engagement_id text not null,
  entity_id text,
  jurisdiction text not null default 'ZA',
  statutory_rate numeric(8,4) not null default 0.27,
  taxable_income numeric(18,2) not null default 0,
  current_tax numeric(18,2) not null default 0,
  deferred_tax_json jsonb not null default '{}'::jsonb,
  reconciliation_json jsonb not null default '[]'::jsonb,
  tax_note_json jsonb,
  created_by text references users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (tenant_id, computation_id),
  foreign key (tenant_id, engagement_id) references afs_engagements(tenant_id, engagement_id) on delete cascade
);
create index if not exists idx_afs_tax_engagement on afs_tax_computations(tenant_id, engagement_id);

-- ============================================================
-- AFS_TEMPORARY_DIFFERENCES (deferred tax line items)
-- ============================================================
create table if not exists afs_temporary_differences (
  tenant_id text not null references tenants(id) on delete cascade,
  difference_id text not null,
  computation_id text not null,
  description text not null,
  carrying_amount numeric(18,2) not null default 0,
  tax_base numeric(18,2) not null default 0,
  difference numeric(18,2) not null default 0,
  deferred_tax_effect numeric(18,2) not null default 0,
  diff_type text not null check (diff_type in ('asset','liability')) default 'liability',
  primary key (tenant_id, difference_id),
  foreign key (tenant_id, computation_id) references afs_tax_computations(tenant_id, computation_id) on delete cascade
);
create index if not exists idx_afs_temp_diff_computation on afs_temporary_differences(tenant_id, computation_id);

-- ============================================================
-- RLS
-- ============================================================

-- afs_reviews
alter table afs_reviews enable row level security;
drop policy if exists "afs_reviews_select" on afs_reviews;
drop policy if exists "afs_reviews_insert" on afs_reviews;
drop policy if exists "afs_reviews_update" on afs_reviews;
drop policy if exists "afs_reviews_delete" on afs_reviews;
create policy "afs_reviews_select" on afs_reviews for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_reviews_insert" on afs_reviews for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_reviews_update" on afs_reviews for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_reviews_delete" on afs_reviews for delete using (tenant_id = current_setting('app.tenant_id', true));

-- afs_review_comments
alter table afs_review_comments enable row level security;
drop policy if exists "afs_review_comments_select" on afs_review_comments;
drop policy if exists "afs_review_comments_insert" on afs_review_comments;
drop policy if exists "afs_review_comments_update" on afs_review_comments;
drop policy if exists "afs_review_comments_delete" on afs_review_comments;
create policy "afs_review_comments_select" on afs_review_comments for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_review_comments_insert" on afs_review_comments for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_review_comments_update" on afs_review_comments for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_review_comments_delete" on afs_review_comments for delete using (tenant_id = current_setting('app.tenant_id', true));

-- afs_tax_computations
alter table afs_tax_computations enable row level security;
drop policy if exists "afs_tax_computations_select" on afs_tax_computations;
drop policy if exists "afs_tax_computations_insert" on afs_tax_computations;
drop policy if exists "afs_tax_computations_update" on afs_tax_computations;
drop policy if exists "afs_tax_computations_delete" on afs_tax_computations;
create policy "afs_tax_computations_select" on afs_tax_computations for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_tax_computations_insert" on afs_tax_computations for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_tax_computations_update" on afs_tax_computations for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_tax_computations_delete" on afs_tax_computations for delete using (tenant_id = current_setting('app.tenant_id', true));

-- afs_temporary_differences
alter table afs_temporary_differences enable row level security;
drop policy if exists "afs_temporary_differences_select" on afs_temporary_differences;
drop policy if exists "afs_temporary_differences_insert" on afs_temporary_differences;
drop policy if exists "afs_temporary_differences_update" on afs_temporary_differences;
drop policy if exists "afs_temporary_differences_delete" on afs_temporary_differences;
create policy "afs_temporary_differences_select" on afs_temporary_differences for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_temporary_differences_insert" on afs_temporary_differences for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_temporary_differences_update" on afs_temporary_differences for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_temporary_differences_delete" on afs_temporary_differences for delete using (tenant_id = current_setting('app.tenant_id', true));
