# PIM v2.0 Build Plan — Portfolio Intelligence Module

> **Version:** 2.0
> **Date:** 2026-03-09
> **Supersedes:** VA_Master_Build_Plan v1.0 (2026-03-07), `2026-03-08-pim-tech-stack-build-plan.md`
> **Source Spec:** `docs/specs/PIM_Requirements_BuildPlan_v2.docx`
> **Status:** Approved for implementation

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Verified Issue Registry](#2-verified-issue-registry)
3. [PIM Pre-Condition Gates](#3-pim-pre-condition-gates)
4. [Functional Requirements](#4-functional-requirements)
5. [Statistical Standards](#5-statistical-standards)
6. [Data Architecture](#6-data-architecture)
7. [Sprint Plan & Master Backlog](#7-sprint-plan--master-backlog)
8. [Developer Testing Framework (DTF)](#8-developer-testing-framework-dtf)
9. [Critical Path & Procurement](#9-critical-path--procurement)
10. [Architecture Decisions](#10-architecture-decisions)

---

## 1. Executive Summary

The Portfolio Intelligence Module (PIM) adds AI-powered portfolio analytics to the Virtual Analyst platform. It integrates with existing modules across 9 touchpoints:

| Existing Module | PIM Integration Point |
|---|---|
| Financial Engine | DCF + ratio outputs feed CIS fundamental quality factor |
| AFS Module | Audited statement data for fundamental aggregation |
| Benchmark Module | Industry percentiles flow into sector positioning sub-score |
| LLM Router | 6 new task labels with calibrated temperatures |
| Monte Carlo Engine | Parallelised MC feeds portfolio risk metrics |
| Ventures Module | Venture-stage companies included in PE benchmarking |
| Board Pack Module | PIM dashboards exportable as board pack sections |
| Draft & Changesets | Portfolio run snapshots stored as versioned drafts |
| Billing Module | `pim_enabled` tenant gate, usage metering for LLM calls |

**Scope:** 71 backlog items across 7 sprints (Sprint 0-6), 23 remediation items (REM-01 through REM-23), 9 new PIM database tables, 4 DTF tables, 6 new LLM task labels, and a Developer Testing Framework for model calibration.

**Effort estimate:** ~22 sprint-weeks (Sprint 0: 2w, Sprints 1-3: 3w each, Sprint 4: 4w, Sprint 5: 3w, Sprint 6: 4w).

---

## 2. Verified Issue Registry

29 issues consolidated from the comprehensive platform review. Each issue was **verified against the actual codebase** by 5 parallel analysis agents. Corrections to the original spec are noted.

### 2.1 Security Issues

| ID | Title | Severity | Status | Verified | Evidence |
|---|---|---|---|---|---|
| CR-S1 | Unauthenticated debug endpoint leaks PII | CRITICAL | **FIXED** | N/A | Removed in Sprint 1 security review |
| CR-S2 | Anomaly detection entirely LLM-based, zero statistics | CRITICAL | Open — **GATE-1** | **CONFIRMED** | `analytics_ai.py:98-126` — `detect_anomalies()` builds text prompt, no Z-score/IQR |
| CR-S3 | Auth middleware investor fallback on DB error | HIGH | **FIXED** | N/A | Fixed in Sprint 1 security review |
| CR-S4 | JWKS async race condition | HIGH | Open — **GATE-2** | **CONFIRMED** | `auth.py:24-47` — sync `httpx.get()` at L37, no `asyncio.Lock()` on globals |
| CR-S5 | Sync Redis blocks event loop | HIGH | Open — **GATE-3** | **CONFIRMED** | `runs.py:55-74`, `jobs.py:24-50` — `redis.Redis` sync calls from async handlers |

### 2.2 Financial Accuracy Issues

| ID | Title | Severity | Status | Verified | Evidence |
|---|---|---|---|---|---|
| CR-F1 | DCF lacks mid-year convention | HIGH | Open — **GATE-4** | **CONFIRMED** | `valuation.py:54` — `(t+1)/12.0` instead of `(t+0.5)/12.0` |
| CR-F2 | DCF missing equity bridge | HIGH | Open — **GATE-5** | **CONFIRMED** | `valuation.py:11-23` — `DCFResult` has no `equity_value`/`net_debt`/`cash` fields |
| CR-F3 | Terminal value uses FCF instead of EBITDA exit multiple | HIGH | Open — **GATE-6** | **CONFIRMED** | `valuation.py:64-65` — `fcf_annual * terminal_multiple`, no `ebitda_series` param |
| CR-F4 | No tax loss carry-forward / NOL | HIGH | Open | **CONFIRMED** | `statements.py:181-183` — `tax = max(0.0, ebt * tax_rate)`, zero NOL logic |
| CR-F5 | Single FX rate for consolidation horizon | HIGH | Open | **PARTIALLY** | `consolidation.py:114-164` — avg/closing split correct (IAS 21) but scalar-only rates |
| CR-F6 | Forecast revenue growth lacks mean-reversion | MEDIUM | Open | Structural | No bounded growth model; linear extrapolation only |

### 2.3 Code Quality Issues

| ID | Title | Severity | Status | Verified | Evidence |
|---|---|---|---|---|---|
| CR-Q1 | `build_three_statement_model` is 500+ lines | HIGH | Open | **PARTIALLY** | `statements.py:90-447` — 357-line body, 3 helpers exist but body poorly decomposed |
| CR-Q2 | `budgets.py` exceeds 1,400 lines | HIGH | Open | **CONFIRMED** (understated) | Actually **1,618 lines** |
| CR-Q3 | `afs.py` exceeds 2,500 lines | HIGH | Open | **CONFIRMED** (understated) | Actually **2,657 lines** |
| CR-Q4 | RunStatus enum mismatch frontend/backend | HIGH | Open | **CONFIRMED** | `compare/page.tsx:78,126` — queries `"completed"` but backend uses `"succeeded"` |
| CR-Q5 | N+1 query pattern in budget listing | MEDIUM | Open | **CONFIRMED** | `budgets.py:394-493` — 4 queries per budget in Python loop (1+4N round-trips) |
| CR-Q6 | f-string SQL in 3 routers | MEDIUM | Open | **PARTIALLY** | `budgets.py:178`, `afs.py:441,452` — f-strings exist but values parameterised; low risk |
| CR-Q7 | Bare `except:` in 6 files | MEDIUM | Open | **CONFIRMED** (understated) | Actually **8 files**: `deps.py:99`, `xero.py:89`, `excel_parser.py:142,171`, `reforecast_agent.py:64`, `integrations.py:38,42`, `metrics.py:22`, `org_structures.py:894` |
| CR-Q8 | `StatementsData` uses `unknown` TS types | MEDIUM | Open | **CONFIRMED** | `api.ts:156-162` — `Record<string, unknown>[] \| unknown` union with bare `unknown` |
| CR-Q9 | Sensitivity `parameter_path` traversal risk | LOW | Open | **NOT CONFIRMED** | `sensitivity.py:43-52` — `_validate_path()` denylist guard exists |

### 2.4 Performance Issues

| ID | Title | Severity | Status | Verified | Evidence |
|---|---|---|---|---|---|
| CR-T1 | Monte Carlo per-sim loop, no parallelism | HIGH | Open — **GATE-7** | **CONFIRMED** | `monte_carlo.py:68` — `for sim_i in range(num_simulations)`, no ProcessPoolExecutor |
| CR-T2 | AFS disclosure drafter not streamed | LOW | Open | Structural | Full response buffered before return |

### 2.5 Nice-to-Have Issues

| ID | Title | Severity | Status | Verified | Evidence |
|---|---|---|---|---|---|
| CR-N1 | Zero page-level frontend tests | LOW | Open | **FALSE** — 57 page test files exist | `apps/web/tests/pages/` has 57 test files; REM-20 scope adjusted |
| CR-N2 | Email distribution is stub | LOW | Open | **PARTIALLY** | Real SendGrid impl exists; dev-mode fallback is the "stub" |
| CR-N3 | Board pack update is Phase 10 stub | LOW | Open | **CONFIRMED** | `board_packs.py:368` — returns hardcoded response |
| CR-N4 | Rounding drift in DCF PV accumulation | LOW | Open | **CONFIRMED** | `valuation.py:55-56` — unrounded `pv` accumulates, rounded in breakdown |
| CR-N5 | LLM retry policy not configurable at runtime | LOW | Open | **CONFIRMED** | `router.py:17-54` — `DEFAULT_POLICY` module constant, `set_policy()` never called |
| CR-N6 | No Sentry frontend integration | LOW | Open | **CONFIRMED** | Backend Sentry configured, frontend not |
| CR-N7 | No structured JSON logging on frontend | LOW | Open | Structural | `logger.ts` exists but uses console methods |
| CR-N8 | CI does not gate Playwright E2E | LOW | Open | Structural | CI runs unit tests only |
| CR-N9 | Health check has no DB timeout | LOW | Open | **CONFIRMED** | `health.py:35` — `await pool.acquire()` with no timeout |

### 2.2a Infrastructure Status (verified)

| Component | Status | Notes |
|---|---|---|
| Celery + Redis broker | **FULLY IMPLEMENTED** | `apps/worker/celery_app.py` + `apps/worker/tasks.py` |
| GitHub Actions CI | **EXISTS** | `.github/workflows/ci.yml` — ruff, black, mypy, Safety, pytest, vitest, tsc, Docker |
| Sentry backend | **CONFIGURED** | `apps/api/app/main.py:56-65` — DSN optional |
| Structlog | **WIDESPREAD** | `shared/fm_shared/logging.py` + 30 files |
| DTF agent spec | **EXISTS** | `.claude/agents/dtf-engineer.md` — no production code yet |

---

## 3. PIM Pre-Condition Gates

7 issues must be closed before PIM feature development begins. These form Sprint 0.

| Gate | CR Ref | Justification | Sprint |
|---|---|---|---|
| GATE-1 | CR-S2 | PIM anomaly detection must have statistical foundation; LLM-only violates ISA 520 | Sprint 0 |
| GATE-2 | CR-S4 | Concurrent JWKS fetches will deadlock under PIM's higher request volume | Sprint 0 |
| GATE-3 | CR-S5 | Sync Redis in async handlers will block event loop during PIM sentiment refresh | Sprint 0 |
| GATE-4 | CR-F1 | CIS fundamental quality factor consumes DCF output; wrong discount timing propagates | Sprint 0 |
| GATE-5 | CR-F2 | Equity value is a required input for PE benchmarking (DPI/TVPI calculations) | Sprint 0 |
| GATE-6 | CR-F3 | Terminal value error distorts all downstream valuation-based scores | Sprint 0 |
| GATE-7 | CR-T1 | PIM backtesting requires 10,000+ MC simulations; single-threaded loop is untenable | Sprint 0 |

**Note on v1.0 gates dropped:** The v1.0 build plan listed 8 gates (G-01 through G-08). Four have been resolved:
- G-05 (Celery) — fully implemented
- G-06 (Structlog) — widespread across 30+ files
- G-07 (Sentry backend) — configured
- G-08 (CI pipeline) — exists in GitHub Actions

v2.0 replaces these with financial accuracy gates (CR-F1, F2, F3) that block PIM correctness.

---

## 4. Functional Requirements

### FR-1: Sentiment Ingestion Engine

| Req ID | Requirement | Priority |
|---|---|---|
| FR-1.1 | Ingest from ≥ 2 text sources (news API + earnings transcripts) | Must |
| FR-1.2 | Produce per-company sentiment score in [-1, +1] with confidence ∈ [0, 1] | Must |
| FR-1.3 | Aggregate to weekly and monthly time-series per company | Must |
| FR-1.4 | Celery-scheduled refresh (configurable interval, default 6 hours) | Must |
| FR-1.5 | Tenant-scoped storage; no cross-tenant data leakage | Must |
| FR-1.6 | LLM extraction uses `pim_sentiment_extraction` label (temp = 0.1) | Should |
| FR-1.7 | Dashboard shows latest scores, trend sparklines, source breakdown | Should |

### FR-2: Economic Context Module

| Req ID | Requirement | Priority |
|---|---|---|
| FR-2.1 | Pull ≥ 5 FRED indicators (GDP, CPI, unemployment, yield curve, ISM PMI) | Must |
| FR-2.2 | Classify economic regime: expansion / contraction / transition | Must |
| FR-2.3 | Regime classification updates monthly with 1-month publication lag | Must |
| FR-2.4 | Store snapshots as `pim_economic_snapshots` with version history | Must |
| FR-2.5 | Dashboard card showing current regime, indicator trends, regime timeline | Should |

### FR-3: Composite Investment Score (CIS)

| Req ID | Requirement | Priority |
|---|---|---|
| FR-3.1 | CIS = weighted sum of 5 sub-scores (configurable weights, default below) | Must |
| FR-3.2 | Default weights: Fundamental Quality 35%, Fundamental Momentum 20%, Idiosyncratic Sentiment 25%, Sentiment Momentum 10%, Sector Positioning 10% | Must |
| FR-3.3 | Each sub-score normalised to [0, 100] before weighting | Must |
| FR-3.4 | CIS recomputed on-demand per portfolio run or on schedule | Must |
| FR-3.5 | Factor attribution breakdown per company (which factors contributed most) | Should |
| FR-3.6 | LLM factor attribution narrative uses `pim_factor_attribution` label (temp = 0.2) | Should |

### FR-4: Markov Chain Engine

| Req ID | Requirement | Priority |
|---|---|---|
| FR-4.1 | 81-state space: 3 levels × 4 dimensions (fundamental quality, momentum, sentiment, economic context) | Must |
| FR-4.2 | Transition matrix estimated from historical data (≥ 5 years) | Must |
| FR-4.3 | Laplace smoothing (α = 1) for zero-count transitions (SR-4) | Must |
| FR-4.4 | Steady-state distribution via QuantEcon `MarkovChain` class | Must |
| FR-4.5 | State persistence: store current state per company per portfolio run | Must |
| FR-4.6 | Numba JIT acceleration on inner transition loops | Should |
| FR-4.7 | D3.js state diagram visualisation on frontend | Should |

### FR-5: Portfolio Construction

| Req ID | Requirement | Priority |
|---|---|---|
| FR-5.1 | Greedy top-N selection ranked by CIS (not mean-variance optimisation) | Must |
| FR-5.2 | Configurable constraints: max position size, sector caps, min liquidity | Must |
| FR-5.3 | Portfolio run stored as snapshot with holdings, weights, CIS scores | Must |
| FR-5.4 | Rebalance trigger: manual or scheduled (weekly/monthly) | Must |
| FR-5.5 | LLM portfolio narrative uses `pim_portfolio_narrative` label (temp = 0.3) | Should |

### FR-6: Backtesting Framework

| Req ID | Requirement | Priority |
|---|---|---|
| FR-6.1 | Walk-forward backtest with configurable lookback and rebalance frequency | Must |
| FR-6.2 | Information Coefficient (IC) and IC Information Ratio (ICIR) computation | Must |
| FR-6.3 | Strategy comparison: PIM vs benchmark, PIM vs equal-weight | Must |
| FR-6.4 | No look-ahead bias: all signals use data available at decision time (SR-2) | Must |
| FR-6.5 | Transaction cost reporting: estimated and actual (SR-7) | Should |
| FR-6.6 | Materialised view aggregates for IC/ICIR/SPC metrics (P-06) | Should |
| FR-6.7 | Backtest studio UI with comparison charts | Should |

### FR-7: PE Benchmarking

| Req ID | Requirement | Priority |
|---|---|---|
| FR-7.1 | PE assessment CRUD: fund name, vintage year, commitment, drawdowns, distributions | Must |
| FR-7.2 | Compute DPI, TVPI, IRR per fund and per vintage year | Must |
| FR-7.3 | J-curve analysis with graphical representation | Must |
| FR-7.4 | Peer comparison against benchmark percentiles | Must |
| FR-7.5 | LLM PE memo generation uses `pim_pe_memo` label (temp = 0.4) | Should |
| FR-7.6 | Venture-stage overlay from existing Ventures module data | Should |

---

## 5. Statistical Standards

All PIM quantitative outputs must comply with these 7 standards.

| ID | Standard | Rationale |
|---|---|---|
| SR-1 | All analytical procedures must satisfy ISA 520 (expectation, threshold, investigation) | Audit-grade analytics require formal statistical basis |
| SR-2 | No look-ahead bias: signals use only data available at decision time | Prevents overfitting; ensures backtest integrity |
| SR-3 | Uncertainty bounds (confidence intervals or prediction intervals) mandatory on all point estimates | Users must understand precision of outputs |
| SR-4 | Markov transition matrix uses Laplace smoothing (α = 1) for zero-count cells | Prevents division-by-zero and ensures ergodicity |
| SR-5 | Statistical Process Control (SPC) significance: flag anomalies only when > 2σ from control limits | Reduces false positives in anomaly detection |
| SR-6 | All PIM reports must include limitations disclosure | Transparency requirement |
| SR-7 | Backtest results must report transaction cost assumptions (estimated and actual where available) | Prevents overstated returns |

**Required limitations disclosure (verbatim):**

> *"PIM outputs are model-based estimates derived from historical data and AI-generated signals. They do not constitute investment advice. Past performance does not predict future results. Sentiment scores reflect NLP model confidence and may not capture all market-relevant information. Markov state transitions assume stationarity over the estimation window. Users should apply independent judgment before making investment decisions."*

---

## 6. Data Architecture

### 6.1 PIM Database Tables (9 new)

| Table | Purpose | Partitioning |
|---|---|---|
| `pim_universes` | Company universe definitions per tenant | None |
| `pim_sentiment_signals` | Raw per-source sentiment signals | By month (`pg_partman`) |
| `pim_sentiment_aggregates` | Weekly/monthly aggregated sentiment per company | By month |
| `pim_economic_snapshots` | FRED indicator snapshots with regime classification | None |
| `pim_portfolio_runs` | Portfolio run metadata (snapshot, config, status) | None |
| `pim_portfolio_holdings` | Holdings per portfolio run (company, weight, CIS) | None |
| `pim_backtest_results` | Backtest output (returns, IC, ICIR, strategy comparison) | None |
| `pim_markov_states` | Current Markov state per company per portfolio run | None |
| `pim_pe_assessments` | PE fund assessments (DPI, TVPI, IRR, J-curve) | None |

### 6.2 DTF Tables (4 new — developer-only)

| Table | Purpose |
|---|---|
| `dtf_calibration_runs` | DTF-A calibration run metadata |
| `dtf_historical_parameters` | Historical parameter snapshots from calibration |
| `dtf_validation_runs` | DTF-B ongoing validation run metadata |
| `dtf_prediction_outcomes` | Prediction vs actual outcomes for IC monitoring |

### 6.3 LLM Task Labels (6 new)

| Label | Temperature | Purpose |
|---|---|---|
| `pim_sentiment_extraction` | 0.1 | Extract sentiment from news/transcript text |
| `pim_sentiment_summary` | 0.3 | Summarise sentiment trends for dashboard |
| `pim_factor_attribution` | 0.2 | Explain CIS factor contributions per company |
| `pim_pe_memo` | 0.4 | Generate PE fund assessment memo |
| `pim_portfolio_narrative` | 0.3 | Portfolio construction rationale narrative |
| `pim_backtest_commentary` | 0.2 | Interpret backtest results and IC trends |

### 6.4 Billing Gate

```
pim_enabled: boolean (per tenant, in billing_plans table)
check_pim_access(tenant_id) → middleware, HTTP 403 when disabled
Usage metering: LLM calls billed via existing billing_service quota
```

### 6.5 Sentiment Data Source Tiers

| Tier | Source | Priority |
|---|---|---|
| Tier 1 (launch) | Polygon.io news API + SEC EDGAR filings (free) | Must |
| Tier 2 (post-launch) | AlphaSense earnings transcripts | Should |
| Tier 3 (future) | Social media sentiment (Twitter/Reddit APIs) | Could |

---

## 7. Sprint Plan & Master Backlog

### Effort Scale

| Tag | Days |
|---|---|
| XS | < 0.5 |
| S | 0.5 – 1 |
| M | 2 – 3 |
| L | 4 – 6 |
| XL | 7 – 10 |

---

### Sprint 0 — Pre-PIM Remediation Gates (2 weeks)

Close the 7 PIM pre-condition gates.

| # | ID | Title | CR Ref | Effort | Files |
|---|---|---|---|---|---|
| 1 | REM-01 | Replace LLM anomaly detection with statistical + LLM hybrid | CR-S2 | L | `analytics_ai.py`, new `anomaly_stats.py` |
| 2 | REM-02 | Fix JWKS async race condition (cache + TTL + asyncio.Lock) | CR-S4 | S | `auth.py` |
| 3 | REM-03 | Migrate sync Redis to `redis.asyncio` | CR-S5 | M | `runs.py`, `jobs.py`, `deps.py` |
| 4 | REM-04 | Add mid-year convention to DCF | CR-F1 | S | `valuation.py` |
| 5 | REM-05 | Add equity bridge (net debt, cash, equity value) | CR-F2 | M | `valuation.py`, `schemas.py` |
| 6 | REM-06 | Fix terminal value to use EBITDA exit multiple | CR-F3 | S | `valuation.py` |
| 7 | REM-07 | Add ProcessPoolExecutor to Monte Carlo | CR-T1 | M | `monte_carlo.py` |

**Sprint 0 acceptance:** All 7 gate items pass unit tests; existing test suite remains green.

---

### Sprint 1 — Sentiment Ingestion + Continued Remediation (3 weeks)

| # | ID | Title | CR Ref | Effort | Notes |
|---|---|---|---|---|---|
| 8 | REM-08 | Add NOL / tax loss carry-forward | CR-F4 | M | `statements.py` |
| 9 | REM-09 | Per-period FX rate table for consolidation | CR-F5 | M | `consolidation.py` |
| 10 | REM-10 | Split `budgets.py` into sub-routers | CR-Q2 | L | Target: ≤ 400 lines per file |
| 11 | REM-11 | Fix RunStatus enum (`"completed"` → `"succeeded"`) | CR-Q4 | XS | `compare/page.tsx`, `setup.tsx` |
| 12 | PIM-1.1 | Create `pim_universes` table + CRUD endpoints | — | M | Migration + router |
| 13 | PIM-1.2 | Create `pim_sentiment_signals` table (partitioned) | — | M | Migration + `pg_partman` |
| 14 | PIM-1.3 | Create `pim_sentiment_aggregates` table (partitioned) | — | S | Migration |
| 15 | PIM-1.4 | Polygon.io news API integration service | — | L | New service in `services/pim/` |
| 16 | PIM-1.5 | LLM sentiment extraction (label: `pim_sentiment_extraction`) | — | M | LLM Router config |
| 17 | PIM-1.6 | Celery task: scheduled sentiment refresh | — | M | `apps/worker/tasks.py` |
| 18 | PIM-1.7 | Sentiment dashboard page (scores, trends, source breakdown) | — | L | `apps/web/app/(app)/pim/sentiment/` |

**Sprint 1 acceptance:** Universe CRUD works; sentiment signals ingested from Polygon.io; Celery refresh runs on schedule; dashboard shows scores.

---

### Sprint 2 — Economic Context + CIS Foundation (3 weeks)

| # | ID | Title | CR Ref | Effort | Notes |
|---|---|---|---|---|---|
| 19 | REM-12 | Fix bare `except` clauses (8 files) | CR-Q7 | S | Replace with specific exceptions |
| 20 | REM-13 | Replace `unknown` TS types in `StatementsData` | CR-Q8 | M | `api.ts` |
| 21 | REM-14 | Fix N+1 query in budget listing | CR-Q5 | M | `budgets.py` — batch SQL |
| 22 | REM-15 | Decompose `build_three_statement_model` | CR-Q1 | L | `statements.py` — extract sub-functions |
| 23 | PIM-2.1 | Create `pim_economic_snapshots` table | — | S | Migration |
| 24 | PIM-2.2 | FRED API integration service (5 indicators) | — | M | New service |
| 25 | PIM-2.3 | Economic regime classifier (expansion/contraction/transition) | — | M | Statistical classifier |
| 26 | PIM-2.4 | Monthly Celery task for FRED refresh | — | S | `apps/worker/tasks.py` |
| 27 | PIM-2.5 | Economic context dashboard page | — | M | `apps/web/app/(app)/pim/economic/` |
| 28 | PIM-2.6 | CIS computation service (5-factor weighted sum) | — | L | `services/pim/cis.py` |
| 29 | PIM-2.7 | CIS normalisation ([0,100] per sub-score) | — | S | Part of CIS service |
| 30 | PIM-2.8 | Factor attribution endpoint + LLM narrative | — | M | `pim_factor_attribution` label |

**Sprint 2 acceptance:** FRED data ingested; regime classification works; CIS computation returns scores; factor attribution narrative generated.

---

### Sprint 3 — Markov Chain Engine + Universe Manager (3 weeks)

| # | ID | Title | CR Ref | Effort | Notes |
|---|---|---|---|---|---|
| 31 | REM-16 | Split `afs.py` into sub-routers | CR-Q3 | L | Target: ≤ 500 lines per file |
| 32 | REM-17 | Add rounding consistency to DCF PV | CR-N4 | XS | `valuation.py` |
| 33 | REM-18 | ~~Add sensitivity parameter allowlist~~ Verify denylist coverage | CR-Q9 | XS | Denylist exists; verify completeness only |
| 34 | PIM-3.1 | Markov 81-state model definition (3^4 state space) | — | L | `services/pim/markov.py` |
| 35 | PIM-3.2 | Transition matrix estimation from historical data | — | L | Statistical estimation + Laplace smoothing |
| 36 | PIM-3.3 | QuantEcon integration (steady-state, ergodicity) | — | M | `QuantEcon.MarkovChain` wrapper |
| 37 | PIM-3.4 | Create `pim_markov_states` table | — | S | Migration |
| 38 | PIM-3.5 | Numba JIT on transition hot loops | — | M | `@njit` decorator |
| 39 | PIM-3.6 | EDGAR/Yahoo fundamental data ingestion | — | L | `services/pim/fundamentals.py` |
| 40 | PIM-3.7 | Universe manager UI (CRUD, sector grouping, quality scoring) | — | L | `apps/web/app/(app)/pim/universe/` |

**Sprint 3 acceptance:** Markov engine computes state transitions; Numba-accelerated; fundamental data ingested; universe manager functional.

---

### Sprint 4 — Portfolio Construction + Backtesting (4 weeks)

| # | ID | Title | CR Ref | Effort | Notes |
|---|---|---|---|---|---|
| 41 | PIM-4.1 | Create `pim_portfolio_runs` + `pim_portfolio_holdings` tables | — | M | Migration |
| 42 | PIM-4.2 | Greedy portfolio constructor (top-N by CIS) | — | L | `services/pim/portfolio.py` |
| 43 | PIM-4.3 | Position constraints engine (max size, sector caps, min liquidity) | — | M | Constraint checker |
| 44 | PIM-4.4 | Portfolio run snapshot + versioning via Draft system | — | M | Integration with existing drafts |
| 45 | PIM-4.5 | LLM portfolio narrative | — | S | `pim_portfolio_narrative` label |
| 46 | PIM-4.6 | Create `pim_backtest_results` table | — | S | Migration |
| 47 | PIM-4.7 | Walk-forward backtester (configurable lookback, rebalance freq) | — | XL | `services/pim/backtester.py` |
| 48 | PIM-4.8 | IC/ICIR computation + strategy comparison | — | L | Statistical computation |
| 49 | REM-19 | Make LLM retry policy runtime-configurable | CR-N5 | S | `router.py` |

**Sprint 4 acceptance:** Portfolio construction works end-to-end; backtesting produces IC/ICIR results; no look-ahead bias verified.

---

### Sprint 5 — Backtest Studio UI + PE Benchmarking Start (3 weeks)

| # | ID | Title | CR Ref | Effort | Notes |
|---|---|---|---|---|---|
| 50 | PIM-5.1 | Backtest studio UI (comparison charts, strategy overlay) | — | L | `apps/web/app/(app)/pim/backtest/` |
| 51 | PIM-5.2 | LLM backtest commentary | — | S | `pim_backtest_commentary` label |
| 52 | PIM-5.3 | Materialised views for backtest aggregates | — | M | `pg_partman` + refresh |
| 53 | PIM-5.4 | D3.js Markov state diagram | — | L | Interactive state transition visualisation |
| 54 | PIM-5.5 | Transaction cost reporting (SR-7) | — | M | Estimated + actual costs |
| 55 | PIM-6.1 | Create `pim_pe_assessments` table | — | S | Migration |
| 56 | PIM-6.2 | PE assessment CRUD endpoints | — | M | Router endpoints |
| 57 | PIM-6.3 | DPI/TVPI/IRR computation engine | — | L | `services/pim/pe_benchmarks.py` |
| 58 | PIM-6.4 | J-curve analysis + graphical representation | — | M | Computation + chart |

**Sprint 5 acceptance:** Backtest studio renders comparison charts; Markov diagram interactive; PE assessments CRUD works; DPI/TVPI/IRR computed.

---

### Sprint 6 — PE Completion + Platform Hardening (4 weeks)

| # | ID | Title | CR Ref | Effort | Notes |
|---|---|---|---|---|---|
| 59 | PIM-7.1 | Peer comparison against benchmark percentiles | — | M | Percentile ranking engine |
| 60 | PIM-7.2 | LLM PE memo generation | — | M | `pim_pe_memo` label |
| 61 | PIM-7.3 | Venture-stage overlay from Ventures module | — | M | Cross-module integration |
| 62 | PIM-7.4 | PE benchmarking dashboard UI | — | L | `apps/web/app/(app)/pim/pe/` |
| 63 | PIM-7.5 | PIM billing gate (`pim_enabled` + middleware) | — | M | Billing integration |
| 64 | PIM-7.6 | Limitations disclosure on all PIM reports (SR-6) | — | S | Template footer |
| 65 | PIM-7.7 | Uncertainty bounds on all point estimates (SR-3) | — | M | Confidence intervals |
| 66 | PIM-7.8 | SPC significance thresholds for anomaly flags (SR-5) | — | M | Statistical thresholds |
| 67 | PIM-7.9 | Board pack PIM section export | — | M | Integration with board pack builder |
| 68 | REM-20 | Expand frontend page test coverage | CR-N1 | M | Adjusted: 57 tests exist; expand to cover PIM pages |
| 69 | REM-21 | Add Sentry frontend integration | CR-N6 | S | `@sentry/nextjs` |
| 70 | REM-22 | Add health check DB timeout | CR-N9 | XS | `health.py` — add `timeout=5.0` |
| 71 | REM-23 | Gate Playwright E2E in CI | CR-N8 | M | `.github/workflows/ci.yml` |

**Sprint 6 acceptance:** PE benchmarking complete; billing gate enforced; statistical standards (SR-1 through SR-7) all satisfied; PIM pages have tests; Sentry frontend live.

---

## 8. Developer Testing Framework (DTF)

### 8.1 Overview

The DTF is developer-only tooling (never exposed on public API) for model calibration and ongoing prediction validation. Two sub-systems:

| System | Purpose | Trigger | Frequency |
|---|---|---|---|
| **DTF-A** (Calibration) | Historical parameter estimation using EDGAR/FRED/Yahoo bulk data | Manual (`dtf.py calibrate`) | Ad-hoc |
| **DTF-B** (Validation) | Ongoing prediction accuracy monitoring (IC, ICIR, SPC charts) | Automated Celery beat | Weekly |

### 8.2 DTF-A Calibration Pipeline (7 steps)

1. **Data Load** — Bulk download from EDGAR, FRED, Yahoo Finance (configurable date range)
2. **Feature Engineering** — Compute ratios, sentiment scores, momentum indicators from raw data
3. **State Discretisation** — Map continuous features to 3-level Markov states (low/medium/high)
4. **Transition Counting** — Count state-to-state transitions across 81-state space
5. **Laplace Smoothing** — Add α = 1 pseudocounts to all cells (SR-4)
6. **Matrix Normalisation** — Row-normalise to produce valid transition probability matrix
7. **Validation** — Ergodicity check via QuantEcon; steady-state distribution; out-of-sample IC test

**DTF-A runs on a separate Celery queue (`dtf_calibration`) with lower priority than production tasks.**

### 8.3 DTF-B Ongoing Validation

- **IC/ICIR monitoring:** Weekly computation of information coefficient; alert if ICIR < 0.5 for 4 consecutive weeks
- **SPC charts:** Control charts for CIS prediction accuracy; flag when > 2σ from control limits (SR-5)
- **Alert dispatch:** Structlog warnings + optional Sentry alert on degradation
- **No automatic model update:** DTF-B only monitors; recalibration requires manual DTF-A trigger

### 8.4 DTF Database Tables

| Table | Key Columns |
|---|---|
| `dtf_calibration_runs` | `run_id`, `started_at`, `completed_at`, `data_range`, `status`, `parameters_json` |
| `dtf_historical_parameters` | `param_id`, `calibration_run_id`, `parameter_name`, `value`, `confidence_interval` |
| `dtf_validation_runs` | `run_id`, `week_ending`, `ic_value`, `icir_value`, `spc_status` |
| `dtf_prediction_outcomes` | `prediction_id`, `company_id`, `predicted_state`, `actual_state`, `prediction_date` |

### 8.5 Iterative Markov Calibration

The Markov transition matrix is calibrated via DTF-A using historical state transitions. The calibration is **iterative** — multiple DTF-A runs may be needed to converge on stable parameters:

1. Initial calibration with 5-year lookback
2. Out-of-sample IC test on holdout year
3. If IC < 0.3, adjust discretisation thresholds and re-run
4. Final matrix accepted when IC ≥ 0.3 and ergodicity confirmed

---

## 9. Critical Path & Procurement

### 9.1 Critical Path

```
Sprint 0 (Gates) → Sprint 1 (Sentiment) → Sprint 2 (Economic + CIS)
    → Sprint 3 (Markov + Fundamentals) → Sprint 4 (Portfolio + Backtest)
    → Sprint 5 (Backtest UI + PE Start) → Sprint 6 (PE Complete + Hardening)

Parallel track: DTF-A calibration begins during Sprint 3 (once Markov engine exists)
```

**Sequential dependency:** Each sprint depends on the prior sprint's outputs. No sprint can be skipped or parallelised with its predecessor.

**DTF-A is the exception:** It runs in parallel starting Sprint 3, using the Markov engine but not blocking feature development.

### 9.2 Procurement Decisions

| Item | Cost | Required By | Decision |
|---|---|---|---|
| Polygon.io Starter | $29/month | Before Sprint 1 | News API for sentiment extraction |
| AlphaSense | Quote required | Before Sprint 4 | Earnings transcripts (Tier 2 source) |
| MSCI Barra / Bloomberg | Quote required | Before Sprint 5 | Transaction cost data for SR-7 |
| Claude Sonnet (LLM) | Usage-based | Before Sprint 1 | PE memo, sentiment, narratives (6 labels) |

### 9.3 Infrastructure Upgrades

| Item | Cost | Required By | Notes |
|---|---|---|---|
| Supabase Large compute | ~$100/month upgrade | Before Sprint 1 | Higher connection limits for Celery workers + time-series queries |
| Sentry Pro (frontend) | ~$26/month | Sprint 6 | REM-21 frontend error tracking |

---

## 10. Architecture Decisions

### AD-1: Greedy Portfolio Construction (not MVO)

**Decision:** Use greedy top-N selection by CIS rank, not mean-variance optimisation.
**Rationale:** MVO requires a covariance matrix that is notoriously unstable for < 100 assets. Greedy selection is transparent, explainable, and avoids false precision.

### AD-2: Weekly/Monthly Sentiment Aggregation

**Decision:** Aggregate sentiment to weekly and monthly granularity, not daily.
**Rationale:** Daily sentiment is noisy and increases storage costs. Weekly/monthly aligns with typical portfolio rebalance frequencies.

### AD-3: 3-Level Markov Discretisation (81 States)

**Decision:** Use 3 levels (low/medium/high) per dimension, yielding 3^4 = 81 states.
**Rationale:** 5 levels would yield 5^4 = 625 states, requiring 390,625 transition probabilities — far too many to estimate reliably from available data. 3 levels balances expressiveness with estimability.

### AD-4: Manual DTF-A Calibration Only

**Decision:** DTF-A calibration is triggered manually by developers, never automatically.
**Rationale:** Automatic recalibration risks introducing parameter instability without human review. DTF-B monitors for degradation; humans decide when to recalibrate.

### AD-5: Rollback Plan

If PIM development is paused or abandoned:
1. PIM tables are isolated (no foreign keys to core tables)
2. PIM router can be disabled via feature flag without affecting other modules
3. Remediation items (REM-01 through REM-23) benefit the platform regardless of PIM status
4. Celery workers can be scaled down if PIM tasks are removed

---

## Appendix A: Cross-Reference to v1.0 Build Plan

| v1.0 Item | v2.0 Mapping | Notes |
|---|---|---|
| G-01 (JWKS fix) | REM-02 (GATE-2) | Retained |
| G-02 (async Redis) | REM-03 (GATE-3) | Retained |
| G-03 (TS types) | REM-13 | Retained, moved to Sprint 2 |
| G-04 (Supabase Large) | Infrastructure upgrade | Retained |
| G-05 (Celery) | **DROPPED** — already implemented | `apps/worker/celery_app.py` exists |
| G-06 (Structlog) | **DROPPED** — widespread | 30+ files already use structlog |
| G-07 (Sentry backend) | **DROPPED** — configured | `main.py:56-65` |
| G-08 (CI pipeline) | **DROPPED** — exists | `.github/workflows/ci.yml` |
| PIM-1 through PIM-7 | Expanded into 71 numbered items | Significantly more granular in v2.0 |
| P-01 (Numba) | PIM-3.5 | Moved into Sprint 3 |
| P-02 (pg_partman) | PIM-1.2, PIM-1.3 | Moved into Sprint 1 |
| P-03 (ProcessPool) | REM-07 (GATE-7) | Elevated to gate |
| P-04 (QuantEcon) | PIM-3.3 | Moved into Sprint 3 |
| P-05 (D3.js) | PIM-5.4 | Moved into Sprint 5 |
| P-06 (Materialised views) | PIM-5.3 | Moved into Sprint 5 |

## Appendix B: Spec Corrections from Codebase Verification

| Spec Claim | Verified Finding | Impact |
|---|---|---|
| CR-N1: "Zero page tests" | **FALSE** — 57 page test files exist | REM-20 scope reduced to "expand coverage for PIM pages" |
| CR-Q9: "No parameter allowlist" | **NOT CONFIRMED** — `_validate_path()` denylist exists | REM-18 reduced to "verify denylist completeness" |
| CR-Q7: "6 files with bare except" | **UNDERSTATED** — actually 8 files | No impact on effort estimate |
| CR-Q2: "1,400+ lines" | **UNDERSTATED** — actually 1,618 lines | No impact on approach (split into sub-routers) |
| CR-Q3: "2,500+ lines" | **UNDERSTATED** — actually 2,657 lines | No impact on approach (split into sub-routers) |
| Infrastructure: Celery, CI, Structlog, Sentry | All verified as implemented/configured | 4 v1.0 gates dropped from v2.0 |
