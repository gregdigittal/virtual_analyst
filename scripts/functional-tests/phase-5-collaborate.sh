#!/usr/bin/env bash
# phase-5-collaborate.sh — Ch22-25: Workflows, Board Packs, Memos, Collaboration
# Manual refs: docs/user-manual/22-workflows-and-tasks.md through 25-collaboration.md
set -euo pipefail
source "$(dirname "$0")/lib/test-helpers.sh"

log_phase "Phase 5: Collaborate & Report (Ch22-25)"

# ── Ch22: Workflows and Tasks ──────────────────────────────────

run_tdd_test "ch22-workflows-page" \
"SPECIFICATION (from docs/user-manual/22-workflows-and-tasks.md):
The Workflows page lists available workflow templates and active
workflow instances. Each instance shows its name, bound entity
(budget, run, baseline, or draft), current stage, and assignee.
A 'Create Workflow' button starts a new workflow instance.

TASK:
1. Log in and navigate to /workflows
2. Assert the page heading contains 'Workflows'
3. Assert a 'Create Workflow' or 'New Workflow' button is visible
4. Assert either workflow instances or an empty state is shown
5. Save to apps/web/e2e/functional/ch22-workflows-page.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch22-workflow-create" \
"SPECIFICATION (from docs/user-manual/22-workflows-and-tasks.md):
Creating a workflow requires selecting a template and binding it
to an entity. The system automatically routes the first task to
the appropriate assignee based on the template's routing rules
(explicit user, team pool, or reports_to chain).

TASK:
1. Log in and navigate to /workflows
2. Click the 'Create Workflow' button
3. Assert template selection is available
4. Assert entity binding (baseline, run, etc.) controls exist
5. Save to apps/web/e2e/functional/ch22-workflow-create.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch22-inbox-tasks" \
"SPECIFICATION (from docs/user-manual/22-workflows-and-tasks.md):
The Inbox page shows all tasks assigned to the current user.
Each task shows its title, source workflow, priority, and due
date. Users can claim pool tasks on a first-come-first-served
basis.

TASK:
1. Log in and navigate to /inbox or /assignments
2. Assert the page shows a task list or inbox interface
3. Assert either assigned tasks or an empty inbox message is shown
4. Save to apps/web/e2e/functional/ch22-inbox-tasks.spec.ts
5. Run and report RED or GREEN"

# ── Ch23: Board Packs ─────────────────────────────────────────

run_tdd_test "ch23-board-packs-list" \
"SPECIFICATION (from docs/user-manual/23-board-packs.md):
The Board Packs page shows all created board packs with their
title, source run, status (draft, generating, ready, error),
and creation date. A 'Create Board Pack' button starts the builder.

TASK:
1. Log in and navigate to /board-packs
2. Assert the page heading contains 'Board Pack'
3. Assert a 'Create Board Pack' or 'New' button is visible
4. Assert either board pack entries or an empty state is shown
5. Save to apps/web/e2e/functional/ch23-board-packs-list.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch23-board-pack-builder" \
"SPECIFICATION (from docs/user-manual/23-board-packs.md):
The board pack builder lets users select a source run, choose
sections to include (Executive Summary, Income Statement, Balance
Sheet, Cash Flow, Budget Variance, KPI Dashboard, Scenario
Comparison, Strategic Commentary, Benchmark Analysis), and
arrange their order. AI generates narrative content for the
executive summary and strategic commentary.

TASK:
1. Log in, navigate to /board-packs, click Create
2. Assert run selection is available
3. Assert section checkboxes or toggles are visible
4. Assert section ordering controls (drag or arrows) exist
5. Save to apps/web/e2e/functional/ch23-board-pack-builder.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch23-board-pack-export" \
"SPECIFICATION (from docs/user-manual/23-board-packs.md):
Completed board packs can be exported to PDF, PPTX, or HTML format.
The export dialog shows format options and a Download or Generate
button. Branding customization (logo, colors, fonts) is available
in settings.

TASK:
1. Log in, navigate to /board-packs
2. If a board pack exists (seeded), click to open it
3. Assert export format options (PDF, PPTX, HTML) are visible
4. Assert a Download or Export button exists
5. Save to apps/web/e2e/functional/ch23-board-pack-export.spec.ts
6. Run and report RED or GREEN"

# ── Ch24: Memos and Documents ──────────────────────────────────

run_tdd_test "ch24-memos-page" \
"SPECIFICATION (from docs/user-manual/24-memos-and-documents.md):
The Memos page lets users create investment memos with structured
narratives and supporting data from model runs. A 'Create Memo'
button starts the memo editor.

TASK:
1. Log in and navigate to /memos
2. Assert the page heading contains 'Memo'
3. Assert a 'Create Memo' button is visible
4. Assert either existing memos or an empty state is shown
5. Save to apps/web/e2e/functional/ch24-memos-page.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch24-documents-page" \
"SPECIFICATION (from docs/user-manual/24-memos-and-documents.md):
The Documents page is a central repository for all generated
outputs including PDFs, spreadsheets, and exports. Users can
search, filter, and download documents. Each document shows
its name, type, generation date, and source entity.

TASK:
1. Log in and navigate to /documents
2. Assert the page heading contains 'Documents'
3. Assert a search or filter input is visible
4. Assert either document entries or an empty state is shown
5. Save to apps/web/e2e/functional/ch24-documents-page.spec.ts
6. Run and report RED or GREEN"

# ── Ch25: Collaboration ───────────────────────────────────────

run_tdd_test "ch25-collaboration-comments" \
"SPECIFICATION (from docs/user-manual/25-collaboration.md):
The Collaboration section includes threaded comments that can be
attached to baselines, drafts, runs, and other entities. Users
can post comments, reply to threads, and mention other team
members with @mentions.

TASK:
1. Log in and navigate to /comments or the collaboration section
2. Assert a comment input or text area is visible
3. Assert either existing comment threads or an empty state is shown
4. Save to apps/web/e2e/functional/ch25-collaboration-comments.spec.ts
5. Run and report RED or GREEN"

run_tdd_test "ch25-activity-feed" \
"SPECIFICATION (from docs/user-manual/25-collaboration.md):
The activity feed shows a chronological log of all actions taken
across the platform: baseline creation, run execution, document
generation, comment posts, and workflow status changes.

TASK:
1. Log in and navigate to /activity
2. Assert an activity feed or log is visible
3. Assert entries show action descriptions and timestamps
4. If no activity, assert an empty state
5. Save to apps/web/e2e/functional/ch25-activity-feed.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch25-notifications" \
"SPECIFICATION (from docs/user-manual/25-collaboration.md):
Notifications alert users to relevant events: new assignments,
review requests, comment mentions, and workflow stage changes.
The bell icon in the sidebar shows unread notification count.
Clicking opens the notification panel.

TASK:
1. Log in and navigate to /dashboard
2. Assert a notification bell icon is visible in the sidebar
3. Click the bell icon
4. Assert a notification panel or dropdown opens
5. Assert either notification entries or 'No notifications' message
6. Save to apps/web/e2e/functional/ch25-notifications.spec.ts
7. Run and report RED or GREEN"

log_phase_complete "Phase 5"
