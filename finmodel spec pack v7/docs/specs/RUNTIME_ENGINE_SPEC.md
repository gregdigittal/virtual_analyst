# Runtime Engine Specification
**Date:** 2026-02-08

## Overview
The runtime engine is a pure, deterministic function:
```
f(model_config, scenario_overrides, mc_samples?) → statements + kpis + artifacts
```
It has no LLM dependency, no network calls, and no side effects. Given the same inputs, it always produces the same outputs.

## Execution Pipeline

```
model_config_v1
      │
      ▼
┌─────────────────┐
│ 1. Parse Config  │  Validate + extract assumptions, blueprint, distributions
└────────┬────────┘
         ▼
┌─────────────────┐
│ 2. Apply Scen.  │  Merge scenario overrides into assumptions
└────────┬────────┘
         ▼
┌─────────────────┐
│ 3. Build Graph   │  DAG from driver_blueprint (nodes, edges, formulas)
└────────┬────────┘
         ▼
┌─────────────────┐
│ 4. Topo Sort     │  Determine execution order
└────────┬────────┘
         ▼
┌─────────────────┐
│ 5. Time Loop     │  For each period (month): evaluate all nodes in order
└────────┬────────┘
         ▼
┌─────────────────┐
│ 6. Statements    │  IS → BS → CF (linked, iterative for plug)
└────────┬────────┘
         ▼
┌─────────────────┐
│ 7. KPIs          │  Derived ratios and metrics
└────────┬────────┘
         ▼
     outputs
```

## Step 1: Parse Config
Extract from model_config_v1:
- `metadata`: horizon_months, start_date, resolution (monthly|annual), currency
- `assumptions`: all assumption categories
- `driver_blueprint`: nodes, edges, formulas
- `distributions`: stochastic config per driver (used only in MC mode)
- `scenarios`: named override sets

## Step 2: Apply Scenario Overrides
If a scenario_id is provided:
1. Find the scenario in `model_config.scenarios`
2. For each override in the scenario:
   - Locate the target driver by `ref`
   - Apply the override (absolute value replacement, or multiplier on base value)
3. Return modified assumptions (original is not mutated)

Override types:
- `"field": "value"` — replace the driver's base value
- `"field": "multiplier"` — multiply the driver's base value

## Step 3: Build Graph
Parse `driver_blueprint`:
- **Nodes** have types: `driver` (input), `formula` (computed), `output` (terminal)
- **Edges** define dependencies: `{ from, to }` means `from` must be computed before `to`
- **Formulas** define how formula/output nodes are computed: `{ formula_id, output_node_id, expression, inputs }`

Build a directed graph. All `driver` nodes are leaves (no incoming edges). All `output` nodes are sinks.

## Step 4: Topological Sort
Topological sort the graph. If a cycle is detected, raise `GraphCycleError` with the cycle path. The sorted order determines the evaluation sequence.

## Step 5: Time Loop
For each period `t` in `[0, horizon_months)`:

```python
for node_id in topo_order:
    node = graph.nodes[node_id]
    if node.type == "driver":
        # Look up value from assumptions
        # Handle time-varying drivers:
        #   - Ramp schedules: interpolate between steps
        #   - Seasonal patterns: apply seasonal factor for month
        #   - Constant: same value every period
        values[node_id][t] = resolve_driver(node, assumptions, t)

    elif node.type in ("formula", "output"):
        formula = graph.formulas[node.formula_id]
        # Evaluate expression with input values at time t
        input_vals = { name: values[ref][t] for name, ref in formula.input_map }
        values[node_id][t] = evaluate(formula.expression, input_vals)
```

### Expression Evaluation
Formulas use a restricted expression language (NOT arbitrary Python eval):
- Arithmetic: `+`, `-`, `*`, `/`
- Functions: `min()`, `max()`, `clamp()`, `if_else(condition, true_val, false_val)`
- References: variable names that map to input nodes
- No loops, no imports, no function definitions

Implementation: parse expression into AST at graph build time; evaluate AST with variable substitution at runtime. Use a safe evaluator (e.g., `asteval` library or a custom recursive descent parser).

### Time-Varying Drivers
Drivers can specify value schedules:
```json
{
  "ref": "drv:utilization",
  "value_type": "ramp",
  "schedule": [
    { "month": 0, "value": 0.3 },
    { "month": 6, "value": 0.6 },
    { "month": 12, "value": 0.75 },
    { "month": 24, "value": 0.85 }
  ],
  "interpolation": "linear"
}
```
Between schedule points, interpolate linearly (or step, if specified). Before the first point, use the first value. After the last point, hold the last value.

## Step 6: Three-Statement Generator

### Income Statement (IS)
Computed per period from engine outputs:

| Line Item | Source |
|---|---|
| Revenue | Sum of all revenue output nodes |
| COGS | Sum of variable cost nodes + allocated fixed production costs |
| **Gross Profit** | Revenue - COGS |
| Operating Expenses | Sum of opex nodes (SG&A, R&D, other) |
| **EBITDA** | Gross Profit - Operating Expenses |
| Depreciation & Amortization | From capex schedule (straight-line over useful life) |
| **EBIT** | EBITDA - D&A |
| Interest Expense | Debt balance × interest rate |
| **EBT** | EBIT - Interest |
| Tax | EBT × tax_rate (floor at 0 for losses; carry forward optional) |
| **Net Income** | EBT - Tax |

### Balance Sheet (BS)
Computed per period end:

**Assets:**
| Line Item | Calculation |
|---|---|
| Cash | **Plug** — derived from CF ending balance |
| Accounts Receivable | Revenue × (ar_days / 30) |
| Inventory | COGS × (inv_days / 30) |
| **Total Current Assets** | Cash + AR + Inventory |
| PP&E (Gross) | Cumulative capex |
| Accumulated Depreciation | Cumulative D&A |
| **PP&E (Net)** | Gross - Accum Depr |
| **Total Assets** | Current + PP&E Net + Other |

**Liabilities & Equity:**
| Line Item | Calculation |
|---|---|
| Accounts Payable | COGS × (ap_days / 30) |
| Short-term Debt | Per funding schedule |
| **Total Current Liabilities** | AP + ST Debt |
| Long-term Debt | Per funding schedule |
| **Total Liabilities** | Current + LT |
| Share Capital | Initial equity + raises |
| Retained Earnings | Prior RE + Net Income - Dividends |
| **Total Equity** | Share Capital + RE |
| **Total L&E** | Liabilities + Equity |

### Cash Plug Mechanism
The BS must balance. Cash is the plug:
1. Compute all BS items except Cash
2. Cash = Total L&E - (Total Assets excluding Cash)
3. If Cash goes negative beyond a threshold, flag an integrity warning (funding gap)

Alternative plug: revolving credit facility (if configured in funding assumptions). In that case, the revolver draws to fill the gap and Cash floors at a minimum balance.

### Cash Flow Statement (CF)
| Section | Items |
|---|---|
| **Operating** | Net Income + D&A + ΔAR + ΔInventory + ΔAP |
| **Investing** | -Capex |
| **Financing** | +Debt draws - Debt repayments + Equity raises - Dividends |
| **Net CF** | Operating + Investing + Financing |
| **Opening Cash** | Prior period closing cash (or initial cash for t=0) |
| **Closing Cash** | Opening + Net CF |

Validation: CF Closing Cash must equal BS Cash for every period.

## Step 7: KPI Calculator
Derived from statements:

| KPI | Formula |
|---|---|
| Gross Margin % | Gross Profit / Revenue |
| EBITDA Margin % | EBITDA / Revenue |
| Net Margin % | Net Income / Revenue |
| Revenue Growth % | (Revenue[t] - Revenue[t-1]) / Revenue[t-1] |
| Current Ratio | Current Assets / Current Liabilities |
| Debt/Equity | Total Debt / Total Equity |
| DSCR | EBITDA / (Interest + Principal Repayments) |
| ROE | Net Income / Avg Equity |
| FCF | Operating CF - Capex |
| Cash Conversion Cycle | AR Days + Inventory Days - AP Days |

## Monte Carlo Wrapper
When mc_enabled=true:
```python
results = []
rng = np.random.default_rng(seed)
for sim in range(num_simulations):
    # Sample stochastic drivers
    sampled_assumptions = deep_copy(assumptions)
    for dist in distributions:
        sampled_value = sample(dist, rng)
        set_at_path(sampled_assumptions, dist.ref, sampled_value)

    # Run deterministic engine with sampled values
    sim_output = run_engine(model_config, sampled_assumptions)
    results.append(sim_output)

# Aggregate across simulations
percentiles = compute_percentiles(results, [5, 10, 25, 50, 75, 90, 95])
```

## Output Artifacts
A completed run produces these artifacts (stored in Supabase Storage):
1. `run_config.json` — the exact inputs used (model_config + overrides + MC params)
2. `statements.json` — IS, BS, CF per period
3. `kpis.json` — all KPIs per period
4. `mc_results.json` (if MC) — percentile outputs
5. `valuation.json` (if valuation configured) — DCF + multiples results

## Performance Targets
- Single deterministic run (12 months): < 100ms
- 1,000 MC simulations (12 months): < 10 seconds
- 10,000 MC simulations (12 months): < 60 seconds

Use numpy vectorization for MC inner loop where possible.
