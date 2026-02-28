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
