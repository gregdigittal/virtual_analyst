# Virtual Analyst v1 — Remaining Backlog Tasks

Generated from `VIRTUAL_ANALYST_BACKLOG.md`. Items marked **— DONE** in the main backlog are omitted here.

**Complexity:** S &lt;1d | M 1–3d | L 3–7d | XL 7–14d

---

## Phase 5 — Excel + Memos + Collaboration

| ID | Complexity | Summary |
|----|------------|--------|
| VA-P5-01 | L | Excel export + live links API — export, connection management — DONE |
| VA-P5-02 | L | Office.js add-in — Auth, bindings, pull/push workflows |
| VA-P5-03 | M | Memo pack generator — HTML/PDF outputs from runs — DONE |

---

## Phase 6 — Team Collaboration & Workflow Engine

| ID | Complexity | Summary |
|----|------------|--------|
| VA-P6-03 | L | Workflow template engine — workflow_templates, workflow_instances, stage rules, seed templates — DONE |
| VA-P6-04 | L | Task assignment system — create/claim/submit, deadlines — DONE |
| VA-P6-05 | L | Review & correction pipeline — reviews, change_summaries, approve/return/reject — DONE |
| VA-P6-06 | M | Learning feedback system — review_summary LLM, acknowledgment |
| VA-P6-07 | M | Workflow notifications — task/review/deadline events, email templates |
| VA-P6-08 | M | Team management UI — /settings/teams, hierarchy tree, job functions — DONE |
| VA-P6-09 | L | Task inbox UI — /inbox, assignment cards, create wizard — DONE |
| VA-P6-10 | L | Review workspace UI — /inbox/{id}/review, methodology, change tracking — DONE |
| VA-P6-11 | M | Learning feedback UI — /inbox/feedback, diffs, acknowledge |
| VA-P6-12 | L | Test suite — Phase 6 (teams, workflow, assignments, reviews, integration) |

---

## Phase 7 — Budgeting & Board Pack

| ID | Complexity | Summary |
|----|------------|--------|
| VA-P7-01 | M | Budget data model & migrations — budgets, line items, versions, RLS |
| VA-P7-02 | L | Budget CRUD & department allocation API — line items, departments, clone |
| VA-P7-03 | M | Budget templates & LLM-assisted seeding — templates, budget_initialization |
| VA-P7-04 | L | Actuals import & variance analysis engine — variance, drill-down |
| VA-P7-05 | M | Rolling forecast engine — reforecast, actuals lock, LLM projection |
| VA-P7-06 | M | Budget approval workflow integration — workflow template, CFO approval |
| VA-P7-07 | L | Board pack composer — sections, LLM narrative, branding |
| VA-P7-08 | L | Board pack export — PDF/PPTX/HTML, charts |
| VA-P7-09 | M | Board pack scheduling & distribution — recurring, email, history |
| VA-P7-10 | L | Budget & board pack UI — budgets, variance, reforecast, board-packs |
| VA-P7-11 | M | Budget KPI dashboard — burn rate, runway, alerts, CFO view |
| VA-P7-12 | L | Test suite — Phase 7 (budgets, variance, reforecast, board pack, workflow) |

---

## Post-Launch (v1.1+)

- Multi-currency and FX overlays  
- SSO/SAML (enterprise)  
- Template marketplace  
- Connector marketplace and QuickBooks adapter  
- Cross-team workflow routing (multi-team approval chains)  
- Workflow analytics dashboard (cycle times, review rates, bottlenecks)  
- AI-assisted review suggestions (flag unusual assumptions)  
- Peer comparison (anonymous benchmarking)  
- Board pack benchmarking (industry median)  
- Natural language budget queries (e.g. “which department is over budget?”)

---

## Summary counts

| Phase | Remaining |
|-------|-----------|
| P5 | 1 |
| P6 | 4 |
| P7 | 12 |
| Post-launch | 10 themes |
| **Total (numbered)** | **18** |
