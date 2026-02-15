-- VA-P6-05: Review & correction pipeline (reviews, change_summaries)
-- Review decisions: approve, request_changes, reject
-- Inline corrections: {path, old_value, new_value, reason}

create table if not exists reviews (
  tenant_id text not null references tenants(id) on delete cascade,
  review_id text not null,
  assignment_id text not null,
  reviewer_user_id text not null references users(id) on delete cascade,
  decision text not null check (decision in ('approved', 'request_changes', 'rejected')),
  notes text,
  corrections_json jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  primary key (tenant_id, review_id),
  foreign key (tenant_id, assignment_id) references task_assignments(tenant_id, assignment_id) on delete cascade
);
create index if not exists idx_reviews_assignment on reviews(tenant_id, assignment_id);
create index if not exists idx_reviews_reviewer on reviews(tenant_id, reviewer_user_id);

create table if not exists change_summaries (
  tenant_id text not null references tenants(id) on delete cascade,
  summary_id text not null,
  review_id text not null,
  summary_text text not null,
  learning_points_json jsonb default '[]'::jsonb,
  created_at timestamptz not null default now(),
  primary key (tenant_id, summary_id),
  foreign key (tenant_id, review_id) references reviews(tenant_id, review_id) on delete cascade
);
create index if not exists idx_change_summaries_review on change_summaries(tenant_id, review_id);

alter table reviews enable row level security;
drop policy if exists "reviews_select" on reviews;
drop policy if exists "reviews_insert" on reviews;
drop policy if exists "reviews_update" on reviews;
drop policy if exists "reviews_delete" on reviews;
create policy "reviews_select" on reviews for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "reviews_insert" on reviews for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "reviews_update" on reviews for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "reviews_delete" on reviews for delete using (tenant_id = current_setting('app.tenant_id', true));

alter table change_summaries enable row level security;
drop policy if exists "change_summaries_select" on change_summaries;
drop policy if exists "change_summaries_insert" on change_summaries;
drop policy if exists "change_summaries_update" on change_summaries;
drop policy if exists "change_summaries_delete" on change_summaries;
create policy "change_summaries_select" on change_summaries for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "change_summaries_insert" on change_summaries for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "change_summaries_update" on change_summaries for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "change_summaries_delete" on change_summaries for delete using (tenant_id = current_setting('app.tenant_id', true));
