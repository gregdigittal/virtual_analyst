# Virtual Analyst Platform — Comprehensive Code & Financial Review

**Date:** 2026-03-04
**Scope:** Full platform review across code quality, financial metrics, and statistical analysis
**Perspectives:** Senior Data Scientist · Financial Analyst (CFA) · Code Reviewer
**Verdict:** REQUEST CHANGES — Score 62/100

---

## Executive Summary

Virtual Analyst is a well-architected financial modeling platform with a solid DAG-based engine, correct three-statement generation, and an impressive Monte Carlo simulation framework. However, **7 critical/high-priority gaps** prevent it from meeting the rigorous standards expected by financial professionals:

1. **Unauthenticated debug endpoint leaks PII in production** (Security — Critical)
2. **DCF valuation lacks mid-year convention, equity bridge, and applies exit multiples to FCF instead of EBITDA** (Finance — High)
3. **Anomaly detection is entirely LLM-based with zero statistical grounding** (Statistics — Critical)
4. **No tax loss carryforward (NOL) in multi-year models** (Finance — High)
5. **Monte Carlo simulation is not parallelized; per-sim Python loop** (Statistics — High)
6. **Single FX rate for entire consolidation horizon violates IAS 21** (Finance — High)
7. **Auth middleware falls back to "investor" role on DB errors** (Security — High)

The platform's foundation is strong. Addressing these issues would elevate it from a solid prototype to a production-grade financial analysis tool suitable for mid-market advisory, investment banking, and FP&A professionals.

---

## Table of Contents

1. [Security & Architecture](#1-security--architecture)
2. [Code Quality](#2-code-quality)
3. [Financial Metrics Review](#3-financial-metrics-review)
4. [Statistical Analysis Review](#4-statistical-analysis-review)
5. [Priority Roadmap](#5-priority-roadmap)
6. [Appendix: Full Issue Registry](#appendix-full-issue-registry)

---

## 1. Security & Architecture

### CRITICAL: Unauthenticated Debug Endpoint in Production

**File:** `apps/api/app/routers/health.py` (lines 76-120)

`GET /api/v1/health/debug-auth` bypasses authentication (falls under `SKIP_AUTH_PATHS`). It returns `tenant_id`, `user_id`, `user_email`, `user_role`, and database existence checks to any caller. This is live at the production API URL.

**Fix:** Remove the endpoint immediately. It was added as a temporary diagnostic (noted in MEMORY.md).

---

### HIGH: Auth Middleware Falls Back to "investor" Role on DB Error

**File:** `apps/api/app/middleware/auth.py` (lines 228-231)

When the database is unreachable during role lookup, the middleware silently assigns `"investor"` role to all authenticated users. This means a DB outage grants read access to financial data for users who should be blocked.

**Fix:** Return `503 Service Unavailable` on DB connectivity failure. If a fallback role is truly needed, use the most restrictive role (read-only or no-access), not `"investor"`.

---

### HIGH: Synchronous Redis Blocking the Async Event Loop

**File:** `apps/api/app/routers/runs.py` (lines 52-73)

The `redis` library is synchronous but called from async FastAPI handlers. This blocks the event loop on every MC progress check. The module-level `_redis_pool` global has a race condition under concurrent initialization, is never closed on shutdown, and all exceptions are silently swallowed (`except Exception: pass`).

**Fix:** Use `redis.asyncio`. Initialize pool in `lifespan`. Log exceptions at WARNING level.

---

### HIGH: JWKS Cache Race Condition in Auth Middleware

**File:** `apps/api/app/middleware/auth.py` (lines 136-138)

Global `_jwks_cache_time` is mutated in async context without locking. Concurrent requests during key rotation will each call synchronous `httpx.get()`, blocking the event loop N times.

**Fix:** Use `asyncio.Lock` for JWKS refresh. Replace synchronous `httpx.get()` with `httpx.AsyncClient`.

---

### MEDIUM: Dynamic SQL Pattern in Routers

**Files:** `apps/api/app/routers/afs.py` (lines 427-456), `budgets.py` (lines 156-176)

While values are properly parameterized, the f-string SQL construction pattern is error-prone for future developers. No explicit column allowlists exist.

**Fix:** Use static queries with full parameterization. Add `ALLOWED_SORT_COLUMNS` allowlists where dynamic columns are needed.

---

### MEDIUM: Sensitivity `parameter_path` Has No Depth/Prefix Allowlist

**File:** `shared/fm_shared/analysis/sensitivity.py` (lines 43-86)

User-supplied `parameter_path` strings traverse model attributes via `getattr`/`setattr` without depth limits or prefix restrictions.

**Fix:** Define a strict allowlist of permissible path prefixes. Enforce in Pydantic validators.

---

## 2. Code Quality

### HIGH: `generate_statements` Is 357 Lines, No Decomposition

**File:** `shared/fm_shared/model/statements.py` (lines 90-446)

A single function handles IS, BS, CF, debt scheduling, equity raises, convertible debt, capex/depreciation, working capital, dividend policy, and a 5-pass funding waterfall iteration. The waterfall block (lines 329-437) duplicates ~80 lines of IS/BS/CF recalculation.

**Fix:** Extract `_build_income_statement()`, `_build_balance_sheet()`, `_build_cash_flow()`, `_apply_funding_waterfall()`.

---

### HIGH: `budgets.py` Is 1,400+ Lines (God File)

**File:** `apps/api/app/routers/budgets.py`

27 route handlers, LLM features, CRUD, variance, reforecast, and a natural-language agent in one file.

**Fix:** Extract into `budgets_crud.py`, `budgets_variance.py`, `budgets_actuals.py`, `budgets_llm.py`.

---

### HIGH: `afs.py` Is 2,500+ Lines (God File)

**File:** `apps/api/app/routers/afs.py`

44 endpoints covering frameworks, engagements, trial balance, sections, reviews, tax, consolidation, and output generation.

**Fix:** Move orchestration logic into `apps/api/app/services/afs/` service layer. Keep router handlers thin.

---

### HIGH: Frontend Status Mismatch Breaks Excel Export

**File:** `apps/web/app/(app)/runs/[id]/page.tsx` (line 300)

Backend sets `status = 'succeeded'` but frontend checks `run?.status === "completed"`. The export button never appears.

**Fix:** Align to `"succeeded"` on the frontend, or change backend to `"completed"`.

---

### MEDIUM: `StatementsData` Uses `unknown` Types

**File:** `apps/web/lib/api.ts` (lines 156-167)

`Record<string, unknown>[] | unknown` effectively erases all type safety. `KpiItem` uses an unbounded index signature.

**Fix:** Define concrete `IncomeStatementRow`, `BalanceSheetRow`, `CashFlowRow` interfaces. Enumerate KPI fields explicitly.

---

### MEDIUM: N+1 Query Problem in Budget Dashboard

**File:** `apps/api/app/routers/budgets.py` (lines 374-472)

4 sequential DB queries per budget inside a loop. 20 budgets = 80+ round-trips.

**Fix:** Use `WHERE budget_id = ANY($1)` to batch all queries. Reduces to 4 queries total.

---

### MEDIUM: Bare `except Exception: pass` Throughout

**Files:** `runs.py:64`, `billing.py:119`, `documents.py:213`, `assignments.py:442`, `scenarios.py:166`, `jobs.py:35,46`

Silent exception swallowing makes failures invisible in monitoring.

**Fix:** Log at WARNING level before returning None/default.

---

## 3. Financial Metrics Review

### HIGH: DCF — No Mid-Year Convention

**File:** `shared/fm_shared/analysis/valuation.py` (line 54)

Discount factor `(1+WACC)^((t+1)/12)` discounts to period-end. Professional DCF uses mid-period convention because cash flows are earned throughout the period. Impact: 4-5% systematic undervaluation at 10% WACC over 5 years.

**Standard:** CFA Valuation (Koller et al. "Valuation" Chapter 8)

**Fix:** Change to `(t + 0.5) / 12.0`. Apply mid-year adjustment to terminal value.

---

### HIGH: DCF — No Equity Bridge (EV to Equity Value)

**File:** `shared/fm_shared/analysis/valuation.py` (lines 67-68)

Returns `enterprise_value` only. No `equity_value = EV - net_debt - minority_interest + associates`. Users cannot derive per-share value or compare to market cap.

**Standard:** Investment banking standard (Goldman Sachs, Morgan Stanley valuation manuals)

**Fix:** Add net debt, minority interest inputs. Return both EV and equity value.

---

### HIGH: DCF — Exit Multiple Applied to FCF, Not EBITDA

**File:** `shared/fm_shared/analysis/valuation.py` (lines 64-65)

`terminal_value = fcf_annual * terminal_multiple` — but exit multiples are conventionally applied to EBITDA. A "12x multiple" on FCF vs EBITDA produces fundamentally different (and lower) terminal values.

**Standard:** EV/EBITDA is the industry-standard exit multiple methodology.

**Fix:** Accept `terminal_ebitda` parameter. Default to EBITDA-based terminal value.

---

### HIGH: No Tax Loss Carryforward (NOL)

**File:** `shared/fm_shared/model/statements.py` (line 182)

`tax = max(0.0, ebt * tax_rate)` — no NOL accumulation. A company with losses in Years 1-3 and profits in Year 4 would, in reality, use carryforward losses to reduce Year 4 tax. The model systematically over-taxes post-loss profits.

**Standard:** IAS 12 / ASC 740 (Deferred Tax Assets)

**Fix:** Add cumulative NOL tracker. Offset against future EBT (with jurisdictional caps, e.g., 80% US TCJA).

---

### HIGH: DSO/DIO/DPO Inconsistency Between Calculators

**File:** `kpis.py` (lines 57-65) vs `ratio_calculator.py` (lines 77-79)

Model KPIs use 30-day months. AFS ratios use 365-day years. Same entity viewed in both modules shows different working capital metrics.

**Standard:** Internal consistency (CFA Level I Financial Statement Analysis)

**Fix:** Standardize calculation basis. Document methodology. Annualize monthly figures before applying 365-day formula.

---

### HIGH: Consolidation — Single FX Rate for Entire Horizon

**File:** `shared/fm_shared/analysis/consolidation.py` (lines 114-160)

Uses one `avg_rate` and one `closing_rate` for all periods. IAS 21 requires period-specific rates. Multi-year consolidated financials are meaningless without varying exchange rates.

**Standard:** IAS 21.39-40 / ASC 830-10-45-6

**Fix:** Accept per-period rate arrays. Apply `avg_rate[t]` to IS, `closing_rate[t]` to BS.

---

### HIGH: Proportional Consolidation Not IFRS 11 Compliant

**File:** `shared/fm_shared/analysis/consolidation.py` (lines 254-271)

IFRS 11 eliminated proportional consolidation for joint ventures (equity method only). Code doesn't distinguish joint ventures from joint operations.

**Standard:** IFRS 11 (Joint Arrangements)

**Fix:** Add `joint_arrangement_type` field. Force equity method for ventures.

---

### MEDIUM: Altman Z-Score Uses Total Equity as Retained Earnings Proxy

**File:** `apps/api/app/services/afs/ratio_calculator.py` (lines 85-93)

Inflates the Z-score for companies with significant paid-in capital, producing overly optimistic bankruptcy risk assessment.

**Fix:** Separate retained earnings from total equity in account classification.

---

### MEDIUM: Only Original Z-Score (1968) — No Z' or Z'' Variants

Private companies and non-manufacturers get inaccurate Z-scores. Z' (1983) for private companies and Z'' (1993) for non-manufacturing firms are missing.

**Fix:** Detect entity characteristics and apply appropriate variant.

---

### MEDIUM: Multiples Valuation Uses min/max, Not Percentiles

**File:** `shared/fm_shared/analysis/valuation.py` (lines 91-107)

Professional comparable company analysis uses IQR (P25/P75). Raw min/max is skewed by outliers.

**Fix:** Return median, P25, P75. Flag outliers outside 1.5x IQR.

---

### MEDIUM: No WACC Calculator

WACC is input-only. No CAPM-based cost of equity, cost of debt, or capital structure weighting.

**Fix:** Implement `WACC = (E/V) x Re + (D/V) x Rd x (1-T)` where `Re = Rf + Beta x ERP`.

---

### MEDIUM: Declining Balance Depreciation Defined in Schema but Not Implemented

**File:** `statements.py` (line 139), `schemas.py` (line 90)

Schema allows `"declining_balance"` but code always uses straight-line. Silent data loss.

**Fix:** Read `depreciation_method` and implement declining balance.

---

### MEDIUM: Interest/Tax Not Disclosed Separately in Cash Flow

**Standard:** IAS 7.35, ASC 230-10-45-25 require separate disclosure.

**Fix:** Add `interest_paid` and `taxes_paid` as separate OCF line items.

---

### MEDIUM: CTA Calculation Is Simplified/Incorrect

The CTA formula uses the same closing rate for opening and closing equity, producing zero CTA from equity retranslation.

**Fix:** Implement proper CTA with historical rates for equity components.

---

## 4. Statistical Analysis Review

### CRITICAL: Anomaly Detection Is Entirely LLM-Based

**File:** `apps/api/app/services/afs/analytics_ai.py` (lines 98-126)

Zero statistical computation: no Z-scores, no IQR outlier flagging, no Grubbs' test. The LLM decides what is "unusual" with no quantitative criteria. This produces non-reproducible, non-auditable results.

**Standard:** ISA 520 (Analytical Procedures)

**Fix:** Add deterministic pre-screening: Z-scores against benchmarks, IQR x 1.5 outlier flags, YoY change magnitude. Feed statistical flags to LLM for interpretation, not detection.

---

### HIGH: Going Concern Assessment Lacks Quantitative Thresholds

**File:** `apps/api/app/services/afs/analytics_ai.py` (lines 160-188)

Standard ISA 570 / ASC 205-40 indicators (Altman Z < 1.8, current ratio < 1.0, consecutive losses, DSCR < 1.0) are not systematically checked before LLM assessment.

**Fix:** Build deterministic risk score with ISA 570 criteria. Pass to LLM for narrative.

---

### HIGH: Monte Carlo Per-Simulation Loop (No Parallelism)

**File:** `shared/fm_shared/analysis/monte_carlo.py` (lines 68-100)

Full Python `for` loop with `run_engine()` + `generate_statements()` + `calculate_kpis()` per iteration. 10,000 sims = minutes for complex models.

**Fix:** Use `ProcessPoolExecutor` (already proven in `sensitivity.py`). Vectorize sampling step.

---

### HIGH: Correlated Sampling Recomputes Cholesky Each Call

**File:** `shared/fm_shared/analysis/distributions.py` (lines 90-156)

`sample_correlated()` generates exactly 1 sample per call. Cholesky is re-evaluated each of 10,000 invocations.

**Fix:** Restructure to accept `num_samples`. Compute Cholesky once, batch-sample.

---

### HIGH: Non-PD Matrix Silently Falls Back to Independent Sampling

User-specified correlations are completely ignored without any user-facing error when Cholesky fails.

**Fix:** Implement Higham nearest-PD correction. Escalate to user-facing warning.

---

### HIGH: No Global Sensitivity Analysis (Sobol/Morris)

**File:** `shared/fm_shared/analysis/sensitivity.py`

OAT analysis cannot capture interaction effects between parameters. A critical gap for multi-factor financial models.

**Fix:** Implement Morris screening (computationally efficient, captures interactions).

---

### HIGH: No Statistical Forecasting Methods

No regression, no ARIMA/SARIMA, no exponential smoothing, no forecast accuracy metrics (MAPE, RMSE). The reforecast agent relies entirely on LLM for trend detection.

**Fix:** Implement linear regression trend analysis, Holt-Winters for seasonal data, and MAPE/RMSE reporting.

---

### HIGH: No Confidence Intervals Reported Anywhere

No bootstrap CIs on percentile estimates, no standard errors, no margin-of-error calculations across the entire platform.

**Fix:** Report standard errors on MC percentiles. Add bootstrap CIs.

---

### MEDIUM: No Variance Reduction Techniques

No antithetic variates, stratified sampling, or Latin hypercube. Antithetic variates can reduce variance by 30-50% at near-zero cost.

**Fix:** Implement antithetic variates as low-effort, high-impact improvement.

---

### MEDIUM: No Convergence Diagnostics for Monte Carlo

Users get results regardless of whether percentile estimates have stabilized. No standard error estimates.

**Fix:** Add `convergence_achieved: bool` to MCResult. Check rolling P50 stability.

---

### MEDIUM: No Goodness-of-Fit Testing for Distribution Selection

Users manually select distribution families with no KS/AD testing against historical data.

**Fix:** Add `fit_distribution()` function with MLE fitting and test statistics.

---

### MEDIUM: Gaussian Copula Has Zero Tail Dependence

Financial variables crash together more often than they boom together. The Gaussian copula assumption has zero tail dependence.

**Fix:** Document limitation prominently. Consider Student-t copula for v2.

---

### MEDIUM: No EV Distribution from Monte Carlo

DCF and MC modules are not integrated. MC tracks revenue/EBITDA/NI/FCF percentiles but not enterprise value percentiles.

**Fix:** Run DCF per simulation, collect EV P5/P50/P95.

---

## 5. Priority Roadmap

### Sprint 1: Security & Critical Fixes (1-2 days)
| # | Item | Impact |
|---|------|--------|
| 1 | Remove `debug-auth` endpoint | Eliminates PII leak |
| 2 | Fix auth fallback role (503 not "investor") | Prevents unauthorized access |
| 3 | Fix frontend status mismatch ("succeeded" vs "completed") | Restores Excel export |
| 4 | Add exception logging to bare `except: pass` blocks | Restores observability |

### Sprint 2: DCF & Valuation (3-5 days)
| # | Item | Impact |
|---|------|--------|
| 5 | Mid-year convention in DCF | Eliminates 4-5% systematic undervaluation |
| 6 | Equity bridge (EV to Equity Value) | Enables per-share valuation |
| 7 | Terminal value: EBITDA-based exit multiple | Correct methodology |
| 8 | WACC calculator (optional, CAPM-based) | Reduces user error |
| 9 | Multiples: IQR percentiles instead of min/max | Professional standard |

### Sprint 3: Tax & Statements (3-5 days)
| # | Item | Impact |
|---|------|--------|
| 10 | NOL carryforward with jurisdictional caps | IAS 12 / ASC 740 compliance |
| 11 | Declining balance depreciation | IAS 16 completeness |
| 12 | Interest/tax disclosure in OCF | IAS 7.35 compliance |
| 13 | Harmonize DSO/DIO/DPO across calculators | User trust |

### Sprint 4: Statistical Foundation (5-7 days)
| # | Item | Impact |
|---|------|--------|
| 14 | Deterministic anomaly pre-screening (Z-scores, IQR) | Reproducible, auditable analytics |
| 15 | Going concern quantitative risk score | ISA 570 grounding |
| 16 | Parallelize Monte Carlo (ProcessPoolExecutor) | 4-8x performance improvement |
| 17 | Batch correlated sampling (Cholesky once) | Major MC speedup |
| 18 | Nearest-PD matrix correction | Preserves user correlations |
| 19 | Convergence diagnostics + standard errors | Statistical quality |

### Sprint 5: Consolidation & Global SA (5-7 days)
| # | Item | Impact |
|---|------|--------|
| 20 | Per-period FX rates in consolidation | IAS 21 compliance |
| 21 | Proper CTA calculation | Correct FX equity accounting |
| 22 | IFRS 11 joint venture/operation distinction | Regulatory compliance |
| 23 | Morris screening for global sensitivity | Captures parameter interactions |

### Sprint 6: Forecasting & Advanced Stats (5-7 days)
| # | Item | Impact |
|---|------|--------|
| 24 | Linear regression trend analysis | Foundation for forecasting |
| 25 | Holt-Winters exponential smoothing | Seasonal forecasting |
| 26 | MAPE/RMSE forecast accuracy metrics | Quality measurement |
| 27 | Antithetic variates for MC | 30-50% variance reduction |
| 28 | Distribution goodness-of-fit testing | Informed distribution selection |
| 29 | MC to DCF integration (EV percentiles) | Range-based valuation |

### Sprint 7: Code Quality & Refactoring (3-5 days)
| # | Item | Impact |
|---|------|--------|
| 30 | Decompose `generate_statements()` (357-line function) | Testability, maintainability |
| 31 | Split `budgets.py` (1,400+ lines) | Separation of concerns |
| 32 | Split `afs.py` (2,500+ lines) | Separation of concerns |
| 33 | Typed financial interfaces in TypeScript | Compile-time error detection |
| 34 | Async Redis + proper lifecycle | Performance, observability |
| 35 | Batch budget dashboard queries (N+1 fix) | Database performance |

---

## Positive Findings

The review also identified significant strengths:

- DAG-based engine with topological sort — correct, elegant dependency resolution
- Safe AST evaluator — no arbitrary code execution for user formulas
- PERT distribution — correctly implemented with proper beta shape parameters
- Sensitivity parallelism — ProcessPoolExecutor with proper pickling and fallback
- Monte Carlo percentiles — vectorized numpy percentile computation post-loop
- Seeded RNG — deterministic reproducibility across all statistical functions
- Funding waterfall — iterative convergence for interest feedback (up to 5 passes)
- Debt schedules — PIK, grace periods, convertible debt, ABL, IAS 1 current/non-current
- Cash flow integrity check — StatementImbalanceError if |CF closing - BS cash| > 0.01
- LLM temperature settings — well-calibrated (0.1 for going concern, 0.3 for commentary)
- Test coverage — solid unit tests with boundary testing, monotonicity assertions, parallel/sequential equivalence

---

## Appendix: Full Issue Registry

| # | Severity | Category | File | Issue | Standard |
|---|----------|----------|------|-------|----------|
| S1 | CRIT | Security | health.py | Unauthenticated debug endpoint leaks PII | OWASP A01 |
| S2 | HIGH | Security | auth.py:228 | Auth fallback to "investor" on DB error | Least privilege |
| S3 | HIGH | Security | runs.py:52 | Sync Redis blocks async event loop | Performance |
| S4 | HIGH | Security | auth.py:136 | JWKS cache race condition | Concurrency safety |
| S5 | MED | Security | afs.py:427 | Dynamic SQL pattern (values safe, pattern risky) | OWASP A03 |
| S6 | MED | Security | sensitivity.py:43 | No parameter_path allowlist | Input validation |
| C1 | HIGH | Code | statements.py:90 | 357-line function, no decomposition | SRP |
| C2 | HIGH | Code | budgets.py | 1,400+ line god file | SRP |
| C3 | HIGH | Code | afs.py | 2,500+ line god file | SRP |
| C4 | HIGH | Code | runs/[id]/page.tsx:300 | Status mismatch breaks export | Bug |
| C5 | MED | Code | api.ts:156 | Unknown types erase type safety | Type safety |
| C6 | MED | Code | budgets.py:374 | N+1 query problem (80+ round-trips) | Performance |
| C7 | MED | Code | runs.py:64 | Bare except swallows exceptions | Observability |
| F1 | HIGH | Finance | valuation.py:54 | No mid-year convention | CFA/Koller |
| F2 | HIGH | Finance | valuation.py:67 | No equity bridge (EV to Equity) | IB standard |
| F3 | HIGH | Finance | valuation.py:64 | Exit multiple on FCF not EBITDA | Valuation practice |
| F4 | HIGH | Finance | statements.py:182 | No tax loss carryforward | IAS 12/ASC 740 |
| F5 | HIGH | Finance | kpis.py vs ratio_calc | DSO/DIO/DPO inconsistency | Consistency |
| F6 | HIGH | Finance | consolidation.py:114 | Single FX rate for all periods | IAS 21.39 |
| F7 | HIGH | Finance | consolidation.py:254 | Proportional consol not IFRS 11 | IFRS 11 |
| F8 | MED | Finance | ratio_calculator.py:85 | Altman Z uses equity proxy | Altman 1968 |
| F9 | MED | Finance | ratio_calculator.py | No Z' or Z'' variants | Altman 1983/93 |
| F10 | MED | Finance | valuation.py:91 | Multiples use min/max not IQR | CCA standard |
| F11 | MED | Finance | valuation.py | No WACC calculator | Completeness |
| F12 | MED | Finance | statements.py:139 | Declining balance not implemented | IAS 16 |
| F13 | MED | Finance | statements.py:291 | No interest/tax disclosure in OCF | IAS 7.35 |
| F14 | MED | Finance | consolidation.py:146 | CTA calculation simplified | IAS 21.41 |
| F15 | MED | Finance | consolidation.py:340 | NCI double-counting risk | IFRS 10.22 |
| F16 | MED | Finance | consolidation.py | No goodwill/PPA | IFRS 3 |
| F17 | MED | Finance | debt.py:90 | Grace period shifts repayments | Loan mechanics |
| F18 | MED | Finance | budgets.py:1345 | No absolute materiality threshold | ISA 320 |
| ST1 | CRIT | Stats | analytics_ai.py:98 | Anomaly detection purely LLM-based | ISA 520 |
| ST2 | HIGH | Stats | analytics_ai.py:160 | Going concern no quant thresholds | ISA 570 |
| ST3 | HIGH | Stats | monte_carlo.py:68 | Per-sim loop, no parallelism | Performance |
| ST4 | HIGH | Stats | distributions.py:90 | Cholesky recomputed per sample | Performance |
| ST5 | HIGH | Stats | distributions.py:128 | Non-PD silent fallback to independent | Correctness |
| ST6 | HIGH | Stats | sensitivity.py | No global SA (Sobol/Morris) | Saltelli |
| ST7 | HIGH | Stats | (missing) | No statistical forecasting methods | Time-series |
| ST8 | HIGH | Stats | (cross-cutting) | No confidence intervals anywhere | ASA/APA |
| ST9 | MED | Stats | monte_carlo.py | No variance reduction techniques | Glasserman |
| ST10 | MED | Stats | monte_carlo.py | No convergence diagnostics | MC standards |
| ST11 | MED | Stats | distributions.py | No goodness-of-fit testing | Dist. selection |
| ST12 | MED | Stats | distributions.py | Gaussian copula zero tail dependence | Risk modeling |
| ST13 | MED | Stats | valuation.py | No EV distribution from MC | Range valuation |
| ST14 | MED | Stats | benchmarks.json | Static benchmarks, no provenance | Data quality |
| ST15 | MED | Stats | ratio_calculator.py | No input outlier detection | Robust stats |

**Total: 2 Critical, 17 High, 22 Medium = 41 findings**

---

*Review conducted using engineering-skills:code-reviewer, finance-skills:financial-analyst, and engineering-skills:senior-data-scientist perspectives.*
