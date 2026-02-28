#!/usr/bin/env bash
# phase-2-setup.sh — Ch03-09: Marketplace, Import, Excel, AFS, Orgs
# Manual refs: docs/user-manual/03-marketplace.md through 09-org-structures.md
set -euo pipefail
source "$(dirname "$0")/lib/test-helpers.sh"

log_phase "Phase 2: Setup (Ch03-09)"

# ── Ch03: Marketplace ──────────────────────────────────────────

run_tdd_test "ch03-marketplace-loads" \
"SPECIFICATION (from docs/user-manual/03-marketplace.md):
The Marketplace page displays a grid of pre-built financial templates.
Each template card shows its name and a type badge. Templates are
displayed in a paginated grid, sorted alphabetically by default.

TASK:
1. Log in and navigate to /marketplace
2. Assert the page heading contains 'Marketplace' or 'Templates'
3. Assert at least one template card is visible
4. Assert each visible card shows a name
5. Save to apps/web/e2e/functional/ch03-marketplace-loads.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch03-marketplace-search" \
"SPECIFICATION (from docs/user-manual/03-marketplace.md):
The Marketplace has a search bar that filters templates by name
and industry. Users can type a search query to narrow the displayed
templates.

TASK:
1. Log in and navigate to /marketplace
2. Locate a search input field
3. Type a search query (e.g., 'SaaS' or 'retail')
4. Assert the template grid updates (fewer or filtered results)
5. Save to apps/web/e2e/functional/ch03-marketplace-search.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch03-marketplace-use-template" \
"SPECIFICATION (from docs/user-manual/03-marketplace.md):
Clicking 'Use Template' on a template card opens a dialog asking
for a label (1-255 characters) and fiscal year end date. After
filling these fields and confirming, a new baseline is created
and the user is redirected to the Baselines page.

TASK:
1. Log in and navigate to /marketplace
2. Click the 'Use Template' button on the first template card
3. Assert a dialog or form appears with label and fiscal year fields
4. Fill in a label (e.g., 'Test Baseline from Template')
5. Fill in a fiscal year (e.g., '2025-12-31')
6. Click the confirm/create button
7. Assert navigation to /baselines or a success message appears
8. Save to apps/web/e2e/functional/ch03-marketplace-use-template.spec.ts
9. Run and report RED or GREEN"

# ── Ch04: Data Import ──────────────────────────────────────────

run_tdd_test "ch04-import-page-loads" \
"SPECIFICATION (from docs/user-manual/04-data-import.md):
The Import Excel page shows a multi-step wizard with five stages:
Upload, Classify, Map, Review, and Create Draft. A stepper bar
at the top shows progress through these stages with green checkmarks
for completed steps.

TASK:
1. Log in and navigate to /excel-import
2. Assert the page heading contains 'Import' or 'Excel'
3. Assert a stepper/progress bar is visible showing the upload step
4. Assert a file upload area or button is visible
5. Save to apps/web/e2e/functional/ch04-import-page-loads.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch04-import-upload-validation" \
"SPECIFICATION (from docs/user-manual/04-data-import.md):
The upload step accepts .xlsx files. If the user tries to proceed
without selecting a file, a validation message appears. The system
supports drag-and-drop and click-to-browse upload methods.

TASK:
1. Log in and navigate to /excel-import
2. Assert a file upload zone is visible (drag-and-drop area or file input)
3. Try clicking a 'Next' or 'Continue' button without uploading
4. Assert a validation message or error appears indicating a file is required
5. Save to apps/web/e2e/functional/ch04-import-upload-validation.spec.ts
6. Run and report RED or GREEN"

# ── Ch05: Excel Live Connections ───────────────────────────────

run_tdd_test "ch05-connections-page-loads" \
"SPECIFICATION (from docs/user-manual/05-excel-connections.md):
The Excel Connections page lists all existing connections. Each
connection shows its name, target (run or baseline), mode (read-only
or read-write), and last sync timestamp. A 'Create Connection'
button is prominently displayed.

TASK:
1. Log in and navigate to /excel-connections
2. Assert the page heading contains 'Connection' or 'Excel'
3. Assert a 'Create Connection' or 'New Connection' button is visible
4. Assert either a list of connections is shown OR an empty state message
5. Save to apps/web/e2e/functional/ch05-connections-page-loads.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch05-create-connection-form" \
"SPECIFICATION (from docs/user-manual/05-excel-connections.md):
Creating a new connection requires: a connection name, selecting a
target (run ID or baseline ID), choosing a mode (read-only or
read-write), and defining cell bindings. The form validates that
all required fields are filled.

TASK:
1. Log in and navigate to /excel-connections
2. Click the 'Create Connection' button
3. Assert a form or dialog appears with fields for name and target selection
4. Assert mode selection (read-only / read-write) is available
5. Save to apps/web/e2e/functional/ch05-create-connection-form.spec.ts
6. Run and report RED or GREEN"

# ── Ch06: AFS Module ───────────────────────────────────────────

run_tdd_test "ch06-afs-dashboard-loads" \
"SPECIFICATION (from docs/user-manual/06-afs-module.md):
The AFS (Annual Financial Statements) page shows a dashboard with
a list of engagements. Each engagement card displays its name,
framework (IFRS or GAAP), status, and creation date. A 'Create
Engagement' button is available.

TASK:
1. Log in and navigate to /afs
2. Assert the page heading contains 'AFS' or 'Annual Financial Statements'
3. Assert a 'Create Engagement' or 'New Engagement' button is visible
4. Assert either engagement cards are displayed OR an empty state
5. Save to apps/web/e2e/functional/ch06-afs-dashboard-loads.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch06-afs-create-engagement" \
"SPECIFICATION (from docs/user-manual/06-afs-module.md):
Creating an engagement opens a setup wizard. The user provides
an engagement name, selects a framework (IFRS or GAAP), sets the
reporting period, and optionally uploads a trial balance.

TASK:
1. Log in and navigate to /afs
2. Click the 'Create Engagement' button
3. Assert a wizard or form appears
4. Assert fields for engagement name and framework selection exist
5. Save to apps/web/e2e/functional/ch06-afs-create-engagement.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch06-afs-section-editor" \
"SPECIFICATION (from docs/user-manual/06-afs-module.md):
Once an engagement is created, the section editor shows all required
disclosure sections. Each section can be AI-drafted, manually edited,
validated, and locked. The editor shows section status (draft, reviewed,
locked) with visual indicators.

TASK:
1. Log in and navigate to /afs (use a seeded engagement if available)
2. If an engagement exists, click into it to open the section editor
3. Assert section cards or a section list is visible
4. Assert each section shows a status indicator
5. If no engagement exists, assert the empty state prompts creation
6. Save to apps/web/e2e/functional/ch06-afs-section-editor.spec.ts
7. Run and report RED or GREEN"

# ── Ch07: AFS Review and Tax ───────────────────────────────────

run_tdd_test "ch07-afs-review-page" \
"SPECIFICATION (from docs/user-manual/07-afs-review-and-tax.md):
The AFS review page provides a three-stage review workflow: Preparer
Review, Manager Review, and Partner Sign-off. Each stage shows the
engagement's sections with their review status and allows reviewers
to approve, request changes, or reject sections.

TASK:
1. Log in and navigate to /afs/review (or /afs with review tab)
2. Assert the review workflow stages are visible
3. Assert section review status indicators are shown
4. Save to apps/web/e2e/functional/ch07-afs-review-page.spec.ts
5. Run and report RED or GREEN"

run_tdd_test "ch07-afs-tax-computation" \
"SPECIFICATION (from docs/user-manual/07-afs-review-and-tax.md):
The tax computation tab allows users to run tax calculations based
on the engagement data. AI-generated tax notes can be produced for
each applicable section. Tax computation results show current tax,
deferred tax, and effective tax rate.

TASK:
1. Log in and navigate to the tax section of AFS
2. Assert tax computation controls or results are visible
3. Assert current tax, deferred tax, or effective rate labels exist
4. Save to apps/web/e2e/functional/ch07-afs-tax-computation.spec.ts
5. Run and report RED or GREEN"

# ── Ch08: AFS Consolidation and Output ─────────────────────────

run_tdd_test "ch08-afs-consolidation" \
"SPECIFICATION (from docs/user-manual/08-afs-consolidation-and-output.md):
The consolidation page allows users to combine multiple entity
engagements into a consolidated set of financial statements. Users
select child entities, define elimination entries, and generate
consolidated trial balances.

TASK:
1. Log in and navigate to /afs/consolidation
2. Assert the consolidation interface is visible
3. Assert entity selection or consolidation controls exist
4. Save to apps/web/e2e/functional/ch08-afs-consolidation.spec.ts
5. Run and report RED or GREEN"

run_tdd_test "ch08-afs-output-generation" \
"SPECIFICATION (from docs/user-manual/08-afs-consolidation-and-output.md):
The output page lets users generate final AFS documents in three
formats: PDF, DOCX, and iXBRL. Users select the output format,
choose which sections to include, and click Generate. The system
produces the document and provides a download link.

TASK:
1. Log in and navigate to /afs/output
2. Assert format selection options (PDF, DOCX, iXBRL) are visible
3. Assert a 'Generate' button is visible
4. Save to apps/web/e2e/functional/ch08-afs-output-generation.spec.ts
5. Run and report RED or GREEN"

# ── Ch09: Org Structures ──────────────────────────────────────

run_tdd_test "ch09-org-structures-page" \
"SPECIFICATION (from docs/user-manual/09-org-structures.md):
The Org Structures page (Groups) lets users manage parent-subsidiary
hierarchies. Users can create entity groups, define ownership
percentages, and set consolidation rules. The page shows a tree
or list view of the organizational hierarchy.

TASK:
1. Log in and navigate to /org-structures
2. Assert the page heading contains 'Group' or 'Organization' or 'Structure'
3. Assert a 'Create Group' or 'Add Entity' button is visible
4. Assert either a hierarchy view or empty state is shown
5. Save to apps/web/e2e/functional/ch09-org-structures-page.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch09-create-org-group" \
"SPECIFICATION (from docs/user-manual/09-org-structures.md):
Creating an organization group requires a group name and at least
one entity. The form allows setting parent-child relationships
and ownership percentages for consolidation purposes.

TASK:
1. Log in and navigate to /org-structures
2. Click the 'Create Group' or 'New' button
3. Assert a form appears with a group name field
4. Assert entity selection or addition controls exist
5. Save to apps/web/e2e/functional/ch09-create-org-group.spec.ts
6. Run and report RED or GREEN"

log_phase_complete "Phase 2"
