-- VA-P3-02: Async MC execution — task_id and progress support
alter table runs add column if not exists task_id text;
alter table runs add column if not exists mc_enabled boolean not null default false;
alter table runs add column if not exists num_simulations integer;
alter table runs add column if not exists seed integer;
alter table runs add column if not exists valuation_config_json jsonb;
alter table runs add column if not exists completed_at timestamptz;
alter table runs add column if not exists error_message text;
