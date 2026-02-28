#!/usr/bin/env bash
# phase-3-configure.sh — Ch10-13: Baselines, Drafts, Scenarios, Changesets
# Manual refs: docs/user-manual/10-baselines.md through 13-changesets.md
set -euo pipefail
source "$(dirname "$0")/lib/test-helpers.sh"

log_phase "Phase 3: Configure (Ch10-13)"

# ── Ch10: Baselines ───────────────────────────────────────────

run_tdd_test "ch10-baselines-list" \
"SPECIFICATION (from docs/user-manual/10-baselines.md):
The Baselines page displays a searchable, paginated list of all
baselines. Each baseline shows its label, version number (v1, v2, ...),
status (Active or Archived), and creation date. A search bar at
the top filters baselines by name.

TASK:
1. Log in and navigate to /baselines
2. Assert the page heading contains 'Baselines'
3. Assert a search/filter input is visible
4. Assert either baseline cards/rows are displayed OR an empty state
5. If baselines exist, assert each shows a label and status
6. Save to apps/web/e2e/functional/ch10-baselines-list.spec.ts
7. Run and report RED or GREEN"

run_tdd_test "ch10-baseline-detail" \
"SPECIFICATION (from docs/user-manual/10-baselines.md):
Clicking a baseline opens its detail view showing the full
configuration: line items, assumptions, version history, and
action buttons to Create Draft, Create Changeset, or Archive.

TASK:
1. Log in and navigate to /baselines
2. If a baseline exists (from seeded data), click on it
3. Assert the detail view shows the baseline label
4. Assert action buttons like 'Create Draft' are visible
5. If no baselines exist, assert the empty state
6. Save to apps/web/e2e/functional/ch10-baseline-detail.spec.ts
7. Run and report RED or GREEN"

run_tdd_test "ch10-baseline-archive" \
"SPECIFICATION (from docs/user-manual/10-baselines.md):
Archiving a baseline changes its status to Archived and makes
it read-only. An Archive button is available in the baseline
detail view. Archived baselines can be restored to Active status.

TASK:
1. Log in and navigate to /baselines
2. Open a baseline detail view
3. Assert an 'Archive' button or action is visible
4. Save to apps/web/e2e/functional/ch10-baseline-archive.spec.ts
5. Run and report RED or GREEN"

# ── Ch11: Drafts ──────────────────────────────────────────────

run_tdd_test "ch11-drafts-list" \
"SPECIFICATION (from docs/user-manual/11-drafts.md):
The Drafts page shows all working copies of baselines. Each draft
displays its label, source baseline, status, and last-modified
timestamp. Drafts persist across sessions.

TASK:
1. Log in and navigate to /drafts
2. Assert the page heading contains 'Drafts'
3. Assert either draft cards/rows are displayed OR an empty state
4. Save to apps/web/e2e/functional/ch11-drafts-list.spec.ts
5. Run and report RED or GREEN"

run_tdd_test "ch11-draft-editor" \
"SPECIFICATION (from docs/user-manual/11-drafts.md):
Opening a draft shows the editor workspace where users can adjust
revenue streams, cost structures, and CapEx items. The editor includes
an AI chat panel for suggestions. Changes can be accepted, rejected,
or refined through the AI assistant.

TASK:
1. Log in and navigate to /drafts
2. If a draft exists (from seeded data), click to open it
3. Assert the editor workspace is visible
4. Assert financial line items or assumption fields are shown
5. Assert an AI chat panel or assistant button is visible
6. Save to apps/web/e2e/functional/ch11-draft-editor.spec.ts
7. Run and report RED or GREEN"

run_tdd_test "ch11-draft-commit" \
"SPECIFICATION (from docs/user-manual/11-drafts.md):
When a draft passes integrity checks, the user can mark it as ready
and commit it to create a new baseline version. The Commit button
triggers validation checks (errors vs warnings) before proceeding.

TASK:
1. Log in, navigate to /drafts, open a draft
2. Assert a 'Commit' or 'Save as Baseline' button is visible
3. Assert integrity check indicators (errors/warnings) are shown
4. Save to apps/web/e2e/functional/ch11-draft-commit.spec.ts
5. Run and report RED or GREEN"

# ── Ch12: Scenarios ────────────────────────────────────────────

run_tdd_test "ch12-scenarios-page" \
"SPECIFICATION (from docs/user-manual/12-scenarios.md):
The Scenarios page lets users create alternative assumption sets
such as Best Case, Base Case, and Worst Case. Each scenario
defines overrides to baseline assumptions that can be compared
side by side.

TASK:
1. Log in and navigate to /scenarios
2. Assert the page heading contains 'Scenarios'
3. Assert a 'Create Scenario' button is visible
4. Assert either scenario cards or an empty state is shown
5. Save to apps/web/e2e/functional/ch12-scenarios-page.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch12-create-scenario" \
"SPECIFICATION (from docs/user-manual/12-scenarios.md):
Creating a scenario requires a name (e.g., 'Best Case'), an
optional description, and selecting which assumptions to override.
Scenarios are linked to a specific baseline.

TASK:
1. Log in and navigate to /scenarios
2. Click 'Create Scenario'
3. Assert a form with name and description fields appears
4. Assert assumption override controls are available
5. Save to apps/web/e2e/functional/ch12-create-scenario.spec.ts
6. Run and report RED or GREEN"

# ── Ch13: Changesets ───────────────────────────────────────────

run_tdd_test "ch13-changesets-page" \
"SPECIFICATION (from docs/user-manual/13-changesets.md):
The Changesets page shows immutable snapshots of targeted overrides.
Each changeset records what was changed, who changed it, and when.
Users can test changes with dry-runs before merging into a new
baseline version.

TASK:
1. Log in and navigate to /changesets
2. Assert the page heading contains 'Changesets' or 'Changes'
3. Assert either changeset entries or an empty state is shown
4. Save to apps/web/e2e/functional/ch13-changesets-page.spec.ts
5. Run and report RED or GREEN"

run_tdd_test "ch13-changeset-dry-run" \
"SPECIFICATION (from docs/user-manual/13-changesets.md):
Before merging a changeset, users can run a dry-run to preview
the impact. The dry-run shows which line items would change
and the resulting values without actually creating a new version.

TASK:
1. Log in and navigate to /changesets
2. If a changeset exists, assert a 'Dry Run' or 'Preview' button is visible
3. If no changesets exist, assert the empty state guides the user
4. Save to apps/web/e2e/functional/ch13-changeset-dry-run.spec.ts
5. Run and report RED or GREEN"

log_phase_complete "Phase 3"
