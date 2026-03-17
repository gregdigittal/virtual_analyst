# Sprint 9 — Product Completion Execution Plan
> Generated: 2026-03-16 · Mode: supervised
> Goal: Close all remaining product gaps before beta user testing (billing deferred)

---

## Executive Summary

7 product gaps identified. 4 parallel agent streams + 1 sequential follow-up + 1 commit task.
Total: 6 tasks. Estimated wall-clock: ~2 hours with all streams running simultaneously.

| Gap | Stream | Task | Effort |
|---|---|---|---|
| AFS sidebar wrong ("AFS Import"), no sub-pages | A | SP9-A1 | S |
| PIM not in sidebar (7 pages inaccessible) | A | SP9-A1 | S |
| PIM has no InstructionsDrawer help | A | SP9-A2 (after A1) | M |
| CONTEXT.md 7 days stale | B | SP9-B | S |
| POLYGON_API_KEY + FRED_API_KEY undocumented | B | SP9-B | S |
| DTF not built (Markov integrity monitoring) | C | SP9-C | L |
| Excel add-in Push/Pull broken | D | SP9-D | M |

---

## Task List

| ID | Title | Stream | Agent | Depends on | Parallel with | Effort |
|---|---|---|---|---|---|---|
| SP9-A1 | VASidebar: AFS group + INTELLIGENCE group | A | frontend-builder | — | SP9-B, SP9-C, SP9-D | S |
| SP9-B | Docs: CONTEXT.md + .env.example + CLAUDE.md | B | general-purpose | — | SP9-A1, SP9-C, SP9-D | S |
| SP9-C | DTF-A calibrate.py + DTF-B weekly_validator.py + tests | C | general-purpose | — | SP9-A1, SP9-B, SP9-D | L |
| SP9-D | Excel add-in: fix Pull/Push + connection dropdown | D | general-purpose | — | SP9-A1, SP9-B, SP9-C | M |
| SP9-A2 | InstructionsDrawer: 8 PIM chapters (ch27–34) | A | frontend-builder | SP9-A1 | — | M |
| SP9-Z | Fast gate + BACKLOG update + commit | — | — | all above | — | S |

**Execution order:**
- Round 1 (parallel): SP9-A1, SP9-B, SP9-C, SP9-D
- Round 2 (sequential): SP9-A2 (after SP9-A1 confirmed complete)
- Round 3: SP9-Z (after all above)

---

## File Ownership (no concurrent edits)

| File | Owner | Reason |
|---|---|---|
| `apps/web/components/VASidebar.tsx` | SP9-A1 only | Single nav data structure |
| `apps/web/lib/instructions-config.ts` | SP9-A2 only | Single INSTRUCTIONS_MAP object |
| `CONTEXT.md` | SP9-B only | Prose document |
| `.env.example` | SP9-B only | Env reference |
| `CLAUDE.md` | SP9-B only | Project config |
| `tools/dtf/*` | SP9-C only | New directory |
| `tests/unit/test_dtf_*.py` | SP9-C only | New test files |
| `apps/excel-addin/taskpane.js` | SP9-D only | Add-in JS |
| `apps/excel-addin/taskpane.html` | SP9-D only | Add-in HTML |

---

## Acceptance Criteria

- [ ] `npm run type-check` passes — VASidebar.tsx has AFS (2) + INTELLIGENCE (7) groups
- [ ] `npm run type-check` passes — instructions-config.ts has ch27–34 PIM entries
- [ ] CONTEXT.md header: 2026-03-16, PIM section: all ✅
- [ ] `.env.example`: POLYGON_API_KEY + FRED_API_KEY present
- [ ] `ruff check tools/dtf/` + `mypy tools/dtf/`: pass
- [ ] `pytest tests/unit/test_dtf_*.py`: 6+ tests pass
- [ ] Excel add-in: Pull writes cells, Push sends non-empty changes[], dropdown works
- [ ] Fast gate: ruff + mypy + pytest dtf + vitest + tsc all pass
- [ ] BACKLOG.md Sprint 9 row committed

---

## Risk Register

| Risk | Mitigation |
|---|---|
| NavIcon doesn't support `brain`/`cpu`/`bar-chart-2` | Read NavIcon.tsx first; fall back to `zap`/`layers`/`trending-up` |
| DTF Markov table name differs from spec | Read pim_markov.py + migrations before writing queries |
| Excel add-in `Excel.run` unavailable outside Office context | Wrap in try/catch; degrade gracefully if not in Office |
| instructions-config.ts TypeScript strict errors | Follow exact interface shape from existing entries |
