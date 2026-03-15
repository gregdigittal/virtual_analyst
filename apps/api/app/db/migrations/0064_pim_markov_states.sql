-- 0064_pim_markov_states.sql
-- PIM-3.4: 81-state Markov transition matrix storage.
--
-- State space: 3^4 = 81 states defined by 4 dimensions, each discretised to
-- three levels (0=low/negative/declining, 1=medium/neutral/stable, 2=high/positive/improving):
--   gdp_state        (0=contraction, 1=neutral, 2=expansion)
--   sentiment_state  (0=negative, 1=neutral, 2=positive)
--   quality_state    (0=weak, 1=average, 2=strong)
--   momentum_state   (0=declining, 1=stable, 2=improving)
--
-- State index = gdp*27 + sentiment*9 + quality*3 + momentum  (0–80).
-- Transition matrix T[i][j] = P(move to state j | currently in state i).
-- Row sums must equal 1.0 (enforced by application layer, SR-4 Laplace smoothing).
--
-- -- down
-- drop table if exists pim_markov_transitions;
-- drop table if exists pim_markov_matrices;

-- Matrices: one per tenant, versioned by estimated_at timestamp.
create table if not exists pim_markov_matrices (
    tenant_id       text        not null,
    matrix_id       text        not null,
    estimated_at    timestamptz not null default now(),
    n_observations  integer     not null default 0,  -- total transitions observed
    alpha           double precision not null default 1.0,  -- Laplace smoothing parameter (SR-4)
    is_ergodic      boolean,           -- null = not yet checked
    created_at      timestamptz not null default now(),
    primary key (tenant_id, matrix_id)
);

create index if not exists idx_pim_markov_matrices_tenant_ts
    on pim_markov_matrices (tenant_id, estimated_at desc);

-- Row-level security
alter table pim_markov_matrices enable row level security;
create policy "tenant isolation" on pim_markov_matrices
    using (tenant_id = current_setting('app.tenant_id', true));

-- Transition probabilities: 81×81 = 6561 rows per matrix.
-- Stored as individual (from_state, to_state) pairs for easy querying/updating.
create table if not exists pim_markov_transitions (
    tenant_id       text    not null,
    matrix_id       text    not null,
    from_state      integer not null check (from_state >= 0 and from_state <= 80),
    to_state        integer not null check (to_state >= 0 and to_state <= 80),
    probability     double precision not null check (probability >= 0.0 and probability <= 1.0),
    raw_count       integer not null default 0,  -- observed transitions before smoothing
    primary key (tenant_id, matrix_id, from_state, to_state),
    foreign key (tenant_id, matrix_id) references pim_markov_matrices (tenant_id, matrix_id) on delete cascade
);

create index if not exists idx_pim_markov_transitions_from
    on pim_markov_transitions (tenant_id, matrix_id, from_state);

-- Row-level security
alter table pim_markov_transitions enable row level security;
create policy "tenant isolation" on pim_markov_transitions
    using (tenant_id = current_setting('app.tenant_id', true));

-- State vector lookup: human-readable labels for each of the 81 states.
-- This is a reference table (no tenant isolation — shared across tenants).
create table if not exists pim_markov_state_labels (
    state_index     integer primary key check (state_index >= 0 and state_index <= 80),
    gdp_state       integer not null check (gdp_state in (0, 1, 2)),
    sentiment_state integer not null check (sentiment_state in (0, 1, 2)),
    quality_state   integer not null check (quality_state in (0, 1, 2)),
    momentum_state  integer not null check (momentum_state in (0, 1, 2)),
    label           text    not null   -- e.g. "expansion/positive/strong/improving"
);

-- Seed all 81 state labels
insert into pim_markov_state_labels (state_index, gdp_state, sentiment_state, quality_state, momentum_state, label)
select
    g*27 + s*9 + q*3 + m as state_index,
    g, s, q, m,
    array['contraction','neutral','expansion'][g+1] || '/' ||
    array['negative','neutral','positive'][s+1] || '/' ||
    array['weak','average','strong'][q+1] || '/' ||
    array['declining','stable','improving'][m+1] as label
from
    generate_series(0,2) g,
    generate_series(0,2) s,
    generate_series(0,2) q,
    generate_series(0,2) m
on conflict (state_index) do nothing;
