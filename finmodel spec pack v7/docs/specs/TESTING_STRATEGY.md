# Testing Strategy
**Date:** 2026-02-08

## Principles
1. **Financial accuracy is non-negotiable.** The calculation engine needs test coverage that proves correctness with hand-calculable examples.
2. **Schema validation is the first line of defense.** Every artifact must validate against its JSON Schema.
3. **Tests are phased.** Each build phase adds tests. No phase gate passes without its tests green.

## Test Framework
- **Python:** pytest + pytest-asyncio
- **TypeScript:** Vitest (for Next.js) + Playwright (E2E)
- **CI:** GitHub Actions — tests run on every PR

## Test Categories

### Unit Tests (`tests/unit/`)
Fast, no external dependencies (DB, LLM, network).

**Engine tests (`tests/unit/engine/`):**
- `test_graph_builder.py` — DAG construction, cycle detection, topo sort
- `test_expression_evaluator.py` — arithmetic, functions, variable substitution
- `test_time_series.py` — constant drivers, ramp schedules, seasonal patterns
- `test_income_statement.py` — revenue, COGS, EBITDA, net income
- `test_balance_sheet.py` — WC calculations, cash plug, BS balance check
- `test_cash_flow.py` — operating/investing/financing, CF ↔ BS cash reconciliation
- `test_kpis.py` — all KPI formulas against known inputs
- `test_distributions.py` — sample statistics match expected (mean, std within tolerance)
- `test_monte_carlo.py` — determinism with seed, P50 near base case

**Schema tests (`tests/unit/schemas/`):**
- `test_schema_validation.py` — every example JSON in ARTIFACT_EXAMPLES/ validates against its schema
- `test_pydantic_models.py` — round-trip: JSON → Pydantic → JSON → identical
- `test_invalid_rejects.py` — known-invalid artifacts are rejected with correct errors

**Service tests (`tests/unit/services/`):**
- `test_commit_pipeline.py` — integrity checks pass/fail correctly
- `test_changeset_merge.py` — overrides apply correctly
- `test_llm_router.py` — routing policy selects correct provider
- `test_usage_metering.py` — aggregation math is correct

### Integration Tests (`tests/integration/`)
Require running Supabase (local via Docker) but no external APIs.

- `test_baseline_crud.py` — create, read, update, archive via API
- `test_run_lifecycle.py` — create run → poll status → get results
- `test_draft_commit_flow.py` — create draft → modify → mark ready → commit → baseline exists
- `test_changeset_flow.py` — create → test → merge → new version
- `test_rls_isolation.py` — tenant A cannot read tenant B's data
- `test_auth_roles.py` — analyst cannot access billing; investor cannot create runs
- `test_artifact_storage.py` — save → load → identical; invalid → rejected

### E2E Tests (`tests/e2e/`)
Playwright tests against running frontend + API.

- `test_login_flow.spec.ts` — login → dashboard renders
- `test_venture_wizard.spec.ts` — create venture → answer questions → draft created
- `test_draft_to_run.spec.ts` — draft → commit → run → view statements
- `test_memo_generation.spec.ts` — generate memo → download PDF

### LLM Tests (`tests/llm/`)
These use recorded fixtures (VCR/cassette pattern), not live API calls:

- `test_draft_chat.py` — send message → structured proposals returned → valid schema
- `test_evidence_extraction.py` — upload fixture → extractions returned
- `test_memo_draft.py` — generate sections → valid content blocks
- `test_llm_fallback.py` — primary fails → secondary succeeds
- `test_llm_logging.py` — every call produces llm_call_log_v1

Record cassettes during development; replay in CI. Use `pytest-recording` or `vcrpy`.

## Phase-Specific Test Requirements

### Phase 1 Gate Tests
```
tests/unit/engine/test_graph_builder.py          — 5+ test cases
tests/unit/engine/test_expression_evaluator.py    — 10+ expressions
tests/unit/engine/test_income_statement.py        — Manufacturing template example
tests/unit/engine/test_balance_sheet.py           — BS balances every month
tests/unit/engine/test_cash_flow.py               — CF reconciles to BS
tests/unit/schemas/test_schema_validation.py      — All examples pass
tests/integration/test_baseline_crud.py           — CRUD + uniqueness
tests/integration/test_run_lifecycle.py           — Full run flow
```

### Phase 2 Gate Tests
```
tests/unit/services/test_commit_pipeline.py       — All integrity checks
tests/unit/services/test_llm_router.py            — Routing logic
tests/llm/test_draft_chat.py                      — Structured proposals (cassette)
tests/integration/test_draft_commit_flow.py       — Full draft → commit
tests/integration/test_auth_roles.py              — Role enforcement
```

### Phase 3 Gate Tests
```
tests/unit/engine/test_distributions.py           — All families
tests/unit/engine/test_monte_carlo.py             — Determinism + P50 check
tests/unit/engine/test_valuation.py               — DCF hand-calculation
tests/integration/test_mc_run.py                  — MC run via API
tests/integration/test_scenarios.py               — Scenario CRUD + apply
```

### Phase 4 Gate Tests
```
tests/integration/test_integration_connection.py  — OAuth mock
tests/integration/test_sync_run.py                — Sync fixture data
tests/integration/test_billing.py                 — Plan limits + metering
tests/integration/test_rls_isolation.py           — Multi-tenant isolation
```

### Phase 5 Gate Tests
```
tests/integration/test_excel_connection.py        — Binding CRUD
tests/integration/test_excel_push_pull.py         — Pull + push flow
tests/integration/test_memo_generation.py         — Generate all formats
tests/e2e/test_draft_to_run.spec.ts               — Full UI flow
```

## Golden File Tests (Engine Accuracy)
For the manufacturing template with known inputs, maintain golden output files:
- `tests/golden/manufacturing_base_statements.json` — hand-verified IS/BS/CF
- `tests/golden/manufacturing_base_kpis.json` — hand-verified KPIs
- `tests/golden/manufacturing_mc_p50.json` — expected P50 values (within tolerance)

Test compares engine output against golden files. If engine logic changes, golden files must be consciously updated (not auto-generated).

## CI Configuration
```yaml
# .github/workflows/test.yml
- Run unit tests (no Docker needed)
- Start Supabase local (Docker)
- Run integration tests
- Build Next.js app
- Run E2E tests (Playwright)
- Coverage report: minimum 70% line coverage for shared/fm_shared/
```
