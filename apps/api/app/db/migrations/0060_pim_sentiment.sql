-- 0060_pim_sentiment.sql
-- PIM-1.2: Raw per-source sentiment signals (partitioned by month).
-- PIM-1.3: Weekly/monthly aggregated sentiment per company (partitioned by month).
--
-- FR-1.2: per-company sentiment score in [-1, +1] with confidence in [0, 1]
-- FR-1.3: aggregate to weekly and monthly time-series per company
-- FR-1.5: tenant-scoped storage; no cross-tenant data leakage

-- ============================================================
-- PIM-1.2: pim_sentiment_signals (partitioned parent)
-- ============================================================

create table if not exists pim_sentiment_signals (
  tenant_id         text not null,
  signal_id         text not null,
  company_id        text not null,
  source_type       text not null,              -- 'news_api', 'earnings_transcript', 'sec_filing', 'social'
  source_ref        text,                       -- external URL or document reference
  headline          text,                       -- article headline or snippet title
  published_at      timestamptz not null,       -- when the source material was published
  sentiment_score   double precision not null    -- [-1.0, +1.0]
    check (sentiment_score >= -1.0 and sentiment_score <= 1.0),
  confidence        double precision not null    -- [0.0, 1.0]
    check (confidence >= 0.0 and confidence <= 1.0),
  raw_text_excerpt  text,                       -- text snippet used for LLM extraction
  llm_model         text,                       -- model identifier used for extraction
  extraction_meta   jsonb not null default '{}'::jsonb,  -- additional LLM output details
  created_at        timestamptz not null default now(),
  primary key (tenant_id, signal_id, published_at)
) partition by range (published_at);

-- Create initial monthly partitions (6 months back + 6 months forward)
create table if not exists pim_sentiment_signals_2025_10 partition of pim_sentiment_signals
  for values from ('2025-10-01') to ('2025-11-01');
create table if not exists pim_sentiment_signals_2025_11 partition of pim_sentiment_signals
  for values from ('2025-11-01') to ('2025-12-01');
create table if not exists pim_sentiment_signals_2025_12 partition of pim_sentiment_signals
  for values from ('2025-12-01') to ('2026-01-01');
create table if not exists pim_sentiment_signals_2026_01 partition of pim_sentiment_signals
  for values from ('2026-01-01') to ('2026-02-01');
create table if not exists pim_sentiment_signals_2026_02 partition of pim_sentiment_signals
  for values from ('2026-02-01') to ('2026-03-01');
create table if not exists pim_sentiment_signals_2026_03 partition of pim_sentiment_signals
  for values from ('2026-03-01') to ('2026-04-01');
create table if not exists pim_sentiment_signals_2026_04 partition of pim_sentiment_signals
  for values from ('2026-04-01') to ('2026-05-01');
create table if not exists pim_sentiment_signals_2026_05 partition of pim_sentiment_signals
  for values from ('2026-05-01') to ('2026-06-01');
create table if not exists pim_sentiment_signals_2026_06 partition of pim_sentiment_signals
  for values from ('2026-06-01') to ('2026-07-01');
create table if not exists pim_sentiment_signals_2026_07 partition of pim_sentiment_signals
  for values from ('2026-07-01') to ('2026-08-01');
create table if not exists pim_sentiment_signals_2026_08 partition of pim_sentiment_signals
  for values from ('2026-08-01') to ('2026-09-01');
create table if not exists pim_sentiment_signals_2026_09 partition of pim_sentiment_signals
  for values from ('2026-09-01') to ('2026-10-01');

-- Indexes on partitioned parent (automatically created on each partition)
create index if not exists idx_pim_signals_tenant_company
  on pim_sentiment_signals (tenant_id, company_id, published_at desc);
create index if not exists idx_pim_signals_source
  on pim_sentiment_signals (tenant_id, source_type, published_at desc);
create index if not exists idx_pim_signals_published
  on pim_sentiment_signals (published_at desc);

-- RLS
alter table pim_sentiment_signals enable row level security;

create policy pim_sentiment_signals_tenant_isolation on pim_sentiment_signals
  using (tenant_id = current_setting('app.tenant_id', true))
  with check (tenant_id = current_setting('app.tenant_id', true));

-- ============================================================
-- PIM-1.3: pim_sentiment_aggregates (partitioned parent)
-- ============================================================

create table if not exists pim_sentiment_aggregates (
  tenant_id         text not null,
  company_id        text not null,
  period_type       text not null               -- 'weekly' or 'monthly'
    check (period_type in ('weekly', 'monthly')),
  period_start      date not null,              -- first day of the aggregation period
  period_end        date not null,              -- last day of the aggregation period
  avg_sentiment     double precision not null    -- weighted average sentiment [-1, +1]
    check (avg_sentiment >= -1.0 and avg_sentiment <= 1.0),
  median_sentiment  double precision,           -- median sentiment score
  min_sentiment     double precision,           -- minimum sentiment in period
  max_sentiment     double precision,           -- maximum sentiment in period
  std_sentiment     double precision,           -- standard deviation of scores
  signal_count      integer not null default 0, -- number of raw signals aggregated
  avg_confidence    double precision,           -- average confidence of constituent signals
  source_breakdown  jsonb not null default '{}'::jsonb,  -- {"news_api": 5, "earnings_transcript": 2, ...}
  trend_direction   text                        -- 'improving', 'stable', 'declining'
    check (trend_direction is null or trend_direction in ('improving', 'stable', 'declining')),
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  primary key (tenant_id, company_id, period_type, period_start)
) partition by range (period_start);

-- Create initial monthly partitions (6 months back + 6 months forward)
create table if not exists pim_sentiment_aggregates_2025_10 partition of pim_sentiment_aggregates
  for values from ('2025-10-01') to ('2025-11-01');
create table if not exists pim_sentiment_aggregates_2025_11 partition of pim_sentiment_aggregates
  for values from ('2025-11-01') to ('2025-12-01');
create table if not exists pim_sentiment_aggregates_2025_12 partition of pim_sentiment_aggregates
  for values from ('2025-12-01') to ('2026-01-01');
create table if not exists pim_sentiment_aggregates_2026_01 partition of pim_sentiment_aggregates
  for values from ('2026-01-01') to ('2026-02-01');
create table if not exists pim_sentiment_aggregates_2026_02 partition of pim_sentiment_aggregates
  for values from ('2026-02-01') to ('2026-03-01');
create table if not exists pim_sentiment_aggregates_2026_03 partition of pim_sentiment_aggregates
  for values from ('2026-03-01') to ('2026-04-01');
create table if not exists pim_sentiment_aggregates_2026_04 partition of pim_sentiment_aggregates
  for values from ('2026-04-01') to ('2026-05-01');
create table if not exists pim_sentiment_aggregates_2026_05 partition of pim_sentiment_aggregates
  for values from ('2026-05-01') to ('2026-06-01');
create table if not exists pim_sentiment_aggregates_2026_06 partition of pim_sentiment_aggregates
  for values from ('2026-06-01') to ('2026-07-01');
create table if not exists pim_sentiment_aggregates_2026_07 partition of pim_sentiment_aggregates
  for values from ('2026-07-01') to ('2026-08-01');
create table if not exists pim_sentiment_aggregates_2026_08 partition of pim_sentiment_aggregates
  for values from ('2026-08-01') to ('2026-09-01');
create table if not exists pim_sentiment_aggregates_2026_09 partition of pim_sentiment_aggregates
  for values from ('2026-09-01') to ('2026-10-01');

-- Indexes on partitioned parent
create index if not exists idx_pim_agg_tenant_company
  on pim_sentiment_aggregates (tenant_id, company_id, period_type, period_start desc);
create index if not exists idx_pim_agg_trend
  on pim_sentiment_aggregates (tenant_id, trend_direction, period_start desc);

-- RLS
alter table pim_sentiment_aggregates enable row level security;

create policy pim_sentiment_aggregates_tenant_isolation on pim_sentiment_aggregates
  using (tenant_id = current_setting('app.tenant_id', true))
  with check (tenant_id = current_setting('app.tenant_id', true));

-- updated_at trigger for aggregates
create or replace function pim_sentiment_aggregates_updated_at() returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_pim_sentiment_agg_updated on pim_sentiment_aggregates;
create trigger trg_pim_sentiment_agg_updated
  before update on pim_sentiment_aggregates
  for each row execute function pim_sentiment_aggregates_updated_at();

-- NOTE: For production, consider enabling pg_partman for automatic monthly partition creation:
--   SELECT partman.create_parent('public.pim_sentiment_signals', 'published_at', 'native', 'monthly');
--   SELECT partman.create_parent('public.pim_sentiment_aggregates', 'period_start', 'native', 'monthly');
