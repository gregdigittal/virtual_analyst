# Functional Test RED Fixes — Design Document

**Date:** 2026-03-02
**Context:** 68 functional tests run against production (`virtual-analyst.ai`). 48 GREEN, 18 RED, 1 SKIP. 6 RED tests are deferred (future features). This plan addresses the remaining 12 RED tests.

## Excluded (Future Features)
- `ch03-marketplace-loads` / `ch03-marketplace-use-template` — marketplace API not deployed
- `ch23-board-pack-builder` / `ch23-board-pack-export` — builder/export UI not yet built
- `ch26-billing-page` — billing API not deployed
- `ch26-currency-management` — currency API not deployed

## Category A: Manual Updates (2 tests)

### Fix 1: `ch01-landing-page` — Hero heading text mismatch
- **Problem:** Manual says "Financial Modeling, Reimagined"; production h1 is "One Platform for the Full Financial Modeling Workflow"
- **Fix:** Update `docs/user-manual/01-getting-started.md` to reflect actual heading
- **File:** `docs/user-manual/01-getting-started.md`

### Fix 2: `ch01-login-success` — Login redirect destination
- **Problem:** Manual says login goes to `/dashboard`; actual redirect is `/baselines`
- **Fix:** Update `docs/user-manual/01-getting-started.md` to say `/baselines` instead of `/dashboard`
- **File:** `docs/user-manual/01-getting-started.md`

## Category B: Code Fixes (8 tests)

### Fix 3: `ch04-import-upload-validation` — Missing Next/Continue button
- **Problem:** Excel import wizard has no explicit step-advance button; file selection triggers upload directly
- **Fix:** Add a "Continue" or "Next" button to advance between import wizard steps
- **File:** `apps/web/app/(app)/excel-import/page.tsx`

### Fix 4: `ch14-create-run` — Missing "New Run" button
- **Problem:** Runs page empty state only shows "View baselines" link, no creation action
- **Fix:** Add "New Run" button (visible when baselines exist, or always with appropriate empty-state messaging)
- **File:** `apps/web/app/(app)/runs/page.tsx`

### Fix 5: `ch17-budgets-list` — Missing "Create Budget" button
- **Problem:** Budgets page empty state shows "Browse templates" link instead of create action
- **Fix:** Add "Create Budget" button to page header/action area
- **File:** `apps/web/app/(app)/budgets/page.tsx`

### Fix 6: `ch21-ventures-questionnaire` — Venture creation API error
- **Problem:** "Create venture" click triggers API call that fails; `saas_b2b` template may not exist
- **Fix:** Investigate API endpoint; ensure venture template catalog is seeded or handle missing template gracefully
- **Files:** `apps/web/app/(app)/ventures/page.tsx`, possibly `apps/api/app/routers/ventures.py`

### Fix 7: `ch23-board-packs-list` — Missing "Create Board Pack" button
- **Problem:** Board packs list page shows only "View runs" in empty state
- **Fix:** Add "Create Board Pack" button to page header
- **File:** `apps/web/app/(app)/board-packs/page.tsx`

### Fix 8: `ch25-collaboration-comments` — Missing comment input UI
- **Problem:** No comment textarea visible on entity detail pages
- **Fix:** Ensure CommentThread component renders with input field on entity detail pages (baselines, runs, scenarios)
- **Files:** Entity detail pages + `apps/web/components/` (comment component)

### Fix 9: `ch26-sso-config` — Missing enable/disable toggle
- **Problem:** SSO page shows form fields and status text but no toggle to enable/disable
- **Fix:** Add toggle/switch component to SSO settings page
- **File:** `apps/web/app/(app)/settings/sso/page.tsx`

### Fix 10: `ch26-teams-management` — Missing member management UI
- **Problem:** Teams page only has "Create team", no member invite/list/role UI
- **Fix:** Add member management section: invite form, member list with roles, remove member action
- **File:** `apps/web/app/(app)/settings/teams/page.tsx`

## Category C: Data Seeding (2 tests)

### Fix 11-12: `ch11-draft-editor` / `ch11-draft-commit` — No seeded drafts
- **Problem:** Tests need existing drafts but none exist for test user; draft creation fails (no baselines)
- **Fix:** Update `scripts/functional-tests/seed-test-data.sh` to create a baseline and draft session for the test user via API
- **File:** `scripts/functional-tests/seed-test-data.sh`

## Implementation Strategy

**Wave 1 (parallel, independent):**
- Manual updates (fixes 1-2)
- Seed script update (fixes 11-12)
- Simple UI button additions (fixes 4, 5, 7)
- SSO toggle (fix 9)

**Wave 2 (more complex, may need code exploration):**
- Import wizard steps (fix 3)
- Ventures questionnaire (fix 6)
- Comments UI (fix 8)
- Teams member management (fix 10)
