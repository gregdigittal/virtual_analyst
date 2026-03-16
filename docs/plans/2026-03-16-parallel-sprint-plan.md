# Virtual Analyst — Parallel-Agent Sprint Plan
> Generated: 2026-03-16
> Author: Chief Architect Review
> Source: Sprint planning prompt + live codebase audit

---

## Executive Summary

### Scope Correction: Most "Open" Items Are Already Done

The planning prompt that generated this document listed 12 open items (AFS P1–P5, PIM Sprint 7,
Tier 5 infra). A live codebase audit before writing this plan found the following:

| Item Group | Prompt Said | Actual State |
|---|---|---|
| AFS P1–P6 | Open | ✅ Complete (done 2026-03-15) — routers, migrations, frontend all shipped |
| PIM Sprints 1–5 (Sentiment/Economic/CIS/Markov/Portfolio/Backtest) | Implied open | ✅ Complete — 1,838 lines across 5 routers, full test coverage |
| PIM-7.4 PE Dashboard UI | Open | ✅ Complete — `/pim/pe/[id]/page.tsx` shipped |
| PIM-7.5 PIM Billing Gate | Open | ✅ Complete — `require_pim_access` in `deps.py`, middleware live |
| PIM-7.6 Limitations Disclosure | Open | ✅ Complete — `limitations` field in pim_backtest, pim_cis, pim_portfolio, pim_pe |
| N-05 OpenAPI Schema Validation | Open | ⚠️ Partially done — 125-line test exists, **missing PIM endpoint coverage** |
| N-06 API-Level Load Tests | Open | ⚠️ Partially done — 95-line test exists, **covers only health/connectors/openapi** |

### Genuinely Open Items (as of 2026-03-16)

| Item | Description | Effort |
|---|---|---|
| **PIM-7.7** | Uncertainty bounds (confidence intervals) on CIS scores + Markov steady-state probabilities | M |
| **N-03** | Fix 3 failing E2E specs + expand coverage for PIM/AFS flows | M |
| **N-05-ext** | Extend OpenAPI schema tests to cover all `/api/v1/pim/*` routes | S |
| **N-06-ext** | Extend API load tests for PIM endpoints (pim_cis, pim_markov, pim_pe, pim_backtest) | S |

### Summary

| Metric | Value |
|---|---|
| Total remaining effort | ~3–4 engineer-days |
| Number of sprints | 1 sprint (Sprint 8) |
| Estimated completion | 2026-03-21 (1 week, 4 parallel streams) |
| Top 3 risks | (1) Bootstrap CI math complexity in PIM-7.7; (2) 3 failing E2E specs may require backend fixes; (3) PIM load tests need auth/tenant mocking |

---

## 1. Dependency Graph

```
PIM-7.7 ──────────────────────────────────────────────────► Commit (SP8-Z)
  (independent — no DB, no migrations, pure service + schema change)

N-03 ────────────────────────────────────────────────────► Commit (SP8-Z)
  (no backend changes; uses existing servers in CI)

N-05-ext ───────────────────────────────────────────────► Commit (SP8-Z)
  (read-only: calls /openapi.json, no production code changes)

N-06-ext ───────────────────────────────────────────────► Commit (SP8-Z)
  (read-only: test-client calls, no production code changes)
```

### Hard Dependencies (blocks)
- None between the 4 tasks — all are independent.
- SP8-Z (commit + BACKLOG update) is blocked by all 4 tasks completing.

### Parallel-Safe (can run simultaneously)
- PIM-7.7 ↔ N-03 ↔ N-05-ext ↔ N-06-ext — zero file overlap:
  - PIM-7.7 touches: `pim_cis.py`, `pim_markov.py`, `shared/fm_shared/analysis/`
  - N-03 touches: `apps/web/e2e/`
  - N-05-ext touches: `tests/unit/test_openapi_schema.py`
  - N-06-ext touches: `tests/load/test_api_performance.py`

### Soft Dependencies (preferred ordering, not blocking)
- PIM-7.7 backend changes slightly before api.ts binding update (but api.ts binding is a 2-line
  addition and carries no sequencing risk).

### High-Conflict Files (single-stream rule)
These files are assigned to exactly one stream and not touched concurrently:

| File | Assigned Stream | Reason |
|---|---|---|
| `apps/web/lib/api.ts` | Stream B (PIM-7.7) | Only stream B touches; 1 new interface |
| `apps/web/tests/pages/setup.tsx` | Stream C (N-03) | Only E2E stream touches |
| `BACKLOG.md` | Stream D at commit | End-of-sprint task only |

---

## 2. Agent Stream Assignments

### Stream A — AFS Core
**Status: COMPLETE. No tasks remain.**
All AFS P1–P6 routers, migrations, and frontend pages are shipped. This stream is retired.

---

### Stream B — PIM Completion
**Agent:** `pim-builder`
**Start condition:** Any time — no prerequisites.
**Handoff:** Produces updated `pim_cis.py` and `pim_markov.py` with CI fields; `api.ts` binding update for Stream C to consume.

**Tasks:**

| # | Task | Effort | Files |
|---|------|--------|-------|
| SP8-B1 | Add `confidence_interval` to CIS score response (bootstrap CI on composite score) | M | `pim_cis.py`, `shared/fm_shared/analysis/` (if CI logic belongs in engine), `api.ts` |
| SP8-B2 | Add `ci_lower`/`ci_upper` to Markov steady-state probability response (analytical CI via Dirichlet) | S | `pim_markov.py` |
| SP8-B3 | Add 3 unit tests: CIS CI width > 0, Markov CI sums ≤ 1.0, CI degrades gracefully with thin data | S | `tests/unit/test_pim_cis_api.py`, `tests/unit/test_pim_markov_api.py` |

**Parallelisable with:** SP8-C1, SP8-D1, SP8-D2 (zero file overlap)

---

### Stream C — Frontend & E2E
**Agent:** `general-purpose`
**Start condition:** Any time — no backend changes required for most tasks.
**Handoff:** Fixed E2E suite + new PIM/AFS flows feeds N-08 CI gate (already configured).

**Tasks:**

| # | Task | Effort | Files |
|---|------|--------|-------|
| SP8-C1 | Diagnose and fix 3 failing E2E specs (UI detail page link failures per BACKLOG) | S | `apps/web/e2e/functional/` (target: 3 failing specs) |
| SP8-C2 | Add E2E flows: PIM sentiment dashboard load, PE assessment detail, AFS engagement create | M | `apps/web/e2e/functional/ch-pim-*.spec.ts`, `ch-afs-engagement.spec.ts` |

**Parallelisable with:** SP8-B1, SP8-B2, SP8-B3, SP8-D1, SP8-D2

---

### Stream D — Infrastructure & Quality
**Agent:** `general-purpose`
**Start condition:** Any time — no prerequisites.
**Handoff:** Extended test coverage feeds CI gate and quality metrics.

**Tasks:**

| # | Task | Effort | Files |
|---|------|--------|-------|
| SP8-D1 | Extend `test_openapi_schema.py` to assert all `/api/v1/pim/*` prefixes present + validate response shape for 3 key PIM endpoints | S | `tests/unit/test_openapi_schema.py` |
| SP8-D2 | Extend `test_api_performance.py` with P95 latency assertions for `pim_cis`, `pim_markov`, `pim_pe`, `pim_backtest` endpoints | S | `tests/load/test_api_performance.py` |

**Parallelisable with:** SP8-B1, SP8-B2, SP8-B3, SP8-C1, SP8-C2

---

## 3. Sprint Breakdown

### Sprint 8 — Platform Hardening & Statistical Standards (1 week)

**Goal:** Close all open SR-3 statistical standard requirements (uncertainty bounds), fix the 3
failing E2E specs, and complete PIM coverage in the OpenAPI and load test suites.

**`/goal` invocation:**
```
/goal --supervised Sprint 8: Close PIM-7.7 (uncertainty bounds on CIS/Markov), fix 3 failing E2E specs and add PIM/AFS flows (N-03), extend OpenAPI schema tests for PIM routes (N-05-ext), extend API load tests for PIM endpoints (N-06-ext). Then commit, push, and update BACKLOG.md.
```

**Task list (6 tasks — well within the 10-task safety limit):**

| ID | Title | Stream | Agent | Inputs | Outputs | Effort | Parallel with |
|---|---|---|---|---|---|---|---|
| SP8-B1 | Add confidence intervals to CIS score response | B | pim-builder | `pim_cis.py` current implementation; SR-3 spec (bootstrap or analytical CI) | Updated `pim_cis.py` with `ci_lower`, `ci_upper`, `ci_method` fields; updated `api.ts` binding | M | SP8-C1, SP8-D1, SP8-D2 |
| SP8-B2 | Add CI to Markov steady-state probabilities | B | pim-builder | `pim_markov.py`; SP8-B1 pattern (Dirichlet analytical CI) | Updated `pim_markov.py` steady-state response with `ci_lower`, `ci_upper` per state | S | SP8-C1, SP8-D1, SP8-D2 |
| SP8-C1 | Fix 3 failing E2E specs + add 3 PIM/AFS flows | C | general-purpose | Failing spec file names from BACKLOG (UI detail page links); existing `seeded-ids.json` | 3 fixed specs; 3 new spec files; 0 failing, 35+ passing | M | SP8-B1, SP8-B2, SP8-D1, SP8-D2 |
| SP8-D1 | Extend OpenAPI schema tests for PIM routes | D | general-purpose | `test_openapi_schema.py` (125 lines); list of 8 PIM router prefixes | 8 new prefix assertions + 3 response-shape tests for CIS, Markov, PE memo | S | SP8-B1, SP8-B2, SP8-C1, SP8-D2 |
| SP8-D2 | Extend API load tests for PIM endpoints | D | general-purpose | `test_api_performance.py` (95 lines); 4 PIM router handlers | 4 new P95 latency test functions (CIS, Markov, PE memo, backtest commentary) | S | SP8-B1, SP8-B2, SP8-C1, SP8-D1 |
| SP8-Z | Run fast gate, commit, push, update BACKLOG.md | — | general-purpose | All SP8-B/C/D outputs passing `ruff + mypy + pytest + vitest` | Commit on `main`; BACKLOG.md updated to close PIM-7.7, N-03, N-05, N-06 | XS | — (final task) |

**Sprint 8 acceptance criteria:**
- [ ] `pim_cis` and `pim_markov` responses include `ci_lower`, `ci_upper` fields with values
- [ ] CIs degrade gracefully (returns `null` with a `ci_warning` message when n < 30)
- [ ] 0 failing E2E specs (was 3); 3+ new PIM/AFS E2E flows passing
- [ ] `test_openapi_schema.py` asserts all 8 `/api/v1/pim/*` prefixes present
- [ ] `test_api_performance.py` P95 assertions for 4 PIM endpoints pass
- [ ] Fast gate passes: `ruff + black --check + mypy + pytest unit/golden + vitest`
- [ ] BACKLOG.md reflects Sprint 8 as complete

---

## 4. Critical Path

```
START
  ├─ SP8-B1 (M) ──► SP8-B2 (S) ─┐
  ├─ SP8-C1 (M) ─────────────────┤
  ├─ SP8-D1 (S) ─────────────────┤
  └─ SP8-D2 (S) ─────────────────┴──► SP8-Z (XS) ──► DONE
```

**Critical path:** SP8-B1 → SP8-B2 → SP8-Z
**Reason:** SP8-B1 is the largest task (M) and SP8-B2 depends on it for the CI pattern.

**Minimum calendar time (all streams parallel):**
- SP8-B1 (M, ~4h) + SP8-B2 (S, ~1h) + SP8-Z (XS, ~30min) = **~6 hours of serial work**
- SP8-C1, SP8-D1, SP8-D2 are all ≤ SP8-B1's duration — they do not extend the critical path
- Realistic wall-clock time with review + iteration: **1–2 days**

**Calendar estimate if all 4 streams run simultaneously:**

| Day | Stream B | Stream C | Stream D (N-05) | Stream D (N-06) |
|---|---|---|---|---|
| Day 1 AM | SP8-B1: CIS CI implementation | SP8-C1: Fix failing specs | SP8-D1: PIM prefix assertions | SP8-D2: PIM P95 tests |
| Day 1 PM | SP8-B2: Markov CI | SP8-C1 cont: new flows | SP8-D1 cont: response shape | SP8-D2 cont: 4 endpoints |
| Day 2 | Fast gate, review, SP8-Z commit | | | |

**Estimated completion: 2026-03-18** (2 working days from today)

---

## 5. Risk Register

### Sprint 8

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Bootstrap CI complexity in SP8-B1** — CIS composite score is a weighted sum across 5 factors; bootstrap requires resampling factor inputs, which may not be stored per-call. | Medium | Medium | Fall back to analytical CI using score variance across the factor components (simpler, defensible for SR-3). If inputs aren't available for bootstrap, use the Dirichlet approach (same as Markov). |
| **3 failing E2E specs require backend fixes** — The 3 failures are described as "UI detail page links." If they're caused by seeded-IDs fixture drift or missing backend routes, SP8-C1 scope expands. | Low | Medium | Diagnose first (30 min). If root cause is backend (missing route, 404), escalate to pim-builder for a companion SP8-B0 task before SP8-C1 proceeds. |
| **PIM load tests require auth mocking** — `test_api_performance.py` currently uses simple `X-Tenant-ID` header. PIM routes use `require_pim_access` which does a DB check — this will fail in the test client without a mock. | High | Low | Patch `check_pim_access` in the load test setup (same pattern as `test_require_pim_access.py`). Document in test file header. |
| **api.ts concurrent edit risk** — If any other work touches `api.ts` during Sprint 8, Stream B's CI field additions will create a merge conflict. | Low | Low | SP8-B1 adds a single new interface (`CISScoreResponse`) at the bottom of the existing PIM group. Minimize surface area; do not reorganise surrounding code. |

---

## 6. Updated BACKLOG.md Structure

### Proposed restructuring

The current BACKLOG.md uses a tier-based flat list that has served its purpose. With the project
now at Sprint 8 (final hardening), the structure should shift to a **completion archive +
open sprint table**.

#### Proposed top-level sections

```markdown
# Virtual Analyst — Backlog
> Updated: 2026-03-16

## Current Sprint

### Sprint 8 — Platform Hardening (2026-03-16 to 2026-03-21)

| ID | Title | Stream | Status | Effort |
|---|---|---|---|---|
| SP8-B1 | CIS confidence intervals | B (pim-builder) | Open | M |
| SP8-B2 | Markov steady-state CI | B (pim-builder) | Open | S |
| SP8-C1 | Fix 3 failing E2E + add PIM/AFS flows | C (general-purpose) | Open | M |
| SP8-D1 | OpenAPI schema tests — PIM coverage | D (general-purpose) | Open | S |
| SP8-D2 | API load tests — PIM coverage | D (general-purpose) | Open | S |
| SP8-Z  | Commit + push + BACKLOG update | — | Blocked | XS |

## Parallel Execution Map

[Mermaid or ASCII dependency diagram — see Section 1 of sprint plan]

## Post-Sprint 8: No Known Backlog

All Tier 1–7 items, AFS P1–P6, and PIM Sprints 0–6 are complete as of 2026-03-16.
Next work is driven by product requirements.

## Completed Rounds (archive)

[Move all existing tier tables here, collapsed with <details> tags for readability]
```

#### Parallel Execution Map (for insertion into BACKLOG.md)

```
Sprint 8 — Parallel Execution Map (2026-03-16)

Stream B (pim-builder)      SP8-B1 ──► SP8-B2 ─────────────────────► SP8-Z
Stream C (general-purpose)  SP8-C1 ──────────────────────────────────► SP8-Z
Stream D-N05 (general)      SP8-D1 ──────────────────────────────────► SP8-Z
Stream D-N06 (general)      SP8-D2 ──────────────────────────────────► SP8-Z

All 4 streams start simultaneously on Day 1.
SP8-Z unblocks when all 4 streams report SKILL_COMPLETE.
```

---

## Appendix: Items Verified Complete (prompt listed as open)

The following items appeared in the planning prompt as open but are confirmed complete
by live codebase audit:

| Item | Evidence of Completion |
|---|---|
| AFS-P1 Framework + Ingestion | `routers/afs/frameworks.py`, `routers/afs/engagements.py`, `routers/afs/ingestion.py`; migrations `0052_afs.sql`; frontend `app/(app)/afs/page.tsx` + `frameworks/[id]/page.tsx` |
| AFS-P2 AI Disclosure Drafter | `routers/afs/disclosure.py`; migration `0053_afs_sections.sql` |
| AFS-P3 Workflow + Tax | `routers/afs/review.py`, `routers/afs/tax.py`; migration `0054_afs_reviews_tax.sql` |
| AFS-P4 Consolidation + Filing | `routers/afs/consolidation.py`, `routers/afs/outputs.py`; migration `0055_afs_consolidation_outputs.sql` |
| AFS-P5 Analytics | `routers/afs/analytics.py`; migration `0056_afs_analytics.sql` |
| PIM Sprint 1 (Sentiment) | `routers/pim_sentiment.py` (338 lines); `tests/unit/test_pim_sentiment_api.py`, `test_pim_sentiment_ingestor.py` |
| PIM Sprint 2 (Economic/FRED) | `routers/pim_universe.py`; `app/(app)/pim/economic/` |
| PIM Sprint 3 (CIS + Markov) | `routers/pim_cis.py` (319 lines), `routers/pim_markov.py` (257 lines); `app/(app)/pim/markov/` |
| PIM Sprint 4 (Portfolio) | `routers/pim_portfolio.py` (364 lines); `app/(app)/pim/universe/` |
| PIM Sprint 5 (Backtest) | `routers/pim_backtest.py` (560 lines); `app/(app)/pim/backtest/`; migrations `0066_pim_backtest_results.sql`, `0067_pim_backtest_commentary.sql`, `0069_pim_backtest_summary_mv.sql` |
| PIM Sprint 6 (PE Benchmarking) | `routers/pim_pe.py`, `routers/pim_peer.py`; migrations `0070_pim_pe_assessments.sql`, `0071_pim_peer_benchmarks.sql`; `app/(app)/pim/pe/` |
| PIM-7.4 PE Dashboard UI | `app/(app)/pim/pe/page.tsx`, `app/(app)/pim/pe/[id]/page.tsx` |
| PIM-7.5 PIM Billing Gate | `deps.py:require_pim_access()`; `tests/unit/test_require_pim_access.py` |
| PIM-7.6 Limitations Disclosure | `pim_backtest.py:321/404/559`, `pim_cis.py:148/315`, `pim_portfolio.py:128/344` — all LLM-generated outputs carry `limitations` field |
| N-05 OpenAPI schema validation | `tests/unit/test_openapi_schema.py` (125 lines) — **partial; PIM coverage gap remains as N-05-ext** |
| N-06 API load tests | `tests/load/test_api_performance.py` (95 lines) — **partial; PIM coverage gap remains as N-06-ext** |
