# Virtual Analyst — Enhancement Build Plan (Round 23)

> 10 enhancements, sequenced for dependency order and incremental value delivery.
> Each prompt is self-contained with context saves and verification steps.

## Sequencing Rationale

```
Phase 1 — Quick wins (no dependencies)
  P1  Run Excel Export button             (S)   ~15 min
  P2  Scenario Creation form              (S)   ~20 min

Phase 2 — Core analytical capabilities
  P3  Run Creation with MC/Scenario opts  (M)   ~30 min  (uses scenarios from P2)
  P4  Changesets UI — model version ctrl  (M)   ~45 min

Phase 3 — Dashboards & visualisation
  P5  Activity Dashboard (replaces perf)  (M)   ~30 min
  P6  Budget Dashboard Charts             (M)   ~30 min

Phase 4 — Comparison & workflows
  P7  Run-vs-Run Comparison               (M)   ~30 min  (uses runs from P3)
  P8  Workflow Management UI              (M)   ~35 min

Phase 5 — Advanced model management
  P9  Baseline Version History & Diff     (M)   ~40 min  (uses changesets from P4)
  P10 Baseline Config Editor              (L)   ~60 min  (uses version history from P9)
```

## Prompt Files

| # | File | Status |
|---|------|--------|
| P1 | `CURSOR_PROMPT_P1_RUN_EXCEL_EXPORT.md` | Frontend only |
| P2 | `CURSOR_PROMPT_P2_SCENARIO_CREATION.md` | Frontend only |
| P3 | `CURSOR_PROMPT_P3_RUN_CREATION_OPTIONS.md` | Frontend only |
| P4 | `CURSOR_PROMPT_P4_CHANGESETS_UI.md` | Frontend: 3 new pages + nav |
| P5 | `CURSOR_PROMPT_P5_ACTIVITY_DASHBOARD.md` | Frontend: rewrite dashboard |
| P6 | `CURSOR_PROMPT_P6_BUDGET_CHARTS.md` | Frontend only |
| P7 | `CURSOR_PROMPT_P7_RUN_COMPARISON.md` | Frontend only |
| P8 | `CURSOR_PROMPT_P8_WORKFLOW_UI.md` | Frontend: 2 new pages + nav |
| P9 | `CURSOR_PROMPT_P9_BASELINE_VERSIONS.md` | Frontend + minor backend |
| P10 | `CURSOR_PROMPT_P10_BASELINE_CONFIG_EDITOR.md` | Frontend + schema read |

## Shared Conventions (applied across all prompts)

- **Auth pattern:** `getAuthContext()` → `router.replace("/login")` on null → `api.setAccessToken(ctx.accessToken)` → `setTenantId(ctx.tenantId)`
- **Design system:** `VAButton`, `VACard`, `VAInput`, `VASelect`, `VASpinner`, `VAPagination`, `useToast` from `@/components/ui`
- **Middleware:** Add new routes to `protectedPaths` array in `apps/web/middleware.ts` AND `matcher` array
- **Navigation:** Add new nav links to `navLinks` array in `apps/web/components/nav.tsx`
- **Error handling:** `try/catch` with `setError(e instanceof Error ? e.message : String(e))`
- **Toast:** Success/error feedback via `const { toast } = useToast()` → `toast.success()` / `toast.error()`

## Context Save Protocol

After each prompt completes, verify and save:

```bash
# 1. TypeScript check
npx tsc --noEmit --project apps/web/tsconfig.json

# 2. Commit
git add -A && git commit -m "Enhancement P[N]: [description]"

# 3. Push
git push
```

## Verification Checklist (per prompt)

- [ ] New pages load without crash
- [ ] Auth guard works (redirect to /login if unauthenticated)
- [ ] API calls use correct tenant/user context
- [ ] Design system components used (no raw HTML buttons/inputs)
- [ ] Error states handled and displayed
- [ ] Loading spinners shown during async operations
- [ ] TypeScript compiles with zero errors
- [ ] New routes added to middleware matcher + protectedPaths
