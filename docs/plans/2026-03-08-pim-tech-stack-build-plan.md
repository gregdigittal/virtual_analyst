# PIM Tech Stack Build Plan

> Date: 2026-03-08
> Source: `docs/reviews/VA_Tech_Stack_Review_PIM.docx`
> Design Spec: `docs/plans/Portfolio_Intelligence_Module_Design_Spec.docx`
> Backlog: Tiers 6, 7, 8 in `BACKLOG.md`

---

## Overview

This plan translates the VA Tech Stack Review into an actionable build sequence for the Portfolio Intelligence Module (PIM). The review assessed 13 platform components against PIM requirements, identified 4 WEAK areas (time-series storage, async jobs, monitoring, CI/CD) and 10 ADEQUATE/STRONG areas, then produced 18 prioritized actions.

**Key principle:** The existing stack is fundamentally sound. PIM is an *extension*, not a rewrite. The 8 gate items below are mandatory before any PIM code is written.

---

## Cost Impact

| Item | Monthly Cost |
|------|-------------|
| Supabase Large compute (G-04) | ~$100 |
| Sentry Team plan (G-07) | ~$26 |
| BetterUptime (optional) | ~$20 |
| Redis (existing) | $0 (reuse) |
| GitHub Actions (existing) | $0 (free tier) |
| **Total incremental** | **~$220–260/month** |

---

## Phase 0: Gate Items (Mandatory Prerequisites)

All 8 items must be complete before PIM development begins. Sequenced by dependency.

### Sprint G-A: Security & Async Foundation (Week 1–2)

| # | Item | Description | Effort |
|---|------|-------------|--------|
| G-01 | Fix JWKS async race condition | Cache JWKS response with TTL; current code re-fetches on every request under concurrent load. Overlaps CR-S4 | S |
| G-02 | Replace sync Redis with `redis.asyncio` | `redis.Redis` blocks the async event loop; migrate all call sites. Overlaps CR-S5 | S |
| G-06 | Add Structlog structured JSON logging | Replace ad-hoc `print`/`logging` with structured JSON logs. Enable correlation IDs and tenant context. Partially done (structlog already imported in some modules) | S |

**Why first:** G-01 and G-02 fix production correctness issues that would cascade under PIM's higher concurrency. G-06 provides observability for everything that follows.

### Sprint G-B: Infrastructure Upgrades (Week 2–3)

| # | Item | Description | Effort |
|---|------|-------------|--------|
| G-04 | Upgrade Supabase to Large compute | PIM requires higher connection limits, more CPU/RAM for time-series queries and concurrent Celery workers. Dashboard config change | Config |
| G-05 | Add Celery + Redis broker + Flower | Async job queue for: sentiment ingestion, backtest execution, DTF-A calibration, scheduled sentiment refresh. Redis already deployed (reuse as broker) | M |
| G-07 | Add Sentry error tracking | Integrate `sentry-sdk[fastapi]` for backend + `@sentry/nextjs` for frontend. Configure source maps, environment tags, user context. Supersedes N-07 | S |

**Why second:** G-04 provisions the compute needed for Celery workers. G-05 is required by PIM-1 (sentiment ingestion) and PIM-6 (backtesting). G-07 catches errors from all new infrastructure.

### Sprint G-C: Quality & CI (Week 3–4)

| # | Item | Description | Effort |
|---|------|-------------|--------|
| G-03 | Replace `unknown` TypeScript types | `StatementsData` and related interfaces use `unknown`; add proper typed interfaces for all financial data structures. Overlaps CR-Q8 | M |
| G-08 | Add GitHub Actions CI pipeline | Automated: `ruff check`, `pytest`, `vitest`, `tsc --noEmit`, ESLint. Run on PR + push to main. Block merge on failure. Supersedes N-08 | M |

**Why third:** G-03 prevents type-unsafety from propagating into PIM's new TypeScript interfaces. G-08 enforces quality gates before PIM PRs land.

---

## Phase 1: Tech Enhancements (During PIM Development)

These are implemented as needed during the relevant PIM sprint, not all upfront.

### High Priority (implement with first PIM sprint that needs them)

| # | Item | When Needed | PIM Sprint |
|---|------|-------------|------------|
| P-01 | Numba JIT for Monte Carlo + Markov hot loops | PIM-4 (Portfolio Scoring), PIM-5 (Markov Engine) | Sprint 4–5 |
| P-02 | `pg_partman` time-series partitioning | PIM-1 (Sentiment Ingestion) — partition `pim_price_history` and `pim_sentiment_scores` by month | Sprint 1 |
| P-03 | `ProcessPoolExecutor` for MC/Markov parallelism | PIM-5 (Markov Engine), PIM-6 (Backtesting). Overlaps CR-T1 | Sprint 5–6 |

### Medium Priority (implement when relevant feature is built)

| # | Item | When Needed | PIM Sprint |
|---|------|-------------|------------|
| P-04 | QuantEcon library | PIM-5 (Markov Engine) — `MarkovChain` class, steady-state computation, ergodicity checks | Sprint 5 |
| P-05 | D3.js for PIM visualizations | PIM-4+ — Markov state diagrams, sentiment heatmaps, backtest comparison charts | Sprint 4+ |
| P-06 | Materialized views for backtest aggregates | PIM-6 (Backtesting) — pre-computed IC/ICIR/SPC metrics, portfolio returns | Sprint 6 |

### Low Priority (evaluate, implement if needed)

| # | Item | When Needed | Notes |
|---|------|-------------|-------|
| P-07 | Supabase read replica | PIM-6+ if analytical query load justifies it | Evaluate after PIM-6 |
| P-08 | Migrate to new Supabase API key format | Before Supabase deprecates legacy `anon`/`service_role` JWTs | Non-blocking |
| P-09 | Evaluate DuckDB for DTF-A calibration | Developer-only calibration pipeline. Process EDGAR/FRED/Yahoo bulk data | Evaluate during PIM-3 |
| P-10 | Evaluate Polars for backtest data processing | If backtest DataFrames exceed memory at 500+ company universes | Evaluate during PIM-6 |

---

## Phase 2: PIM Module Development

Sequential phases, each building on the previous. Estimated 7 sprints.

| Sprint | Phase | Sub-systems | Key Deliverables | Effort |
|--------|-------|-------------|------------------|--------|
| 1 | PIM-1 | Sentiment Engine | Multi-source sentiment ingestion (news APIs, earnings transcripts, social), NLP scoring via LLM, Celery-scheduled refresh, tenant-scoped storage. **Requires:** G-05 (Celery), P-02 (pg_partman) | XL |
| 2 | PIM-2 | Economic Context | FRED API integration, economic regime classification (expansion/contraction/transition), indicator dashboard, regime-aware model conditioning | L |
| 3 | PIM-3 | Fundamental Aggregation | EDGAR/Yahoo fundamental data ingestion, financial ratio computation, sector/peer grouping, universe CRUD, quality scoring | XL |
| 4 | PIM-4 | Portfolio Scoring | 81-state Markov chain (3×3×3×3: sentiment × fundamental × economic × momentum), state transition matrix estimation, composite scoring. **Requires:** P-01 (Numba), P-05 (D3.js) | XL |
| 5 | PIM-5 | Markov Chain Engine | Numba-accelerated Markov simulation, QuantEcon integration, steady-state distribution, state persistence, matrix calibration. **Requires:** P-03 (ProcessPoolExecutor), P-04 (QuantEcon) | L |
| 6 | PIM-6 | Backtesting Framework | Walk-forward backtesting, IC/ICIR calculation, strategy comparison, materialized view aggregates, backtest studio UI. **Requires:** P-03, P-06 (materialized views) | XL |
| 7 | PIM-7 | PE Benchmarking | PE benchmark database, fund return comparison, J-curve analysis, vintage year analytics, DPI/TVPI/IRR computation | L |

### Infrastructure Dependencies per Sprint

```
Sprint 1 (PIM-1): G-05 (Celery) + P-02 (pg_partman)
Sprint 2 (PIM-2): — (no new infra)
Sprint 3 (PIM-3): P-09 (DuckDB eval, optional)
Sprint 4 (PIM-4): P-01 (Numba) + P-05 (D3.js)
Sprint 5 (PIM-5): P-03 (ProcessPoolExecutor) + P-04 (QuantEcon)
Sprint 6 (PIM-6): P-06 (materialized views) + P-10 (Polars eval, optional)
Sprint 7 (PIM-7): — (no new infra)
```

---

## What NOT to Change

The tech stack review explicitly confirmed these components are appropriate and should not be replaced:

| Component | Current | Verdict |
|-----------|---------|---------|
| Database | Supabase PostgreSQL | STRONG — keep. Add pg_partman for time-series, not TimescaleDB (deprecated on PG17) |
| Backend framework | FastAPI | STRONG — keep as-is |
| Frontend framework | Next.js 14 App Router | STRONG — keep as-is |
| UI library | Tailwind + custom VA design system | STRONG — keep as-is |
| LLM integration | Claude + LLMRouter + AgentService | STRONG — keep as-is |
| Auth | Supabase Auth + ES256 JWKS | ADEQUATE — fix JWKS race (G-01), otherwise keep |
| Caching | Redis | ADEQUATE — fix async (G-02), reuse as Celery broker |
| Charting | Recharts | ADEQUATE — supplement with D3.js (P-05), don't replace |
| Deployment | Vercel + Render | ADEQUATE — keep for now, evaluate paid Render if cold-starts worsen |
| Numerical | NumPy/SciPy | ADEQUATE — add Numba JIT (P-01), don't switch to JAX/PyTorch |

---

## Cross-References

| Build Plan Item | Comprehensive Review Item | Notes |
|-----------------|--------------------------|-------|
| G-01 (JWKS race) | CR-S4 | Sprint 1 security |
| G-02 (sync Redis) | CR-S5 | Sprint 7 item 34 |
| G-03 (unknown types) | CR-Q8 | Sprint 7 item 33 |
| G-07 (Sentry) | Supersedes N-07 | Monitoring & alerting |
| G-08 (CI pipeline) | Supersedes N-08 | CI enhancements |
| P-03 (ProcessPoolExecutor) | CR-T1 | Sprint 4 item 16 |

---

## Success Criteria

1. **Gate complete:** All 8 G-items pass verification (CI green, Sentry capturing, Celery processing test job, structured logs in production)
2. **PIM-1 baseline:** Sentiment scores ingesting on schedule, stored in partitioned tables, queryable per tenant
3. **PIM-4 baseline:** 81-state model producing composite scores for a test universe of 50+ companies
4. **PIM-6 baseline:** Walk-forward backtest completing in <60s for 5-year horizon, 100-company universe
5. **Full PIM:** All 7 phases deployed, DTF calibration pipeline validating model accuracy (IC > 0.05, ICIR > 0.5)
