# Virtual Analyst — State Review & Build Plan Prompt
> Version: 1.0 · Created: 2026-03-17
> Usage: paste into a fresh Claude Code session, or invoke as `/goal --supervised [this document]`

---

## MISSION

You are the chief architect for the Virtual Analyst project. Before proposing any plan,
conduct a **live codebase audit** to establish actual state — do not trust documentation alone.
Prior planning sessions have been burned by stale docs that described work as open when it
was already shipped. Ground truth is the code, not BACKLOG.md.

Your deliverable is a sequenced, dependency-ordered build plan for all remaining work,
with clear rationale for ordering and an honest assessment of what is genuinely done vs.
genuinely open.

---

## STEP 1 — LOAD CONTEXT (read these files first)

Read in this order:

1. `BACKLOG.md` — sprint history and open item list
2. `CONTEXT.md` — architecture snapshot and recent changes
3. `CLAUDE.md` — project configuration and env vars
4. `docs/plans/2026-03-16-product-completion-prompt.md` — Sprint 9 plan (may or may not be executed)
5. `docs/plans/2026-03-09-pim-v2-build-plan.md` — PIM build plan with FR-1 through FR-7 spec

Do NOT read every file in `docs/plans/` — only the ones above.

---

## STEP 2 — LIVE CODEBASE AUDIT

For each item group below, check actual file existence and content — do not assume documentation
is accurate. Record your finding as ✅ Done, ⚠️ Partial, or ❌ Open.

### A. Navigation & Help Content

| Check | How to verify |
|-------|--------------|
| VASidebar.tsx has INTELLIGENCE group with 7 PIM items | Read `apps/web/components/VASidebar.tsx` — look for `key: "intelligence"` or similar |
| VASidebar.tsx has standalone AFS group (not just "AFS Import" under SETUP) | Same file — look for `key: "afs"` group with Engagements + Frameworks items |
| instructions-config.ts has PIM chapters (ch27–34) | Read `apps/web/lib/instructions-config.ts` — search for `/pim` keys |

### B. Documentation & Environment

| Check | How to verify |
|-------|--------------|
| CONTEXT.md header is 2026-03-16 or later | Read `CONTEXT.md` header line |
| CONTEXT.md PIM section shows all 7 sprints ✅ | Read `CONTEXT.md` PIM Module Status section |
| `.env.example` has POLYGON_API_KEY and FRED_API_KEY | Read `.env.example` |
| `CLAUDE.md` optional vars table has both PIM keys | Read `CLAUDE.md` optional vars table |

### C. DTF (Developer Testing Framework)

| Check | How to verify |
|-------|--------------|
| `tools/dtf/calibrate.py` exists | Glob `tools/dtf/*.py` |
| `tools/dtf/weekly_validator.py` exists | Same glob |
| DTF unit tests exist | Glob `tests/unit/test_dtf_*.py` |
| Tests pass | Run `pytest tests/unit/test_dtf_*.py -v --tb=short` (skip if files don't exist) |

### D. Excel Add-in

| Check | How to verify |
|-------|--------------|
| `taskpane.js` Pull handler writes cell values via `Excel.run` | Read `apps/excel-addin/taskpane.js` — look for `Excel.run` in `onPull` |
| `taskpane.js` Push handler reads cell values before sending | Same file — `onPush` should populate `changes[]` from Excel cells |
| Connection dropdown exists | Read `apps/excel-addin/taskpane.html` — look for `<select id="connectionSelect">` |

### E. PIM Module Completeness

| Check | How to verify |
|-------|--------------|
| All 8 PIM routers present | Glob `apps/api/app/routers/pim_*.py` — expect: pim_sentiment, pim_universe, pim_cis, pim_markov, pim_portfolio, pim_backtest, pim_pe, pim_peer |
| CIS response includes `ci_lower`/`ci_upper` fields | Read `apps/api/app/routers/pim_cis.py` — search for `ci_lower` |
| Markov steady-state response includes CI fields | Read `apps/api/app/routers/pim_markov.py` — search for `ci_lower` |
| PIM pages exist in frontend | Glob `apps/web/app/(app)/pim/*/page.tsx` |

### F. AFS Module Completeness

| Check | How to verify |
|-------|--------------|
| AFS router package exists (not monolithic file) | Glob `apps/api/app/routers/afs/*.py` |
| All 6 phase migrations exist | Glob `apps/api/app/db/migrations/005*.sql` |
| AFS frontend pages exist | Glob `apps/web/app/(app)/afs/*/page.tsx` |

### G. Test Health

Run the fast gate and record results:
```bash
cd /home/gregmorris/projects/virtual_analyst

# Python (30-60 seconds)
ruff check . 2>&1 | tail -5
mypy apps/ shared/ 2>&1 | tail -5
pytest tests/unit/ tests/golden/ -v --tb=short -q 2>&1 | tail -10

# Frontend (30-60 seconds)
cd apps/web && npm run type-check 2>&1 | tail -5 && npm run test -- --reporter=verbose 2>&1 | tail -10
```

Record: pass counts, fail counts, any errors. Do NOT proceed with planning if there are
test failures or type errors — address them first.

---

## STEP 3 — AUDIT FINDINGS SUMMARY

After completing Step 2, produce a findings table:

```
| Item | Documented State | Actual State | Delta |
|------|-----------------|--------------|-------|
| VASidebar INTELLIGENCE group | ❓ (Sprint 9 planned) | ✅/⚠️/❌ | ... |
| ... | ... | ... | ... |
```

Be explicit about any discrepancy between what BACKLOG.md claims and what the code shows.
Flag any items where documentation says "done" but evidence is thin.

---

## STEP 4 — IDENTIFY REMAINING WORK

Based purely on the audit findings (not documentation), list every open or partial item.
For each item include:

- **What is missing**: concrete description of the gap
- **Impact**: who is blocked and how badly (user-facing vs. internal)
- **Effort estimate**: XS (< 1h) / S (1-4h) / M (half-day) / L (full day) / XL (multi-day)
- **Dependencies**: what must be done before this item can start

Do NOT include items that the live audit confirms are complete.

---

## STEP 5 — BUILD PLAN

### 5a. Dependency Graph

Draw a dependency graph for all open items. Identify:
- Items with no dependencies (can start immediately)
- Items blocked on one other item
- Items blocked on multiple items
- Items that are blocking many other items (critical path)

### 5b. Sequenced Sprint Plan

Group open items into sprints. Apply these ordering principles:

**Principle 1 — User-facing blockers first**
If a feature is built but inaccessible to users (e.g. missing navigation), fix navigation before
adding more features. A user who can't reach the page can't use anything built for it.

**Principle 2 — Infrastructure before features**
Broken CI, failing tests, or type errors block all other work. Fix these in sprint 0 if any exist.

**Principle 3 — Parallelise where safe**
Group items with no file overlap into parallel streams. Assign each stream a clear file ownership
list. Flag high-conflict files (touched by multiple streams) and assign them to one stream only.

**Principle 4 — Defer non-blocking polish**
InstructionsDrawer content, documentation updates, and developer tooling (DTF) can run parallel
to product work but should not delay user-facing items.

**Principle 5 — Billing is explicitly out of scope**
Do not include Stripe/billing verification in any sprint. It is post-beta by product decision.

### 5c. Sprint Table Format

For each sprint, produce:

```markdown
## Sprint N — [Name] (estimated: X days)

**Goal:** [one sentence]

| ID | Title | Stream | Depends on | Effort | Parallel with |
|----|-------|--------|------------|--------|---------------|
| SPN-A1 | ... | A (agent-type) | — | S | SPN-B1 |
| SPN-B1 | ... | B (agent-type) | — | M | SPN-A1 |
| SPN-Z  | Fast gate + commit | — | all above | XS | — |

**Acceptance criteria:**
- [ ] ...
```

### 5d. Critical Path

State the critical path explicitly:
```
Sprint N critical path: [Task A] → [Task B] → [Task C]
Reason: Task A is the largest single task; B and C depend on it.
Total serial work: ~X hours
```

### 5e. Post-Sprint Backlog

List any items that are intentionally deferred (low priority, blocked on external decisions,
or billing-related). Be explicit about why each is deferred.

---

## STEP 6 — SAVE OUTPUTS

1. Write the build plan to `docs/plans/YYYY-MM-DD-build-plan.md` using today's date
2. Update `BACKLOG.md`:
   - Add a "Current Sprint" section at the top reflecting the first sprint from your plan
   - Update the "Current Status" table header date to today
   - Do NOT delete the existing completed rounds archive
3. Update `CONTEXT.md` if the audit found it materially out of date:
   - Only update the sections where the audit found discrepancies
   - Update the header date

---

## CONSTRAINTS

- Do NOT propose work that the live audit confirms is already done
- Do NOT propose billing/Stripe work — it is explicitly out of scope until post-beta
- Do NOT propose architectural changes — the architecture is stable; this is completion work
- Do NOT propose new features beyond what is in the existing backlog and design specs
- Every sprint must end with a fast gate run (`ruff + mypy + pytest unit/golden + vitest + tsc`)
- Maximum 4 parallel agent streams per sprint
- Maximum 10 tasks per sprint before requiring a checkpoint
- Each stream must have exclusive ownership of the files it touches

---

## SUCCESS CRITERIA FOR THIS PROMPT

This prompt succeeds when you produce:

1. ✅ An audit findings table that distinguishes documented state from actual state
2. ✅ A complete list of genuinely open items with effort estimates and dependencies
3. ✅ A sprint plan where each sprint has: goal, task table, parallel stream assignments, acceptance criteria
4. ✅ An explicit critical path for each sprint
5. ✅ A deferred backlog with rationale
6. ✅ The plan saved to `docs/plans/` and BACKLOG.md updated
