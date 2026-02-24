# Cursor Prompts for Remaining Backlog Items

> Generated: 2026-02-23 from comprehensive codebase review
> Use these prompts in Cursor to implement each backlog item.
> Copy a prompt, paste into Cursor, and let it do the work.

---

## Tier 1 — Ship Blockers

### S-01: Commit and deploy uncommitted work

```
This is a git housekeeping task. The following files are uncommitted and need to be staged and committed:

Modified: apps/api/app/main.py
New test files in tests/unit/:
- test_activity_api.py, test_audit_api.py, test_benchmark_api.py
- test_board_pack_schedules_api.py, test_comments_api.py, test_compliance_api.py
- test_connectors_api.py, test_covenants_api.py, test_documents_api.py
- test_feedback_api.py, test_health_api.py, test_import_csv_api.py
- test_integrations_api.py, test_marketplace_api.py, test_metrics_summary_api.py
- test_notifications_api.py, test_org_structures_api.py

Also commit the security hardening fixes in:
- apps/api/app/core/settings.py (production secret validation)
- apps/api/app/routers/integrations.py (HMAC strength, error masking)
- apps/api/app/routers/drafts.py (XSS pattern hardening)
- apps/api/app/routers/excel.py (bounds checking)
- apps/api/app/services/integrations/quickbooks.py (safe int parsing)
- apps/api/app/services/integrations/xero.py (safe int parsing)
- apps/api/app/db/connection.py (cleanup logging)
- apps/api/app/services/excel_parser.py (named ranges logging)
- apps/web/components/ui/ToastProvider.tsx (timeout cleanup)

Commit message: "Round 25: 18 router test files, security hardening (HMAC, XSS, secrets validation, safe parsing)"

Run `python -m pytest tests/unit/ -x -q` to verify all tests pass before committing.
Do NOT push — just commit locally.
```

### S-02: Update CONTEXT.md

```
Update CONTEXT.md to reflect the current state of the project:

1. Update "Latest commit" to reference the Round 25 commit (after S-01 is committed)
2. Update backend test count to 284 passed (was 214)
3. Update "Routers with tests" to 35/35 (was 17/35) — all 18 previously untested routers now have tests:
   activity, audit, benchmark, board_pack_schedules, comments, compliance, connectors, covenants, documents, feedback, health, import_csv, integrations, marketplace, metrics_summary, notifications, org_structures
4. Clear the "In Progress" section
5. Add security hardening to the changelog: production secrets validation (ValueError instead of warning), HMAC-SHA256 increased to 32 hex chars, XSS pattern expanded (data:, vbscript:, event handlers), safe int() parsing in OAuth adapters, bounds checking in Excel path resolver, toast timeout cleanup
6. Frontend tests remain at 33 passed (5 test files)
7. TypeScript: 0 errors

Keep the same format and tone as the existing CONTEXT.md.
```

---

## Tier 2 — High Priority

### H-02: Frontend page-level smoke tests

```
Create frontend page-level smoke tests using Vitest + React Testing Library. Tests go in apps/web/tests/pages/.

The project uses:
- Next.js 14.2 App Router
- Vitest 4.0 (configured in apps/web/)
- React Testing Library
- @supabase/ssr for auth
- Existing test pattern: see apps/web/tests/components/VAInput.test.tsx

For each page, create a smoke test that:
1. Mocks `@/lib/auth` getAuthContext to return { tenantId: "t1", userId: "u1", accessToken: "tok" }
2. Mocks `@/lib/api` — stub the relevant api.* methods to return minimal valid data
3. Mocks `next/navigation` useRouter, useParams, usePathname, useSearchParams
4. Renders the page component
5. Asserts it renders without crashing (no thrown errors)
6. Asserts key UI elements are present (headings, buttons, tables)

Priority pages (do these first):
1. apps/web/app/dashboard/page.tsx — mock api.getDashboard()
2. apps/web/app/baselines/page.tsx — mock api.listBaselines()
3. apps/web/app/baselines/[id]/page.tsx — mock api.getBaseline(), useParams returns {id: "bl_test"}
4. apps/web/app/runs/[id]/page.tsx — mock api.getRun(), api.getStatements(), useParams
5. apps/web/app/compare/page.tsx — mock api.listRuns(), api.listOrgStructures()
6. apps/web/app/workflows/page.tsx — mock api.listWorkflows()
7. apps/web/app/budgets/[id]/page.tsx — mock api.getBudget(), useParams

Use this mock pattern:
```typescript
vi.mock("@/lib/auth", () => ({
  getAuthContext: vi.fn().mockResolvedValue({
    tenantId: "t1", userId: "u1", accessToken: "tok",
  }),
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
  useParams: () => ({ id: "test-id" }),
  usePathname: () => "/test",
  useSearchParams: () => new URLSearchParams(),
}));
```

Run `npx vitest run` after creating each test to verify it passes.
```

### H-03: Board pack email distribution (SendGrid)

```
Implement real email distribution for board packs. The stub is at:
apps/api/app/routers/board_pack_schedules.py line 247 — the `distribute` endpoint currently just marks the pack as distributed but doesn't send email.

Implementation plan:
1. Add a new service at apps/api/app/services/email.py:
   - Use SendGrid (sendgrid Python package) or AWS SES (boto3)
   - Add SENDGRID_API_KEY to apps/api/app/core/settings.py as optional Field
   - Create an async function: send_board_pack_email(to_emails: list[str], pack_id: str, tenant_id: str, pdf_bytes: bytes | None, subject: str)
   - If SENDGRID_API_KEY is not set, log a warning and skip sending (graceful degradation)
   - Include the board pack PDF as an attachment if pdf_bytes is provided

2. Update the distribute endpoint in board_pack_schedules.py:
   - After marking distributed, call the email service
   - Load the board pack PDF from artifact store if available
   - Send to body.emails
   - Log success/failure per recipient
   - Return { distributed: true, emails_sent: N, errors: [...] }

3. Add SENDGRID_API_KEY to .env.example with a comment

4. Add a unit test at tests/unit/test_email_service.py:
   - Mock sendgrid.SendGridAPIClient
   - Verify send_board_pack_email calls the API correctly
   - Verify graceful skip when API key is not set

Don't install sendgrid yet — just add it to pyproject.toml [project.optional-dependencies].
The existing test pattern uses unittest.mock — follow that convention.
```

### H-04: Board pack update endpoint (real implementation)

```
The board pack PATCH endpoint at apps/api/app/routers/board_packs.py line 368 is labeled "Phase 10 stub". It currently only updates label, status, branding_json, and section_order_json via simple SQL UPDATE.

Read the full endpoint code at board_packs.py to understand the current implementation, then enhance it:

1. Read the current PatchBoardPackBody model — it already has fields for label, section_order_json, branding_json, and status
2. Add support for updating individual sections:
   - Add an optional `sections` field to PatchBoardPackBody: list of { section_id: str, title: str | None, content_json: dict | None, position: int | None }
   - For each section in the list, UPDATE board_pack_sections SET title/content/position WHERE pack_id AND section_id AND tenant_id
3. Add validation:
   - section_order_json must be a list of valid section_id strings
   - branding_json must have at most: logo_url (str), primary_color (str), font_family (str)
   - Reject unknown keys in branding_json
4. Remove the "Phase 10 stub" comment
5. Add audit event for pack updates (use create_audit_event with event_type "board_pack_updated")

Add a test at tests/unit/test_board_packs_update.py following the existing test pattern (mock tenant_conn, TestClient).
```

---

## Tier 3 — Medium Priority

### M-01: Compare page entity scoping

```
Fix the TODO at apps/web/app/compare/page.tsx line 119:
// TODO: scope runs per entity once baseline_id is exposed on OrgStructureItem

Current behavior: The compare page shows ALL runs across all entities.
Desired behavior: Filter runs to only show those belonging to the selected entity's baseline.

Steps:
1. Check apps/api/app/routers/org_structures.py — verify that OrgStructureItem includes baseline_id in the response. If not, add it to the SQL SELECT and response dict.
2. In apps/web/app/compare/page.tsx:
   - After fetching org structures, when user selects an entity, use its baseline_id to filter runs
   - Update the runs fetch to include ?baseline_id=X query parameter
3. In apps/api/app/routers/runs.py — verify the list runs endpoint supports filtering by baseline_id. If not, add a Query parameter: baseline_id: str | None = Query(None)
4. Remove the TODO comment after implementing

The compare page currently calls api.listRuns() — check apps/web/lib/api.ts for the function signature and add baseline_id as an optional parameter if needed.
```

### M-02: Budget is_revenue flag

```
Implement the TODO at apps/api/app/routers/budgets.py line 1388:
// TODO(VA-P7): add explicit is_revenue flag to budget_line_items for accuracy.

Steps:
1. Create a new migration file at apps/api/app/db/migrations/0049_budget_is_revenue.sql:
   ALTER TABLE budget_line_items ADD COLUMN is_revenue BOOLEAN DEFAULT false;
   UPDATE budget_line_items SET is_revenue = true WHERE category = 'revenue';

2. In apps/api/app/routers/budgets.py:
   - Add is_revenue to the INSERT for budget_line_items
   - Add is_revenue to the SELECT and response serialization
   - Use is_revenue instead of category-based heuristics for variance calculations
   - Remove the TODO comment

3. In apps/web/app/budgets/[id]/page.tsx:
   - If the budget form has a line item editor, add a checkbox/toggle for "Is Revenue"
   - Use is_revenue to color-code variance (positive = good for revenue, negative = good for costs)

4. Add a unit test verifying that is_revenue=true items have correct variance sign.

Keep the migration idempotent (use IF NOT EXISTS or check column existence).
```

### M-03: Nav sign-out auth migration

```
In apps/web/components/nav.tsx, the sign-out handler at line 78 uses raw createClient() from @/lib/supabase/client:

  const supabase = createClient();
  await supabase.auth.signOut();

Migrate this to use the shared auth utility for consistency with the rest of the app.

Steps:
1. Check apps/web/lib/auth.ts for an existing signOut or logout function. If none exists, add one:
   export async function signOut() {
     const supabase = createClient();
     await supabase.auth.signOut();
   }

2. In nav.tsx:
   - Import signOut from "@/lib/auth" instead of createClient from "@/lib/supabase/client"
   - Replace the signOut handler body:
     api.setAccessToken(null);
     await signOut();
     router.push("/");
     router.refresh();
   - Remove the unused createClient import

3. Verify no other files use createClient() directly for auth operations (signIn, signOut, signUp) — if they do, migrate those too.

Run `npx tsc --noEmit` to verify no TypeScript errors after the change.
```

### M-04: Cursor prompt cleanup

```
There are 47 CURSOR_PROMPT_*.md files in the repo root. All prompts have been applied and are no longer needed.

Steps:
1. Create a directory: docs/prompts/archive/
2. Move all CURSOR_PROMPT_*.md files from the repo root to docs/prompts/archive/
3. Add docs/prompts/archive/ to .gitignore so they don't clutter the repo
4. Alternatively, if the user prefers a clean repo, delete them entirely

Use: git ls-files --others --exclude-standard | grep CURSOR_PROMPT to find all untracked prompt files.
Then: mkdir -p docs/prompts/archive && mv CURSOR_PROMPT_*.md docs/prompts/archive/

Do NOT delete them without user confirmation — archive first.
```

### M-05: BUILD_PLAN_ENHANCEMENTS.md

```
The file BUILD_PLAN_ENHANCEMENTS.md is untracked in the repo root. It documents the Round 23 P1-P10 enhancement plan which has been fully implemented and committed.

Options:
1. Commit it to the repo for historical reference
2. Move it to docs/plans/ and commit
3. Add it to .gitignore

Recommended: Move to docs/plans/BUILD_PLAN_ENHANCEMENTS_R23.md and commit with message "docs: archive Round 23 enhancement plan"
```

---

## Tier 4 — Nice to Have

### N-01: Integration tests without real DB

```
The 18 integration tests in tests/integration/ are skipped unless INTEGRATION_TESTS=1 is set and a real PostgreSQL database is available.

Create a Docker Compose test target for CI:

1. Create docker-compose.test.yml:
   services:
     postgres-test:
       image: postgres:15
       environment:
         POSTGRES_DB: finmodel_test
         POSTGRES_USER: postgres
         POSTGRES_PASSWORD: postgres
       ports: ["5433:5432"]
       healthcheck:
         test: ["CMD-SHELL", "pg_isready -U postgres"]
         interval: 5s
         timeout: 5s
         retries: 5

2. Create scripts/run-integration-tests.sh:
   #!/bin/bash
   docker compose -f docker-compose.test.yml up -d --wait
   export DATABASE_URL="postgresql://postgres:postgres@localhost:5433/finmodel_test"
   export INTEGRATION_TESTS=1
   export ENVIRONMENT=test
   # Run migrations
   for f in apps/api/app/db/migrations/*.sql; do psql "$DATABASE_URL" -f "$f"; done
   # Run tests
   python -m pytest tests/integration/ -v --tb=short
   docker compose -f docker-compose.test.yml down -v

3. Add to .github/workflows/ci.yml as a separate job:
   integration-tests:
     runs-on: ubuntu-latest
     services:
       postgres: (same as above)
     steps: run migrations, then pytest tests/integration/
```

### N-02: Render cold-start mitigation

```
The backend on Render free tier has 3-5 minute cold starts.

Options (implement the simplest):
1. Add a cron health ping using GitHub Actions:
   Create .github/workflows/keepalive.yml:
   name: Keep API alive
   on:
     schedule:
       - cron: '*/14 * * * *'  # Every 14 minutes (Render spins down after 15)
   jobs:
     ping:
       runs-on: ubuntu-latest
       steps:
         - run: curl -sf https://your-api.onrender.com/api/v1/health/live || true

2. Alternative: Use UptimeRobot (free, 5-min intervals) to ping /api/v1/health/live

The health endpoint is already at /api/v1/health/live (returns {"status": "ok"}).
Update the URL in the workflow to match your Render deployment URL from render.yaml.
```

### N-03: Frontend E2E tests (Playwright)

```
Set up Playwright for browser-level E2E testing. No E2E tests exist yet.

1. Install Playwright in apps/web/:
   cd apps/web && npm install -D @playwright/test && npx playwright install

2. Create apps/web/playwright.config.ts:
   - baseURL: process.env.E2E_BASE_URL || "http://localhost:3000"
   - testDir: "./e2e"
   - use: { headless: true, screenshot: "only-on-failure" }

3. Create initial E2E tests in apps/web/e2e/:

   a) auth.spec.ts:
      - Visit / → should redirect to /login
      - Visit /login → should show login form with email and password fields
      - Submit invalid credentials → should show error message

   b) navigation.spec.ts (requires auth mock or test account):
      - After login → should show baselines page
      - Navigate to /dashboard → should render dashboard
      - Navigate to /runs → should render runs list

4. Add "e2e" script to package.json: "e2e": "playwright test"
5. Add to .github/workflows/ci.yml as a separate job (needs Next.js dev server running)

Note: E2E tests require either a running backend or comprehensive MSW (Mock Service Worker) mocks. Start with MSW for CI reliability.
```

### N-04: API rate-limit testing

```
The security middleware at apps/api/app/middleware/security.py has rate limiting via slowapi, but no tests exercise it.

Create tests/unit/test_rate_limiting.py:

1. Read apps/api/app/middleware/security.py to understand the rate limit configuration
2. Read apps/api/app/core/settings.py for the rate_limit setting (default: "100/minute")

Test cases:
- test_rate_limit_allows_normal_traffic: Send 5 requests → all return 200
- test_rate_limit_returns_429: Override rate_limit to "2/minute", send 3 requests → third returns 429
- test_rate_limit_per_tenant: Verify different X-Tenant-ID headers have separate limits
- test_rate_limit_header_present: Verify X-RateLimit-Remaining header in response

Use FastAPI TestClient with the app from apps/api/app/main.py.
Mock settings to use a low rate limit ("2/minute") for testing.
Follow the existing test pattern in tests/unit/.
```

### N-05: OpenAPI schema validation tests

```
Create tests that validate the FastAPI OpenAPI schema matches actual endpoint behavior.

Create tests/unit/test_openapi_schema.py:

1. Import the app and get the OpenAPI schema:
   from apps.api.app.main import app
   client = TestClient(app)
   schema = client.get("/openapi.json").json()

2. Test cases:
   - test_openapi_schema_valid: Validate schema against OpenAPI 3.x spec
   - test_all_routers_documented: Check every mounted router has paths in the schema
   - test_response_schemas_match: For key endpoints (baselines, runs, budgets), verify response matches documented schema
   - test_no_undocumented_endpoints: Compare app.routes against schema paths

3. Optional: Generate TypeScript types from the OpenAPI schema:
   - Install openapi-typescript: cd apps/web && npm install -D openapi-typescript
   - Add script: "generate-types": "npx openapi-typescript http://localhost:8000/openapi.json -o lib/api-types.ts"
   - This auto-generates TypeScript interfaces matching the API

pip install openapi-spec-validator for schema validation.
```

### N-06: Performance/load test expansion

```
Expand the existing load tests at tests/load/test_engine_performance.py to cover API-level performance.

Create tests/load/test_api_performance.py:

1. Use the existing test infrastructure (pytest, TestClient)
2. Test cases with timing assertions:
   - test_baseline_list_performance: GET /baselines with 100 baselines → P95 < 200ms
   - test_run_execution_performance: POST /runs with standard model → P95 < 2s
   - test_statements_retrieval_performance: GET /runs/{id}/statements → P95 < 500ms
   - test_concurrent_requests: 10 parallel requests to /baselines → all complete < 1s

3. Mock the database layer (tenant_conn) but test the full router→service pipeline
4. Use time.perf_counter() for measurements, run each test 10 times
5. Mark with @pytest.mark.performance so they can be skipped in CI:
   @pytest.mark.performance
   def test_baseline_list_performance():
       times = []
       for _ in range(10):
           start = time.perf_counter()
           r = client.get("/api/v1/baselines", headers=headers)
           times.append(time.perf_counter() - start)
       p95 = sorted(times)[int(len(times) * 0.95)]
       assert p95 < 0.2, f"P95 latency {p95:.3f}s exceeds 200ms"

Add to conftest.py: pytest.ini marker for performance tests.
```

### N-07: Monitoring & alerting (Sentry)

```
Add Sentry for error tracking and performance monitoring.

Backend (FastAPI):
1. Add sentry-sdk[fastapi] to pyproject.toml dependencies
2. Add to apps/api/app/core/settings.py:
   sentry_dsn: str | None = Field(default=None, alias="SENTRY_DSN")
3. In apps/api/app/main.py, after creating the app:
   if settings.sentry_dsn:
       import sentry_sdk
       from sentry_sdk.integrations.fastapi import FastApiIntegration
       sentry_sdk.init(
           dsn=settings.sentry_dsn,
           integrations=[FastApiIntegration()],
           traces_sample_rate=0.1,
           environment=settings.environment,
       )
4. Add SENTRY_DSN to .env.example and render.yaml

Frontend (Next.js):
1. cd apps/web && npm install @sentry/nextjs
2. Run: npx @sentry/wizard@latest -i nextjs
3. This creates sentry.client.config.ts, sentry.server.config.ts, sentry.edge.config.ts
4. Add NEXT_PUBLIC_SENTRY_DSN to .env.example and vercel.json env

Don't add actual DSN values — leave as empty/placeholder for the user to configure.
```

### N-08: CI pipeline enhancements

```
Enhance the GitHub Actions CI pipeline at .github/workflows/ci.yml.

Current CI: lint + pytest + integration tests
Add these jobs:

1. Frontend tests job:
   frontend-tests:
     runs-on: ubuntu-latest
     defaults:
       run:
         working-directory: apps/web
     steps:
       - uses: actions/checkout@v4
       - uses: actions/setup-node@v4
         with: { node-version: 20 }
       - run: npm ci
       - run: npx vitest run
       - run: npx tsc --noEmit

2. Docker image scan job:
   docker-scan:
     runs-on: ubuntu-latest
     steps:
       - uses: actions/checkout@v4
       - run: docker build -t va-api .
       - uses: aquasecurity/trivy-action@master
         with:
           image-ref: va-api
           severity: HIGH,CRITICAL
           exit-code: 1

3. TypeScript check (already in frontend-tests but also useful standalone):
   Add `npx tsc --noEmit` to the frontend step

4. Dependency audit:
   Add `npm audit --audit-level=high` to frontend step
   Add `pip-audit` to backend step (install pip-audit first)

Read the existing ci.yml first to understand the current structure and add these as new jobs.
```

---

## Summary: Effort Estimates

| Tier | Items | Total Effort |
|------|-------|-------------|
| Tier 1 (Ship Blockers) | S-01, S-02 | 30 min |
| Tier 2 (High Priority) | H-02, H-03, H-04 | 3-5 days |
| Tier 3 (Medium Priority) | M-01 through M-05 | 1-2 days |
| Tier 4 (Nice to Have) | N-01 through N-08 | 3-5 days |

**Recommended order:** S-01 → S-02 → H-02 → H-04 → H-03 → M-01 → M-02 → M-03 → M-04 → M-05 → N-08 → N-01 → N-04 → N-07 → N-02 → N-05 → N-06 → N-03
