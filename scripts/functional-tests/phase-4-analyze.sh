#!/usr/bin/env bash
# phase-4-analyze.sh — Ch14-21: Runs, MC, Valuation, Budgets, Covenants, Benchmarking, Compare, Ventures
# Manual refs: docs/user-manual/14-runs.md through 21-ventures.md
set -euo pipefail
source "$(dirname "$0")/lib/test-helpers.sh"

log_phase "Phase 4: Analyze (Ch14-21)"

# ── Ch14: Runs ─────────────────────────────────────────────────

run_tdd_test "ch14-runs-list" \
"SPECIFICATION (from docs/user-manual/14-runs.md):
The Runs page shows a list of all executed model runs. Each run
displays its label, source draft, execution date, status (success
or error), and run mode (Deterministic or Monte Carlo).

TASK:
1. Log in and navigate to /runs
2. Assert the page heading contains 'Runs'
3. Assert either run entries are listed OR an empty state message
4. If runs exist (from seeded data), assert each shows a status
5. Save to apps/web/e2e/functional/ch14-runs-list.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch14-run-detail-statements" \
"SPECIFICATION (from docs/user-manual/14-runs.md):
Drilling into a run shows financial statements: Income Statement,
Balance Sheet, and Cash Flow Statement. Each statement is displayed
as a table with line items and period columns.

TASK:
1. Log in and navigate to /runs
2. Click on a run (use seeded run if available)
3. Assert financial statement tabs or sections are visible
4. Assert at least one of: Income Statement, Balance Sheet, Cash Flow
5. Save to apps/web/e2e/functional/ch14-run-detail-statements.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch14-run-kpis" \
"SPECIFICATION (from docs/user-manual/14-runs.md):
The run detail view includes a KPI dashboard showing key performance
indicators derived from the financial statements. KPIs include
metrics like revenue growth, gross margin, EBITDA margin, etc.

TASK:
1. Log in, navigate to /runs, open a run
2. Assert a KPI section or dashboard tab is visible
3. Assert at least one KPI metric is displayed with a value
4. Save to apps/web/e2e/functional/ch14-run-kpis.spec.ts
5. Run and report RED or GREEN"

run_tdd_test "ch14-create-run" \
"SPECIFICATION (from docs/user-manual/14-runs.md):
To create a new run, users select a draft, choose the run mode
(Deterministic or Monte Carlo), and optionally set iterations and
confidence intervals for Monte Carlo mode. Clicking Execute starts
the run.

TASK:
1. Log in and navigate to /runs
2. Click a 'Create Run' or 'New Run' button
3. Assert draft selection is available
4. Assert mode selection (Deterministic / Monte Carlo) exists
5. Assert an 'Execute' or 'Run' button is visible
6. Save to apps/web/e2e/functional/ch14-create-run.spec.ts
7. Run and report RED or GREEN"

# ── Ch15: Monte Carlo and Sensitivity ──────────────────────────

run_tdd_test "ch15-monte-carlo-charts" \
"SPECIFICATION (from docs/user-manual/15-monte-carlo-and-sensitivity.md):
For Monte Carlo runs, the results include fan charts showing
probability distributions, confidence intervals, and percentile
bands for key financial metrics. Charts are interactive with hover
tooltips.

TASK:
1. Log in, navigate to /runs, open a run that used Monte Carlo mode
2. Assert chart elements are visible (canvas, SVG, or chart containers)
3. Assert Monte Carlo or probability distribution labels appear
4. If no MC run exists, assert the page shows deterministic results only
5. Save to apps/web/e2e/functional/ch15-monte-carlo-charts.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch15-sensitivity-analysis" \
"SPECIFICATION (from docs/user-manual/15-monte-carlo-and-sensitivity.md):
Sensitivity analysis shows tornado diagrams and heatmaps revealing
which input assumptions have the greatest impact on key outputs.
Users can toggle between different output metrics.

TASK:
1. Log in, navigate to /runs, open a run
2. Look for a Sensitivity tab or section
3. Assert tornado diagram or heatmap chart elements are visible
4. If no sensitivity data exists, assert appropriate empty state
5. Save to apps/web/e2e/functional/ch15-sensitivity-analysis.spec.ts
6. Run and report RED or GREEN"

# ── Ch16: Valuation ────────────────────────────────────────────

run_tdd_test "ch16-valuation-outputs" \
"SPECIFICATION (from docs/user-manual/16-valuation.md):
The valuation section of a run shows DCF (Discounted Cash Flow)
and multiples-based valuations. It displays enterprise value,
equity value, implied share price, and key assumptions like
WACC and terminal growth rate.

TASK:
1. Log in, navigate to /runs, open a run
2. Look for a Valuation tab or section
3. Assert valuation metrics are visible (enterprise value, equity value, or WACC)
4. If no valuation data, assert the section indicates it's unavailable
5. Save to apps/web/e2e/functional/ch16-valuation-outputs.spec.ts
6. Run and report RED or GREEN"

# ── Ch17: Budgets ──────────────────────────────────────────────

run_tdd_test "ch17-budgets-list" \
"SPECIFICATION (from docs/user-manual/17-budgets.md):
The Budgets page shows all budgets with their name, period type
(monthly, quarterly, annual), status, and variance summary.
A 'Create Budget' button is available.

TASK:
1. Log in and navigate to /budgets
2. Assert the page heading contains 'Budgets'
3. Assert a 'Create Budget' button is visible
4. Assert either budget entries or an empty state is shown
5. Save to apps/web/e2e/functional/ch17-budgets-list.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch17-budget-variance" \
"SPECIFICATION (from docs/user-manual/17-budgets.md):
Opening a budget shows variance analysis comparing budget
projections to actual values. Variance charts display
period-by-period comparisons with favorable/unfavorable
indicators.

TASK:
1. Log in, navigate to /budgets, open a budget (seeded data)
2. Assert variance analysis elements are visible
3. Assert charts or tables comparing budget vs actual exist
4. If no budget exists, assert empty state
5. Save to apps/web/e2e/functional/ch17-budget-variance.spec.ts
6. Run and report RED or GREEN"

# ── Ch18: Covenants ────────────────────────────────────────────

run_tdd_test "ch18-covenants-page" \
"SPECIFICATION (from docs/user-manual/18-covenants.md):
The Covenants page monitors debt covenant compliance. Each covenant
shows its metric (e.g., Debt/EBITDA), threshold value, current value,
and status (compliant, warning, or breach). A 'Create Covenant'
button allows adding new monitors.

TASK:
1. Log in and navigate to /covenants
2. Assert the page heading contains 'Covenants'
3. Assert a 'Create Covenant' or 'Add Monitor' button is visible
4. Assert either covenant monitors or an empty state is shown
5. Save to apps/web/e2e/functional/ch18-covenants-page.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch18-covenant-alerts" \
"SPECIFICATION (from docs/user-manual/18-covenants.md):
Covenants approaching or breaching thresholds trigger visual alerts.
Warning status shows when a metric is within a configurable margin
of the threshold. Breach status shows when the threshold is exceeded.
Color coding: green (compliant), yellow (warning), red (breach).

TASK:
1. Log in, navigate to /covenants
2. If covenants exist, assert status indicators with color coding are visible
3. Assert threshold and current value labels are present
4. Save to apps/web/e2e/functional/ch18-covenant-alerts.spec.ts
5. Run and report RED or GREEN"

# ── Ch19: Benchmarking ─────────────────────────────────────────

run_tdd_test "ch19-benchmarking-page" \
"SPECIFICATION (from docs/user-manual/19-benchmarking.md):
The Benchmarking page lets users compare their financial metrics
against anonymized industry peers. Users can opt in to share data
and view percentile rankings for key metrics like revenue growth,
margins, and efficiency ratios.

TASK:
1. Log in and navigate to /benchmark
2. Assert the page heading contains 'Benchmark' or 'Peer'
3. Assert industry comparison controls or charts are visible
4. Assert an opt-in toggle or data sharing notice exists
5. Save to apps/web/e2e/functional/ch19-benchmarking-page.spec.ts
6. Run and report RED or GREEN"

# ── Ch20: Entity Comparison ────────────────────────────────────

run_tdd_test "ch20-compare-page" \
"SPECIFICATION (from docs/user-manual/20-entity-comparison.md):
The Compare page provides side-by-side comparison of entities or
runs. Users select two or more items to compare and view KPI
differences, variance drivers, and financial statement deltas
in a tabular format.

TASK:
1. Log in and navigate to /compare
2. Assert the page heading contains 'Compare' or 'Comparison'
3. Assert entity/run selection controls are visible
4. Assert a comparison table or chart area exists
5. Save to apps/web/e2e/functional/ch20-compare-page.spec.ts
6. Run and report RED or GREEN"

# ── Ch21: Ventures ─────────────────────────────────────────────

run_tdd_test "ch21-ventures-page" \
"SPECIFICATION (from docs/user-manual/21-ventures.md):
The Ventures page provides a guided questionnaire-to-model wizard.
Users answer questions about their business (industry, stage,
revenue model, team size) and AI generates initial financial
assumptions as a draft.

TASK:
1. Log in and navigate to /ventures
2. Assert the page heading contains 'Ventures' or 'Startup'
3. Assert a 'Start' or 'Begin Questionnaire' button is visible
4. Assert the wizard interface or question form is displayed
5. Save to apps/web/e2e/functional/ch21-ventures-page.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch21-ventures-questionnaire" \
"SPECIFICATION (from docs/user-manual/21-ventures.md):
The venture questionnaire walks through questions about industry,
business model, revenue projections, and key assumptions. After
completing the questionnaire, AI generates a draft with populated
financial assumptions.

TASK:
1. Log in and navigate to /ventures
2. Click to start the questionnaire
3. Assert question fields or selection options appear
4. Assert a progress indicator shows questionnaire steps
5. Save to apps/web/e2e/functional/ch21-ventures-questionnaire.spec.ts
6. Run and report RED or GREEN"

log_phase_complete "Phase 4"
