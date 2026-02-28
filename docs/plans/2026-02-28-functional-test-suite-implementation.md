# TDD Red-Green Functional Test Suite — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Generate a complete functional test suite driven by `claude -p` shell prompts, using the 26-chapter user manual as the TDD specification. RED = app diverges from manual, GREEN = app conforms.

**Architecture:** Shell scripts organized into 6 phases (matching sidebar groups) invoke `claude -p` sequentially. Each prompt instructs Claude to write a Playwright test encoding a manual specification, run it, and report RED/GREEN. Tests live in `apps/web/e2e/functional/` alongside existing e2e tests. Test data is seeded via API calls before execution.

**Tech Stack:** Bash scripts, Claude Code CLI (`claude -p`), Playwright (already installed), TypeScript, Supabase auth

---

## Prerequisites

- Dev server running: `localhost:3000` (Next.js) + `localhost:8000` (FastAPI)
- Claude Code CLI installed and authenticated
- Playwright installed (`apps/web` already has `@playwright/test@^1.58.2`)
- Database with migrations applied
- Existing Playwright config: `apps/web/playwright.config.ts`
- Existing e2e tests: `apps/web/e2e/auth.spec.ts`, `apps/web/e2e/navigation.spec.ts`

---

## Task 1: Create directory structure and helper library

**Files:**
- Create: `scripts/functional-tests/lib/test-helpers.sh`
- Create: `scripts/functional-tests/results/.gitkeep`
- Create: `apps/web/e2e/functional/fixtures/test-constants.ts`
- Create: `.gitignore` entry for `scripts/functional-tests/results/*.log`

**Step 1: Create directories**

```bash
mkdir -p "scripts/functional-tests/lib"
mkdir -p "scripts/functional-tests/results"
mkdir -p "apps/web/e2e/functional/fixtures"
```

**Step 2: Write `scripts/functional-tests/lib/test-helpers.sh`**

```bash
#!/usr/bin/env bash
# test-helpers.sh — Shared functions for the TDD Red-Green functional test runner

RED_CLR='\033[0;31m'
GREEN_CLR='\033[0;32m'
YELLOW_CLR='\033[1;33m'
CYAN_CLR='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
declare -a RESULTS=()

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

log_phase() {
    echo ""
    echo -e "${CYAN_CLR}${BOLD}════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN_CLR}${BOLD}  $1${NC}"
    echo -e "${CYAN_CLR}${BOLD}════════════════════════════════════════════════════${NC}"
    echo ""
}

log_phase_complete() {
    echo ""
    echo -e "${CYAN_CLR}  ✓ $1 complete (GREEN: $PASS_COUNT | RED: $FAIL_COUNT | SKIP: $SKIP_COUNT)${NC}"
    echo ""
}

run_tdd_test() {
    local test_name="$1"
    local spec="$2"

    echo -e "${YELLOW_CLR}  ▶ TDD test: ${test_name}${NC}"

    local prompt="You are executing a TDD RED-GREEN functional test for Virtual Analyst.

${spec}

TEST CONSTRAINTS:
- Base URL: http://localhost:3000
- Test user email: functional-test@va.dev
- Test user password: TestPass123!
- Write the test in TypeScript using @playwright/test
- Save to: apps/web/e2e/functional/${test_name}.spec.ts
- Use page.waitForSelector() or expect(locator).toBeVisible() for async content
- Assert on visible UI text and elements, not CSS classes or implementation details
- Each test must be independently runnable (login fresh if needed)
- Do not modify application source code
- If you need seeded data IDs, import from apps/web/e2e/functional/fixtures/test-constants.ts
- Run with: cd apps/web && npx playwright test e2e/functional/${test_name}.spec.ts --project=chromium
- Report the result on the LAST LINE in this EXACT format:
  RESULT: GREEN — ${test_name} — PASS
  or
  RESULT: RED — ${test_name} — FAIL — <one-line reason>"

    local output
    output=$(cd "$PROJECT_DIR" && claude -p "$prompt" 2>&1) || true

    # Save full output
    echo "$output" > "$SCRIPT_DIR/results/${test_name}.log"

    # Parse RESULT line
    local result_line
    result_line=$(echo "$output" | grep "^RESULT:" | tail -1)

    if echo "$result_line" | grep -q "GREEN"; then
        echo -e "    ${GREEN_CLR}✓ GREEN — ${test_name} — PASS${NC}"
        PASS_COUNT=$((PASS_COUNT + 1))
        RESULTS+=("GREEN|${test_name}")
    elif echo "$result_line" | grep -q "RED"; then
        local reason
        reason=$(echo "$result_line" | sed 's/.*FAIL — //')
        echo -e "    ${RED_CLR}✗ RED — ${test_name} — FAIL — ${reason}${NC}"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        RESULTS+=("RED|${test_name}|${reason}")
    else
        echo -e "    ${YELLOW_CLR}? SKIP — ${test_name} — No RESULT line in output${NC}"
        SKIP_COUNT=$((SKIP_COUNT + 1))
        RESULTS+=("SKIP|${test_name}|No RESULT line")
    fi
}

print_summary() {
    local total=$((PASS_COUNT + FAIL_COUNT + SKIP_COUNT))
    echo ""
    echo -e "${BOLD}════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}  FUNCTIONAL TEST SUMMARY${NC}"
    echo -e "${BOLD}════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${GREEN_CLR}GREEN (pass): ${PASS_COUNT}${NC}"
    echo -e "  ${RED_CLR}RED (fail):   ${FAIL_COUNT}${NC}"
    echo -e "  ${YELLOW_CLR}SKIP:         ${SKIP_COUNT}${NC}"
    echo -e "  Total:        ${total}"
    echo ""

    if [ ${FAIL_COUNT} -gt 0 ]; then
        echo -e "${RED_CLR}${BOLD}  Specification violations:${NC}"
        for result in "${RESULTS[@]}"; do
            if [[ "$result" == RED* ]]; then
                local name reason
                name=$(echo "$result" | cut -d'|' -f2)
                reason=$(echo "$result" | cut -d'|' -f3)
                echo -e "    ${RED_CLR}✗ ${name}: ${reason}${NC}"
            fi
        done
        echo ""
        exit 1
    else
        echo -e "${GREEN_CLR}${BOLD}  All tests match specification ✓${NC}"
        exit 0
    fi
}
```

**Step 3: Write placeholder `apps/web/e2e/functional/fixtures/test-constants.ts`**

```typescript
// test-constants.ts — Populated by seed-test-data.sh before test execution
export const TEST_USER = {
  email: 'functional-test@va.dev',
  password: 'TestPass123!',
};

export const SEEDED_IDS = {
  tenantId: '',
  baselineId: '',
  draftId: '',
  runId: '',
  afsEngagementId: '',
  budgetId: '',
  covenantId: '',
  boardPackId: '',
  workflowTemplateId: '',
};

export const BASE_URL = 'http://localhost:3000';
export const API_URL = 'http://localhost:8000/api/v1';
```

**Step 4: Add gitignore entry**

Append to `.gitignore`:
```
scripts/functional-tests/results/*.log
```

**Step 5: Commit**

```bash
git add scripts/functional-tests/ apps/web/e2e/functional/ .gitignore
git commit -m "feat: scaffold functional test suite infrastructure

Add test-helpers.sh with TDD RED/GREEN runner, test-constants
fixture placeholder, and results directory for test output logs."
```

---

## Task 2: Create seed and cleanup scripts

**Files:**
- Create: `scripts/functional-tests/seed-test-data.sh`
- Create: `scripts/functional-tests/cleanup-test-data.sh`

**Step 1: Write `scripts/functional-tests/seed-test-data.sh`**

```bash
#!/usr/bin/env bash
# seed-test-data.sh — Seed dev database with test fixtures via API
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
API_URL="${API_URL:-http://localhost:8000/api/v1}"
FIXTURES_FILE="$PROJECT_DIR/apps/web/e2e/functional/fixtures/test-constants.ts"

echo "Seeding test data via ${API_URL}..."

# Step 1: Create test user via Supabase (or use existing)
# In dev, we assume the test user already exists in Supabase auth.
# If not, create via supabase admin API or direct DB insert.
echo "  → Ensuring test user exists (functional-test@va.dev)"

# Step 2: Get auth token
TOKEN=$(curl -s -X POST "${API_URL}/auth/token" \
  -H "Content-Type: application/json" \
  -d '{"email":"functional-test@va.dev","password":"TestPass123!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || echo "")

if [ -z "$TOKEN" ]; then
    echo "  ⚠ Could not get auth token. Using dev bypass header."
    AUTH_HEADER="X-Dev-User: functional-test@va.dev"
else
    AUTH_HEADER="Authorization: Bearer ${TOKEN}"
fi

# Helper: API call with tenant header
api() {
    local method="$1" path="$2"
    shift 2
    curl -s -X "$method" "${API_URL}${path}" \
        -H "Content-Type: application/json" \
        -H "X-Tenant-ID: test-tenant-001" \
        -H "$AUTH_HEADER" \
        "$@"
}

# Step 3: Seed baseline from marketplace template
echo "  → Creating baseline from marketplace template"
TEMPLATES=$(api GET "/marketplace/templates")
FIRST_TEMPLATE_ID=$(echo "$TEMPLATES" | python3 -c "import sys,json; ts=json.load(sys.stdin); print(ts[0]['id'] if ts else '')" 2>/dev/null || echo "")

if [ -n "$FIRST_TEMPLATE_ID" ]; then
    BASELINE_RESP=$(api POST "/marketplace/templates/${FIRST_TEMPLATE_ID}/use" \
        -d "{\"label\":\"Functional Test Baseline\",\"fiscal_year_end\":\"2025-12-31\"}")
    BASELINE_ID=$(echo "$BASELINE_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "seed-baseline-001")
else
    BASELINE_ID="seed-baseline-001"
fi
echo "  → Baseline ID: ${BASELINE_ID}"

# Step 4: Create draft from baseline
echo "  → Creating draft"
DRAFT_RESP=$(api POST "/drafts/create" -d "{\"baseline_id\":\"${BASELINE_ID}\",\"label\":\"Functional Test Draft\"}")
DRAFT_ID=$(echo "$DRAFT_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "seed-draft-001")
echo "  → Draft ID: ${DRAFT_ID}"

# Step 5: Execute a run
echo "  → Executing run"
RUN_RESP=$(api POST "/runs/execute" -d "{\"draft_id\":\"${DRAFT_ID}\",\"mode\":\"deterministic\"}")
RUN_ID=$(echo "$RUN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "seed-run-001")
echo "  → Run ID: ${RUN_ID}"

# Step 6: Create budget
echo "  → Creating budget"
BUDGET_RESP=$(api POST "/budgets/create" -d "{\"label\":\"FY2025 Test Budget\",\"baseline_id\":\"${BASELINE_ID}\"}")
BUDGET_ID=$(echo "$BUDGET_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "seed-budget-001")
echo "  → Budget ID: ${BUDGET_ID}"

# Step 7: Create board pack
echo "  → Creating board pack"
BP_RESP=$(api POST "/board-packs/create" -d "{\"run_id\":\"${RUN_ID}\",\"title\":\"Test Board Pack\"}")
BOARD_PACK_ID=$(echo "$BP_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "seed-bp-001")
echo "  → Board Pack ID: ${BOARD_PACK_ID}"

# Step 8: Get workflow template ID
echo "  → Fetching workflow templates"
WF_TEMPLATES=$(api GET "/workflows/templates")
WF_TEMPLATE_ID=$(echo "$WF_TEMPLATES" | python3 -c "import sys,json; ts=json.load(sys.stdin); print(ts[0]['id'] if ts else '')" 2>/dev/null || echo "seed-wf-tpl-001")
echo "  → Workflow Template ID: ${WF_TEMPLATE_ID}"

# Step 9: Write IDs to test-constants.ts
echo "  → Writing seeded IDs to fixtures"
cat > "$FIXTURES_FILE" << EOF
// test-constants.ts — Auto-generated by seed-test-data.sh
// DO NOT EDIT MANUALLY — re-run seed script to regenerate

export const TEST_USER = {
  email: 'functional-test@va.dev',
  password: 'TestPass123!',
};

export const SEEDED_IDS = {
  tenantId: 'test-tenant-001',
  baselineId: '${BASELINE_ID}',
  draftId: '${DRAFT_ID}',
  runId: '${RUN_ID}',
  afsEngagementId: '',
  budgetId: '${BUDGET_ID}',
  covenantId: '',
  boardPackId: '${BOARD_PACK_ID}',
  workflowTemplateId: '${WF_TEMPLATE_ID}',
};

export const BASE_URL = 'http://localhost:3000';
export const API_URL = 'http://localhost:8000/api/v1';
EOF

echo ""
echo "✓ Test data seeded successfully."
```

**Step 2: Write `scripts/functional-tests/cleanup-test-data.sh`**

```bash
#!/usr/bin/env bash
# cleanup-test-data.sh — Remove test fixtures (reverse order to avoid FK violations)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
API_URL="${API_URL:-http://localhost:8000/api/v1}"
FIXTURES_FILE="$PROJECT_DIR/apps/web/e2e/functional/fixtures/test-constants.ts"

echo "Cleaning up test data..."

# Read IDs from fixtures file
read_id() {
    grep "$1" "$FIXTURES_FILE" | sed "s/.*'\(.*\)'.*/\1/" | head -1
}

BOARD_PACK_ID=$(read_id "boardPackId")
BUDGET_ID=$(read_id "budgetId")
RUN_ID=$(read_id "runId")
DRAFT_ID=$(read_id "draftId")
BASELINE_ID=$(read_id "baselineId")

api() {
    local method="$1" path="$2"
    shift 2
    curl -s -X "$method" "${API_URL}${path}" \
        -H "Content-Type: application/json" \
        -H "X-Tenant-ID: test-tenant-001" \
        -H "X-Dev-User: functional-test@va.dev" \
        "$@"
}

# Delete in reverse dependency order
[ -n "$BOARD_PACK_ID" ] && api DELETE "/board-packs/${BOARD_PACK_ID}" && echo "  → Deleted board pack"
[ -n "$BUDGET_ID" ] && api DELETE "/budgets/${BUDGET_ID}" && echo "  → Deleted budget"
[ -n "$RUN_ID" ] && api DELETE "/runs/${RUN_ID}" && echo "  → Deleted run"
[ -n "$DRAFT_ID" ] && api DELETE "/drafts/${DRAFT_ID}" && echo "  → Deleted draft"
[ -n "$BASELINE_ID" ] && api DELETE "/baselines/${BASELINE_ID}" && echo "  → Deleted baseline"

# Clean up generated test files
echo "  → Removing generated spec files"
rm -f "$PROJECT_DIR/apps/web/e2e/functional/"*.spec.ts

echo ""
echo "✓ Cleanup complete."
```

**Step 3: Make scripts executable**

```bash
chmod +x scripts/functional-tests/seed-test-data.sh
chmod +x scripts/functional-tests/cleanup-test-data.sh
```

**Step 4: Commit**

```bash
git add scripts/functional-tests/seed-test-data.sh scripts/functional-tests/cleanup-test-data.sh
git commit -m "feat: add seed and cleanup scripts for functional test data"
```

---

## Task 3: Create Phase 1 — Getting Started (Ch01-02)

**Files:**
- Create: `scripts/functional-tests/phase-1-getting-started.sh`

**Step 1: Write the phase script with all test prompts**

```bash
#!/usr/bin/env bash
# phase-1-getting-started.sh — Ch01-02: Auth & Dashboard
# Manual refs: docs/user-manual/01-getting-started.md, 02-dashboard.md
set -euo pipefail
source "$(dirname "$0")/lib/test-helpers.sh"

log_phase "Phase 1: Getting Started (Ch01-02)"

# ── Ch01: Getting Started ─────────────────────────────────────

run_tdd_test "ch01-landing-page" \
"SPECIFICATION (from docs/user-manual/01-getting-started.md):
The landing page at the root URL (/) displays a hero section with the
headline 'Financial Modeling, Reimagined' and a primary call-to-action
button labeled 'Get started free'. Clicking the CTA navigates to the
authentication page. If the user is already authenticated, visiting /
redirects them to /dashboard.

TASK:
1. Navigate to http://localhost:3000
2. Assert the hero heading text is visible
3. Assert a CTA button/link with text containing 'Get started' exists
4. Click the CTA and assert the URL changes to include /login or /signup or /auth
5. Save to apps/web/e2e/functional/ch01-landing-page.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch01-login-form" \
"SPECIFICATION (from docs/user-manual/01-getting-started.md):
The login page presents email and password input fields and a Sign in
button. It also shows Google SSO and Microsoft SSO options as alternative
sign-in methods. There is a link to switch to the signup/registration form.

TASK:
1. Navigate to http://localhost:3000/login
2. Assert an email input field is visible
3. Assert a password input field is visible
4. Assert a Sign in button is visible
5. Assert Google and Microsoft OAuth buttons are visible
6. Assert a link to the signup page exists
7. Save to apps/web/e2e/functional/ch01-login-form.spec.ts
8. Run and report RED or GREEN"

run_tdd_test "ch01-signup-form" \
"SPECIFICATION (from docs/user-manual/01-getting-started.md):
The signup page lets users create an account with email and password.
It includes email, password, and confirm-password fields plus a Create
account button. OAuth options (Google, Microsoft) are also shown.

TASK:
1. Navigate to http://localhost:3000/signup
2. Assert email, password, and confirm-password inputs exist
3. Assert a Create account or Sign up button is visible
4. Assert OAuth provider buttons are visible
5. Save to apps/web/e2e/functional/ch01-signup-form.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch01-login-success" \
"SPECIFICATION (from docs/user-manual/01-getting-started.md):
After entering valid credentials (email + password) and clicking Sign in,
the user is redirected to the Dashboard at /dashboard.

TASK:
1. Navigate to http://localhost:3000/login
2. Fill the email field with functional-test@va.dev
3. Fill the password field with TestPass123!
4. Click the Sign in button
5. Wait up to 15 seconds for navigation
6. Assert the URL is /dashboard
7. Save to apps/web/e2e/functional/ch01-login-success.spec.ts
8. Run and report RED or GREEN"

run_tdd_test "ch01-protected-redirect" \
"SPECIFICATION (from docs/user-manual/01-getting-started.md):
If an unauthenticated user tries to access a protected page like
/dashboard, /baselines, or /runs, they are redirected to the login
page. After logging in, they should be sent to the originally
requested page.

TASK:
1. Without logging in, navigate to http://localhost:3000/dashboard
2. Assert the URL changes to /login (possibly with a ?next= parameter)
3. Save to apps/web/e2e/functional/ch01-protected-redirect.spec.ts
4. Run and report RED or GREEN"

# ── Ch02: Dashboard ────────────────────────────────────────────

run_tdd_test "ch02-dashboard-loads" \
"SPECIFICATION (from docs/user-manual/02-dashboard.md):
After login, the Dashboard is the first page the user sees. It displays
summary cards for Recent Runs, Pending Tasks, and Unread Notifications.
The sidebar navigation is visible with links to all major sections.

TASK:
1. Log in as functional-test@va.dev / TestPass123!
2. Assert the page URL is /dashboard
3. Assert at least one summary card or stat widget is visible
4. Assert the sidebar/navigation menu is visible
5. Save to apps/web/e2e/functional/ch02-dashboard-loads.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch02-sidebar-navigation" \
"SPECIFICATION (from docs/user-manual/02-dashboard.md):
The sidebar shows navigation links organized into groups: SETUP
(Dashboard, Marketplace, Import Excel, Excel Connections, AFS, Groups),
CONFIGURE (Baselines, Drafts, Scenarios, Changesets), ANALYZE (Runs,
Budgets, Covenants, Benchmarking, Compare, Ventures), COLLABORATE &
REPORT (Workflows, Board Packs, Memos, Documents, Collaboration),
and ADMIN (Settings).

TASK:
1. Log in and navigate to /dashboard
2. Assert the sidebar contains links with text matching at least:
   Dashboard, Marketplace, Baselines, Runs, Settings
3. Assert clicking 'Baselines' navigates to /baselines
4. Save to apps/web/e2e/functional/ch02-sidebar-navigation.spec.ts
5. Run and report RED or GREEN"

run_tdd_test "ch02-dashboard-activity" \
"SPECIFICATION (from docs/user-manual/02-dashboard.md):
The Dashboard shows a recent-activity section listing the user's
latest actions such as baseline creation, run execution, and
document generation. For a new account with no activity, an empty
state is displayed.

TASK:
1. Log in and navigate to /dashboard
2. Look for a recent activity section or activity feed element
3. Assert that either activity items are listed OR an empty-state
   message is visible (both are valid states)
4. Save to apps/web/e2e/functional/ch02-dashboard-activity.spec.ts
5. Run and report RED or GREEN"

log_phase_complete "Phase 1"
```

**Step 2: Make executable**

```bash
chmod +x scripts/functional-tests/phase-1-getting-started.sh
```

**Step 3: Commit**

```bash
git add scripts/functional-tests/phase-1-getting-started.sh
git commit -m "feat: add Phase 1 functional tests — Getting Started (Ch01-02)

8 TDD RED/GREEN tests covering: landing page, login form, signup form,
login success, protected redirects, dashboard loading, sidebar nav,
and dashboard activity feed."
```

---

## Task 4: Create Phase 2 — Setup (Ch03-09)

**Files:**
- Create: `scripts/functional-tests/phase-2-setup.sh`

**Step 1: Write the phase script**

```bash
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
```

**Step 2: Make executable and commit**

```bash
chmod +x scripts/functional-tests/phase-2-setup.sh
git add scripts/functional-tests/phase-2-setup.sh
git commit -m "feat: add Phase 2 functional tests — Setup (Ch03-09)

16 TDD RED/GREEN tests covering: marketplace browse/search/use,
data import wizard, Excel connections, AFS module (dashboard, engagement,
sections, review, tax, consolidation, output), org structures."
```

---

## Task 5: Create Phase 3 — Configure (Ch10-13)

**Files:**
- Create: `scripts/functional-tests/phase-3-configure.sh`

**Step 1: Write the phase script**

```bash
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
```

**Step 2: Make executable and commit**

```bash
chmod +x scripts/functional-tests/phase-3-configure.sh
git add scripts/functional-tests/phase-3-configure.sh
git commit -m "feat: add Phase 3 functional tests — Configure (Ch10-13)

10 TDD RED/GREEN tests covering: baselines list/detail/archive,
drafts list/editor/commit, scenarios page/create, changesets
page/dry-run."
```

---

## Task 6: Create Phase 4 — Analyze (Ch14-21)

**Files:**
- Create: `scripts/functional-tests/phase-4-analyze.sh`

**Step 1: Write the phase script**

```bash
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
```

**Step 2: Make executable and commit**

```bash
chmod +x scripts/functional-tests/phase-4-analyze.sh
git add scripts/functional-tests/phase-4-analyze.sh
git commit -m "feat: add Phase 4 functional tests — Analyze (Ch14-21)

16 TDD RED/GREEN tests covering: runs list/detail/KPIs/create,
Monte Carlo charts, sensitivity analysis, valuation, budgets
list/variance, covenants page/alerts, benchmarking, entity
comparison, ventures page/questionnaire."
```

---

## Task 7: Create Phase 5 — Collaborate (Ch22-25)

**Files:**
- Create: `scripts/functional-tests/phase-5-collaborate.sh`

**Step 1: Write the phase script**

```bash
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
```

**Step 2: Make executable and commit**

```bash
chmod +x scripts/functional-tests/phase-5-collaborate.sh
git add scripts/functional-tests/phase-5-collaborate.sh
git commit -m "feat: add Phase 5 functional tests — Collaborate & Report (Ch22-25)

11 TDD RED/GREEN tests covering: workflows page/create, inbox tasks,
board packs list/builder/export, memos page, documents page,
collaboration comments, activity feed, notifications."
```

---

## Task 8: Create Phase 6 — Admin (Ch26)

**Files:**
- Create: `scripts/functional-tests/phase-6-admin.sh`

**Step 1: Write the phase script**

```bash
#!/usr/bin/env bash
# phase-6-admin.sh — Ch26: Settings and Administration
# Manual ref: docs/user-manual/26-settings-and-admin.md
set -euo pipefail
source "$(dirname "$0")/lib/test-helpers.sh"

log_phase "Phase 6: Admin (Ch26)"

# ── Ch26: Settings and Administration ──────────────────────────

run_tdd_test "ch26-settings-hub" \
"SPECIFICATION (from docs/user-manual/26-settings-and-admin.md):
The Settings page is a card-based hub with sections for Billing,
Integrations, Teams, SSO/SAML, Audit Log, Compliance, and Currency
Management. Each card links to its configuration sub-page.

TASK:
1. Log in and navigate to /settings
2. Assert the page heading contains 'Settings'
3. Assert multiple settings cards or sections are visible
4. Assert at least these sections exist: Billing, Teams, Integrations
5. Save to apps/web/e2e/functional/ch26-settings-hub.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch26-teams-management" \
"SPECIFICATION (from docs/user-manual/26-settings-and-admin.md):
The Teams section lets tenant administrators manage team members.
Admins can invite new users, assign roles, and remove members.
The team list shows each member's name, email, role, and status.

TASK:
1. Log in and navigate to /settings (then click Teams)
2. Assert a team member list is visible
3. Assert an 'Invite' or 'Add Member' button exists
4. Assert each member shows a name and role
5. Save to apps/web/e2e/functional/ch26-teams-management.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch26-billing-page" \
"SPECIFICATION (from docs/user-manual/26-settings-and-admin.md):
The Billing section shows the current plan tier, usage meters
(LLM tokens, Monte Carlo runs, sync events), and payment method.
Users can upgrade or downgrade their plan.

TASK:
1. Log in and navigate to /settings (then click Billing)
2. Assert the current plan tier is displayed
3. Assert usage meter(s) are visible
4. Assert plan upgrade/downgrade options exist
5. Save to apps/web/e2e/functional/ch26-billing-page.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch26-integrations" \
"SPECIFICATION (from docs/user-manual/26-settings-and-admin.md):
The Integrations section shows available third-party connections:
Xero and QuickBooks (via OAuth 2.0). Each integration card shows
its connection status and a Connect/Disconnect button.

TASK:
1. Log in and navigate to /settings (then click Integrations)
2. Assert integration cards are visible (Xero, QuickBooks)
3. Assert each shows a connection status
4. Assert Connect buttons are available for unconnected integrations
5. Save to apps/web/e2e/functional/ch26-integrations.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch26-audit-log" \
"SPECIFICATION (from docs/user-manual/26-settings-and-admin.md):
The Audit Log provides an immutable record of all significant
actions. Entries show timestamp, user, action type, and affected
entity. The log is searchable and filterable by date range and
action type.

TASK:
1. Log in and navigate to /settings (then click Audit Log)
2. Assert audit log entries or a table is visible
3. Assert search/filter controls exist
4. Assert entries show timestamp, user, and action
5. Save to apps/web/e2e/functional/ch26-audit-log.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch26-currency-management" \
"SPECIFICATION (from docs/user-manual/26-settings-and-admin.md):
The Currency section lets users configure multi-currency support
and FX rates. Users can set a base currency, add supported
currencies, and update exchange rates manually or via automatic
feeds.

TASK:
1. Log in and navigate to /settings (then click Currency)
2. Assert base currency display or selection is visible
3. Assert currency list or FX rate table is shown
4. Assert an 'Add Currency' or 'Update Rates' control exists
5. Save to apps/web/e2e/functional/ch26-currency-management.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch26-compliance-settings" \
"SPECIFICATION (from docs/user-manual/26-settings-and-admin.md):
The Compliance section provides GDPR tools including data export
requests, data deletion requests, and consent management. It shows
compliance status and available actions.

TASK:
1. Log in and navigate to /settings (then click Compliance)
2. Assert compliance or GDPR controls are visible
3. Assert data export and deletion request options exist
4. Save to apps/web/e2e/functional/ch26-compliance-settings.spec.ts
5. Run and report RED or GREEN"

run_tdd_test "ch26-sso-config" \
"SPECIFICATION (from docs/user-manual/26-settings-and-admin.md):
The SSO/SAML section allows enterprise administrators to configure
single sign-on with their identity provider. Fields include IdP
metadata URL, entity ID, and certificate. SSO can be enabled or
disabled per tenant.

TASK:
1. Log in and navigate to /settings (then click SSO or SAML)
2. Assert SSO configuration fields are visible
3. Assert an enable/disable toggle exists
4. Assert IdP configuration fields (URL, entity ID) are shown
5. Save to apps/web/e2e/functional/ch26-sso-config.spec.ts
6. Run and report RED or GREEN"

log_phase_complete "Phase 6"
```

**Step 2: Make executable and commit**

```bash
chmod +x scripts/functional-tests/phase-6-admin.sh
git add scripts/functional-tests/phase-6-admin.sh
git commit -m "feat: add Phase 6 functional tests — Admin (Ch26)

8 TDD RED/GREEN tests covering: settings hub, teams management,
billing page, integrations, audit log, currency management,
compliance settings, SSO configuration."
```

---

## Task 9: Create master runner (run-all.sh)

**Files:**
- Create: `scripts/functional-tests/run-all.sh`

**Step 1: Write `scripts/functional-tests/run-all.sh`**

```bash
#!/usr/bin/env bash
# run-all.sh — Master runner for TDD Red-Green functional test suite
#
# Usage:
#   ./scripts/functional-tests/run-all.sh              # Run all 6 phases
#   ./scripts/functional-tests/run-all.sh --phase 3    # Run only phase 3
#   ./scripts/functional-tests/run-all.sh --no-seed    # Skip seeding (data already exists)
#   ./scripts/functional-tests/run-all.sh --no-cleanup  # Skip cleanup (keep test data)
#
# Prerequisites:
#   - Dev server running at localhost:3000 (Next.js) and localhost:8000 (FastAPI)
#   - Claude Code CLI installed and authenticated
#   - Node.js and npx available
#   - Database with migrations applied
#
# TDD Philosophy:
#   Each test encodes a claim from docs/user-manual/ (the specification).
#   RED = app diverges from the manual. GREEN = app conforms.
#   Run this suite to answer: "Does the app do what the manual says?"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/lib/test-helpers.sh"

PHASE_FILTER=""
SEED=true
CLEANUP=true

while [[ $# -gt 0 ]]; do
    case $1 in
        --phase) PHASE_FILTER="$2"; shift 2 ;;
        --no-seed) SEED=false; shift ;;
        --no-cleanup) CLEANUP=false; shift ;;
        --help|-h)
            echo "Usage: $0 [--phase N] [--no-seed] [--no-cleanup]"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

echo -e "${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║  Virtual Analyst — TDD Red-Green Functional Test Suite  ║${NC}"
echo -e "${BOLD}║  Specification: docs/user-manual/ (26 chapters)         ║${NC}"
echo -e "${BOLD}║  Method: claude -p → Playwright → RED/GREEN             ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Preflight checks
echo "Preflight checks..."

if ! command -v claude &>/dev/null; then
    echo -e "${RED_CLR}✗ Claude Code CLI not found. Install: https://docs.anthropic.com/claude-code${NC}"
    exit 1
fi
echo -e "  ${GREEN_CLR}✓ Claude Code CLI available${NC}"

if ! curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo -e "${RED_CLR}✗ Web server not responding at localhost:3000${NC}"
    exit 1
fi
echo -e "  ${GREEN_CLR}✓ Web server running at localhost:3000${NC}"

if ! curl -s http://localhost:8000/docs > /dev/null 2>&1; then
    echo -e "${YELLOW_CLR}⚠ API server may not be running at localhost:8000 (non-critical for UI tests)${NC}"
fi

# Ensure Playwright is ready
cd "$PROJECT_DIR/apps/web"
if ! npx playwright --version &>/dev/null 2>&1; then
    echo "Installing Playwright..."
    npx playwright install chromium
fi
echo -e "  ${GREEN_CLR}✓ Playwright available${NC}"
cd "$PROJECT_DIR"

# Create results directory
mkdir -p "$SCRIPT_DIR/results"

# Seed test data
if $SEED; then
    echo ""
    echo -e "${CYAN_CLR}Seeding test data...${NC}"
    bash "$SCRIPT_DIR/seed-test-data.sh" || {
        echo -e "${YELLOW_CLR}⚠ Seed script had errors (continuing anyway)${NC}"
    }
fi

echo ""
echo -e "${CYAN_CLR}Starting test execution...${NC}"
START_TIME=$(date +%s)

# Run phases
run_phase() {
    local phase_num="$1"
    if [[ -n "$PHASE_FILTER" && "$PHASE_FILTER" != "$phase_num" ]]; then
        return
    fi
    local phase_script="$SCRIPT_DIR/phase-${phase_num}-"*.sh
    for script in $phase_script; do
        if [[ -f "$script" ]]; then
            source "$script"
        fi
    done
}

run_phase 1
run_phase 2
run_phase 3
run_phase 4
run_phase 5
run_phase 6

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))

echo ""
echo -e "${CYAN_CLR}Total execution time: ${MINUTES}m ${SECONDS}s${NC}"

# Cleanup
if $CLEANUP; then
    echo ""
    echo -e "${CYAN_CLR}Cleaning up test data...${NC}"
    bash "$SCRIPT_DIR/cleanup-test-data.sh" 2>/dev/null || true
fi

# Print final summary
print_summary
```

**Step 2: Make executable and commit**

```bash
chmod +x scripts/functional-tests/run-all.sh
git add scripts/functional-tests/run-all.sh
git commit -m "feat: add master runner for functional test suite

run-all.sh orchestrates all 6 phases with preflight checks, seeding,
cleanup, and summary reporting. Supports --phase N, --no-seed, and
--no-cleanup flags."
```

---

## Task 10: Verify the suite structure

**Step 1: List all created files**

```bash
find scripts/functional-tests -type f | sort
find apps/web/e2e/functional -type f | sort
```

Expected:
```
scripts/functional-tests/cleanup-test-data.sh
scripts/functional-tests/lib/test-helpers.sh
scripts/functional-tests/phase-1-getting-started.sh
scripts/functional-tests/phase-2-setup.sh
scripts/functional-tests/phase-3-configure.sh
scripts/functional-tests/phase-4-analyze.sh
scripts/functional-tests/phase-5-collaborate.sh
scripts/functional-tests/phase-6-admin.sh
scripts/functional-tests/results/.gitkeep
scripts/functional-tests/run-all.sh
scripts/functional-tests/seed-test-data.sh
apps/web/e2e/functional/fixtures/test-constants.ts
```

**Step 2: Count total tests**

```bash
grep -c "run_tdd_test" scripts/functional-tests/phase-*.sh | awk -F: '{s+=$2} END {print "Total tests:", s}'
```

Expected: `Total tests: 69`

**Step 3: Verify all scripts are executable**

```bash
ls -la scripts/functional-tests/*.sh scripts/functional-tests/lib/*.sh
```

Expected: All files show `-rwxr-xr-x` permissions.

**Step 4: Dry run syntax check (no execution)**

```bash
bash -n scripts/functional-tests/run-all.sh
bash -n scripts/functional-tests/lib/test-helpers.sh
bash -n scripts/functional-tests/phase-1-getting-started.sh
bash -n scripts/functional-tests/phase-2-setup.sh
bash -n scripts/functional-tests/phase-3-configure.sh
bash -n scripts/functional-tests/phase-4-analyze.sh
bash -n scripts/functional-tests/phase-5-collaborate.sh
bash -n scripts/functional-tests/phase-6-admin.sh
bash -n scripts/functional-tests/seed-test-data.sh
bash -n scripts/functional-tests/cleanup-test-data.sh
```

Expected: No syntax errors.

---

## Task 11: Final commit with all files

**Step 1: Stage and commit everything**

```bash
git add scripts/functional-tests/ apps/web/e2e/functional/ docs/plans/2026-02-28-functional-test-suite-*.md .gitignore
git commit -m "feat: complete TDD Red-Green functional test suite

69 tests across 6 phases, driven by claude -p prompts:
- Phase 1: Getting Started (8 tests) — Ch01-02
- Phase 2: Setup (16 tests) — Ch03-09
- Phase 3: Configure (10 tests) — Ch10-13
- Phase 4: Analyze (16 tests) — Ch14-21
- Phase 5: Collaborate & Report (11 tests) — Ch22-25
- Phase 6: Admin (8 tests) — Ch26

Each test encodes a specification from docs/user-manual/.
RED = app diverges from manual, GREEN = app conforms.

Run: ./scripts/functional-tests/run-all.sh
Single phase: ./scripts/functional-tests/run-all.sh --phase 1"
```

---

## Test Count Summary

| Phase | Chapters | Tests |
|-------|----------|-------|
| 1 — Getting Started | Ch01-02 | 8 |
| 2 — Setup | Ch03-09 | 16 |
| 3 — Configure | Ch10-13 | 10 |
| 4 — Analyze | Ch14-21 | 16 |
| 5 — Collaborate & Report | Ch22-25 | 11 |
| 6 — Admin | Ch26 | 8 |
| **Total** | **26 chapters** | **69** |
