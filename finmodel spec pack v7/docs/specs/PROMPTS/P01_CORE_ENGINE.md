# Phase 1 Prompt — Core Model Engine

## Context
You are building the core model engine for FinModel, a deterministic financial forecasting platform. This phase creates the foundation: schema validation, calculation graph, time-series engine, three-statement generator, and basic API + UI.

## Pre-requisites
- Read: `CURSOR_MASTER_PROMPT.md` (hard constraints)
- Read: `RUNTIME_ENGINE_SPEC.md` (engine design)
- Read: `AUTH_AND_TENANCY.md` (auth approach)
- Read: `FRONTEND_STACK.md` (Next.js setup)
- Schema: `ARTIFACT_SCHEMAS/ARTIFACT_MODEL_CONFIG_SCHEMA.json`
- Template: `TEMPLATES/default_catalog.json`

## Tasks (execute in order)

### 1. Project Setup
```
- Initialize Python project: pyproject.toml with FastAPI, Pydantic v2, supabase-py, numpy, pytest
- Initialize Next.js 14 project in apps/web/ with TypeScript, Tailwind, shadcn/ui
- Create .env.example with: SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY, DATABASE_URL
- Apply migration: apps/api/app/db/migrations/0001_init.sql
- Apply migration: apps/api/app/db/migrations/0002_functions.sql
```

### 2. Pydantic Models
```
File: shared/fm_shared/model/schemas.py

Create Pydantic v2 models that mirror ARTIFACT_MODEL_CONFIG_SCHEMA.json exactly:
- ModelConfig (root)
- Metadata, Assumptions, RevenueStream, DriverValue, CostStructure, CostItem
- WorkingCapital, Capex, Funding
- DriverBlueprint, BlueprintNode, BlueprintEdge, BlueprintFormula
- DistributionConfig, Scenario, ScenarioOverride
- EvidenceEntry, IntegrityBlock, IntegrityCheck

All fields must match the JSON Schema types, enums, and constraints.
Use Pydantic validators for cross-field checks (e.g., schedule required when value_type=ramp).
```

### 3. Artifact Storage
```
File: shared/fm_shared/storage/artifact_store.py

Interface:
  save_artifact(tenant_id, artifact_type, artifact_id, data: dict) -> str (storage_path)
  load_artifact(tenant_id, artifact_type, artifact_id) -> dict
  list_artifacts(tenant_id, artifact_type) -> list[str]

Backend: Supabase Storage
  Bucket: tenant-{tenant_id}
  Path: {artifact_type}/{artifact_id}.json

On save: validate data against the artifact's JSON Schema (load from ARTIFACT_SCHEMAS/).
On load: parse JSON, return dict.
```

### 4. Calculation Graph
```
File: shared/fm_shared/model/graph.py

Classes:
  CalcGraph:
    - from_blueprint(blueprint: DriverBlueprint) -> CalcGraph
    - topo_sort() -> list[str]  # node_ids in execution order
    - detect_cycles() -> list[list[str]] | None

Use adjacency list representation. Kahn's algorithm for topological sort.
Raise GraphCycleError with cycle path if cycles detected.
```

### 5. Expression Evaluator
```
File: shared/fm_shared/model/evaluator.py

Safe arithmetic expression evaluator. NO eval() or exec().
Approach: parse expression string into AST, then evaluate with variable bindings.

Supported:
  - Arithmetic: +, -, *, /
  - Parentheses
  - Functions: min(a, b), max(a, b), clamp(x, lo, hi), if_else(cond, true_val, false_val)
  - Variable names (alphanumeric + underscore)

parse(expression: str) -> AST
evaluate(ast: AST, variables: dict[str, float]) -> float
```

### 6. Time-Series Engine
```
File: shared/fm_shared/model/engine.py

def run_engine(config: ModelConfig, scenario_overrides: list[ScenarioOverride] | None = None) -> EngineOutput:
    # 1. Apply scenario overrides to assumptions (deep copy first)
    # 2. Build calc graph from driver_blueprint
    # 3. Topo sort
    # 4. For each period t in [0, horizon_months):
    #      For each node in topo order:
    #        If driver: resolve value at time t (constant/ramp/seasonal/step)
    #        If formula/output: evaluate expression with input values at t
    # 5. Return time-series dict: { node_id: [value_at_t0, value_at_t1, ...] }

EngineOutput:
  time_series: dict[str, list[float]]
  periods: list[str]  # ISO date strings for each period
  resolution: str  # "monthly" or "annual"

Driver resolution logic per value_type:
  constant: return value every period
  ramp: interpolate between schedule points (linear or step)
  seasonal: base_value * seasonal_factors[month_index]
  step: return schedule value, holding until next step
```

### 7. Three-Statement Generator
```
File: shared/fm_shared/model/statements.py

def generate_statements(config: ModelConfig, engine_output: EngineOutput) -> Statements:

Follow RUNTIME_ENGINE_SPEC.md exactly:
  - Income Statement: Revenue through Net Income
  - Balance Sheet: Assets = Liabilities + Equity (cash plug)
  - Cash Flow: Operating + Investing + Financing
  
Validate:
  - BS balances every period (tolerance < 0.01)
  - CF closing cash == BS cash every period
  
If validation fails, raise StatementImbalanceError with details.

Statements dataclass:
  income_statement: list[dict]  # one dict per period
  balance_sheet: list[dict]
  cash_flow: list[dict]
```

### 8. KPI Calculator
```
File: shared/fm_shared/model/kpis.py

def calculate_kpis(statements: Statements) -> list[dict]:
  Per RUNTIME_ENGINE_SPEC.md: gross_margin_pct, ebitda_margin_pct, net_margin_pct,
  revenue_growth_pct, current_ratio, debt_equity, dscr, roe, fcf, cash_conversion_cycle
```

### 9. FastAPI Application
```
File: apps/api/app/main.py

- FastAPI app with CORS, request_id middleware, error handler
- Response envelope: { "data": ..., "meta": { "request_id": "...", "timestamp": "..." } }
- Health check: GET /api/v1/health

File: apps/api/app/routers/baselines.py
- POST /api/v1/baselines — body is model_config JSON; validate, store, insert into DB
- GET /api/v1/baselines — list for tenant (from JWT)
- GET /api/v1/baselines/{baseline_id}
- PATCH /api/v1/baselines/{baseline_id} — update status

File: apps/api/app/routers/runs.py
- POST /api/v1/runs — { baseline_id, scenario_id? }; queue run
- GET /api/v1/runs/{run_id} — status + metadata
- GET /api/v1/runs/{run_id}/statements — IS/BS/CF
- GET /api/v1/runs/{run_id}/kpis

Run execution: load baseline model_config → run_engine → generate_statements → calculate_kpis → store artifacts → update status

Auth: use Supabase JWT middleware. Set tenant_id from JWT claims. See AUTH_AND_TENANCY.md.
```

### 10. Next.js Frontend
```
Directory: apps/web/

Setup:
- Supabase Auth with @supabase/ssr
- Protected route middleware
- Tailwind + shadcn/ui (Button, Card, Table, Dialog components)
- TanStack Query for API state

Pages:
- /login — email/password form
- /dashboard — redirect here after login; show baseline list
- /baselines — list baselines (name, status, created_at, link to runs)
- /runs/[id] — tabbed view: Statements tab with IS/BS/CF tables
  - Months as columns, line items as rows
  - Format numbers as currency (comma separated, 2 decimals)
  - Negative values in red

Layout: sidebar with nav links (Dashboard, Baselines, Runs) + top bar with user info + logout
```

### 11. Tests
Write tests per TESTING_STRATEGY.md Phase 1 section. At minimum:
- `tests/unit/engine/test_graph_builder.py`
- `tests/unit/engine/test_expression_evaluator.py`
- `tests/unit/engine/test_income_statement.py` (manufacturing template with known inputs)
- `tests/unit/engine/test_balance_sheet.py` (BS balance check)
- `tests/unit/engine/test_cash_flow.py` (CF ↔ BS reconciliation)
- `tests/unit/schemas/test_schema_validation.py`
- `tests/integration/test_baseline_crud.py`
- `tests/integration/test_run_lifecycle.py`

## Verification
After completing all tasks, verify the Phase 1 gate criteria from BUILD_PLAN.md:
1. Load manufacturing_discrete template
2. Create model_config with sample inputs
3. Run engine → 12-month IS/BS/CF
4. BS balances every month
5. Same inputs → identical outputs
6. All tests pass
7. API returns correct envelope
8. Web UI: login → baseline list → run results
