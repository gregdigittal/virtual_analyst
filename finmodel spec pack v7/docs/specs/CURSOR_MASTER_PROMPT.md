# Cursor Master Prompt (v7)
**Date:** 2026-02-11

## System Identity
You are building **FinModel** — a deterministic forecasting and valuation platform with an LLM-assisted Draft layer. The LLM proposes; the deterministic engine executes. These two worlds never mix at runtime.

## Hard Constraints (never violate)
1. **Never execute arbitrary code from LLM output.** LLM output is treated as data (JSON), validated against schemas, and stored. The runtime engine uses only compiled model_config artifacts.
2. **Never mutate baselines directly.** All changes flow through changesets or draft sessions. Baselines are immutable once committed.
3. **Log and meter all LLM calls.** Every LLM invocation produces an `llm_call_log_v1` artifact. Usage is aggregated into `usage_meter_v1` per billing period.
4. **Schema-first development.** Every artifact has a JSON Schema in `ARTIFACT_SCHEMAS/`. Validate on write; reject invalid data.
5. **Tenant isolation via RLS.** Every table with `tenant_id` must have Supabase Row-Level Security policies. No cross-tenant data leaks.
6. **Deterministic reproducibility.** Given the same model_config + scenario + seed, the runtime engine must produce identical outputs.

## Architecture Overview
```
┌─────────────┐    ┌──────────────┐    ┌─────────────────┐
│  Web UI      │    │  Excel Add-in│    │  API Clients    │
│  (Next.js)   │    │  (Office.js) │    │                 │
└──────┬───────┘    └──────┬───────┘    └──────┬──────────┘
       │                   │                   │
       └───────────┬───────┴───────────────────┘
                   │
           ┌───────▼────────┐
           │   FastAPI       │
           │   REST API      │
           │                 │
           ├─────────────────┤
           │ Services Layer  │
           │  ├─ Draft       │  ← LLM-assisted (sandboxed)
           │  ├─ Commit      │  ← Validation + compile
           │  ├─ Runtime     │  ← Deterministic engine
           │  ├─ Integration │  ← ERP sync
           │  ├─ Billing     │  ← Usage metering
           │  └─ Export      │  ← Memo packs + Excel
           ├─────────────────┤
           │ Supabase        │
           │  ├─ Postgres    │
           │  ├─ Auth        │
           │  ├─ Storage     │  ← Artifact JSON blobs
           │  └─ Realtime    │  ← Change notifications
           └─────────────────┘
```

## Planning & Sequencing
- **Build Plan:** `docs/specs/BUILD_PLAN.md` — 6 phases with gate criteria (includes Phase 0)
- **Backlog:** `docs/specs/BACKLOG.md` — all work items with acceptance criteria

## Implementation Prompts (use in order)
- Phase 0: `docs/specs/PROMPTS/P00_FOUNDATION.md`
- Phase 1: `docs/specs/PROMPTS/P01_CORE_ENGINE.md`
- Phase 2: `docs/specs/PROMPTS/P02_DRAFT_LLM.md`
- Phase 3: `docs/specs/PROMPTS/P03_MC_SCENARIOS_VALUATION.md`
- Phase 4: `docs/specs/PROMPTS/P04_ERP_BILLING.md`
- Phase 5: `docs/specs/PROMPTS/P05_EXCEL_MEMOS.md`

## Key Specifications
- **Draft → Commit:** `docs/specs/DRAFT_COMMIT_SPEC.md`
- **Runtime Engine:** `docs/specs/RUNTIME_ENGINE_SPEC.md`
- **LLM Integration:** `docs/specs/LLM_INTEGRATION_SPEC.md`
- **Auth & Tenancy:** `docs/specs/AUTH_AND_TENANCY.md`
- **Frontend Stack:** `docs/specs/FRONTEND_STACK.md`
- **Testing:** `docs/specs/TESTING_STRATEGY.md`
- **Foundation Specs:** `docs/specs/ERROR_HANDLING_SPEC.md`, `docs/specs/PERFORMANCE_SPEC.md`, `docs/specs/OBSERVABILITY_SPEC.md`, `docs/specs/DEPLOYMENT_SPEC.md`, `docs/specs/AUDIT_COMPLIANCE_SPEC.md`, `docs/specs/SECURITY_SPEC.md`

## Schema Index
All artifact schemas in `docs/specs/ARTIFACT_SCHEMAS/`:
- `model_config_v1` — compiled model configuration (THE core artifact)
- `macro_regime_v1` — macroeconomic overlay (rates, CPI, FX)
- `sentiment_v1` — assumption confidence + evidence
- `org_structure_v1` — multi-entity / group structure
- `integration_connection_v1`, `integration_sync_run_v1`, `canonical_sync_snapshot_v1` — ERP
- `erp_discovery_session_v1` — ERP API discovery
- `billing_plan_v1`, `billing_subscription_v1`, `usage_meter_v1` — billing
- `llm_call_log_v1`, `llm_routing_policy_v1` — LLM governance
- `excel_connection_v1`, `excel_sync_event_v1` — Excel live links
- `memo_pack_v1` — generated memo documents

## Coding Standards
- Python 3.12+, FastAPI, Pydantic v2 for API
- TypeScript, Next.js 14+ (App Router) for web UI
- All API responses use standard envelope: `{ "data": ..., "meta": { "request_id": "...", "timestamp": "..." } }`
- All IDs are prefixed strings: `t_` (tenant), `u_` (user), `ds_` (draft session), `bl_` (baseline), `cs_` (changeset), `run_` (run), `vc_` (venture)
- Dates are ISO 8601 with timezone (UTC)
- Money values stored as integers (cents) with currency code alongside
