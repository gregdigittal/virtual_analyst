-- VA-P6-01: Team & hierarchy data model (teams, team_members, job_functions)

-- ============================================================
-- JOB FUNCTIONS (per-tenant; seed defaults on first use via API)
-- ============================================================
create table if not exists job_functions (
  tenant_id text not null references tenants(id) on delete cascade,
  job_function_id text not null,
  name text not null,
  created_at timestamptz not null default now(),
  primary key (tenant_id, job_function_id)
);
create index if not exists idx_job_functions_tenant on job_functions(tenant_id);

-- Seed default job functions for all existing tenants (new tenants get defaults via API in P6-02)
insert into job_functions (tenant_id, job_function_id, name)
select t.id, v.job_function_id, v.name
from tenants t
cross join (values
  ('jf_analyst', 'Analyst'),
  ('jf_senior_analyst', 'Senior Analyst'),
  ('jf_manager', 'Manager'),
  ('jf_director', 'Director'),
  ('jf_cfo', 'CFO')
) as v(job_function_id, name)
on conflict (tenant_id, job_function_id) do nothing;

-- ============================================================
-- TEAMS
-- ============================================================
create table if not exists teams (
  tenant_id text not null references tenants(id) on delete cascade,
  team_id text not null,
  name text not null,
  description text,
  created_at timestamptz not null default now(),
  created_by text references users(id) on delete set null,
  primary key (tenant_id, team_id)
);
create index if not exists idx_teams_tenant on teams(tenant_id);

-- ============================================================
-- TEAM MEMBERS (reports_to = user_id of manager; API must ensure same team)
-- ============================================================
create table if not exists team_members (
  tenant_id text not null references tenants(id) on delete cascade,
  team_id text not null,
  user_id text not null references users(id) on delete cascade,
  job_function_id text not null,
  reports_to text references users(id) on delete set null,
  created_at timestamptz not null default now(),
  primary key (tenant_id, team_id, user_id),
  foreign key (tenant_id, team_id) references teams(tenant_id, team_id) on delete cascade,
  foreign key (tenant_id, job_function_id) references job_functions(tenant_id, job_function_id) on delete restrict
);
comment on column team_members.reports_to is 'Manager user_id; API must validate they are in same (tenant_id, team_id).';
create index if not exists idx_team_members_team on team_members(tenant_id, team_id);
create index if not exists idx_team_members_user on team_members(tenant_id, user_id);
create index if not exists idx_team_members_reports_to on team_members(tenant_id, team_id, reports_to) where reports_to is not null;

-- ============================================================
-- RLS
-- ============================================================
alter table job_functions enable row level security;
drop policy if exists "job_functions_select" on job_functions;
drop policy if exists "job_functions_insert" on job_functions;
drop policy if exists "job_functions_update" on job_functions;
drop policy if exists "job_functions_delete" on job_functions;
create policy "job_functions_select" on job_functions for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "job_functions_insert" on job_functions for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "job_functions_update" on job_functions for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "job_functions_delete" on job_functions for delete using (tenant_id = current_setting('app.tenant_id', true));

alter table teams enable row level security;
drop policy if exists "teams_select" on teams;
drop policy if exists "teams_insert" on teams;
drop policy if exists "teams_update" on teams;
drop policy if exists "teams_delete" on teams;
create policy "teams_select" on teams for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "teams_insert" on teams for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "teams_update" on teams for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "teams_delete" on teams for delete using (tenant_id = current_setting('app.tenant_id', true));

alter table team_members enable row level security;
drop policy if exists "team_members_select" on team_members;
drop policy if exists "team_members_insert" on team_members;
drop policy if exists "team_members_update" on team_members;
drop policy if exists "team_members_delete" on team_members;
create policy "team_members_select" on team_members for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "team_members_insert" on team_members for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "team_members_update" on team_members for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "team_members_delete" on team_members for delete using (tenant_id = current_setting('app.tenant_id', true));
