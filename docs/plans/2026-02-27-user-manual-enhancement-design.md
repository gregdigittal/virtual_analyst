# User Manual Enhancement — Design Document

**Date:** 2026-02-27
**Status:** Approved
**Scope:** Comprehensive rewrite of all 19 existing chapters + 4 new chapters + glossary expansion

---

## Goal

Enhance the Virtual Analyst user manual to:
1. Fix the README.md table of contents (currently out of sync with actual files)
2. Reorganize chapters to mirror the sidebar navigation groups
3. Add 4 missing chapters (Marketplace, Excel Connections, Changesets, Ventures)
4. Rewrite every chapter with a consistent template including process flows, troubleshooting, and quick-reference checklists
5. Expand thin chapters (Entity Comparison, etc.)

---

## Chapter Structure (26 chapters + glossary)

### GETTING STARTED
| # | Chapter | File | Status |
|---|---------|------|--------|
| 01 | Getting Started | `01-getting-started.md` | Rewrite |
| 02 | Dashboard | `02-dashboard.md` | Rewrite |

### SETUP (Data In)
| # | Chapter | File | Status |
|---|---------|------|--------|
| 03 | Marketplace | `03-marketplace.md` | Rewrite (was embedded in import chapter) |
| 04 | Data Import (Excel + CSV) | `04-data-import.md` | Rewrite |
| 05 | Excel Live Connections | `05-excel-connections.md` | **NEW** |
| 06 | AFS Module | `06-afs-module.md` | Rewrite (was Ch. 10) |
| 07 | AFS Review and Tax | `07-afs-review-and-tax.md` | Rewrite (was Ch. 11) |
| 08 | AFS Consolidation and Output | `08-afs-consolidation-and-output.md` | Rewrite (was Ch. 12) |
| 09 | Org Structures | `09-org-structures.md` | Rewrite (was Ch. 19) |

### CONFIGURE
| # | Chapter | File | Status |
|---|---------|------|--------|
| 10 | Baselines | `10-baselines.md` | Rewrite (was Ch. 4 combined) |
| 11 | Drafts | `11-drafts.md` | Rewrite (split from Ch. 4) |
| 12 | Scenarios | `12-scenarios.md` | Rewrite (split from Ch. 5) |
| 13 | Changesets | `13-changesets.md` | **NEW** |

### ANALYZE
| # | Chapter | File | Status |
|---|---------|------|--------|
| 14 | Runs | `14-runs.md` | Rewrite (was Ch. 5/8) |
| 15 | Monte Carlo and Sensitivity | `15-monte-carlo-and-sensitivity.md` | Rewrite (was Ch. 6) |
| 16 | Valuation | `16-valuation.md` | Rewrite (was Ch. 7) |
| 17 | Budgets | `17-budgets.md` | Rewrite (was Ch. 8) |
| 18 | Covenants | `18-covenants.md` | Rewrite (was Ch. 14) |
| 19 | Benchmarking and Competitor Analysis | `19-benchmarking.md` | Rewrite + expand (was Ch. 16) |
| 20 | Entity Comparison | `20-entity-comparison.md` | Rewrite + expand (was Ch. 17) |
| 21 | Ventures | `21-ventures.md` | **NEW** |

### COLLABORATE & REPORT
| # | Chapter | File | Status |
|---|---------|------|--------|
| 22 | Workflows, Tasks, and Inbox | `22-workflows-and-tasks.md` | Rewrite (was Ch. 13) |
| 23 | Board Packs | `23-board-packs.md` | Rewrite (was Ch. 9) |
| 24 | Memos and Documents | `24-memos-and-documents.md` | Rewrite (from Ch. 15) |
| 25 | Collaboration | `25-collaboration.md` | Rewrite (was Ch. 15) |

### ADMIN
| # | Chapter | File | Status |
|---|---------|------|--------|
| 26 | Settings and Administration | `26-settings-and-admin.md` | Rewrite (was Ch. 18) |
| A | Glossary | `appendix-a-glossary.md` | Rewrite + expand |

---

## Chapter Template

Every chapter follows this structure:

```
# Chapter Title

## Overview
Brief description of the feature and when you'd use it.

## Process Flow
Mermaid flowchart showing the primary workflow.

## Key Concepts
Definitions specific to this feature (linked to glossary).

## Step-by-Step Guide
Numbered walkthrough of the primary workflow.

## [Feature-Specific Sections]
Deeper dives into sub-features, configuration options, etc.

## Quick Reference
Checklist or table summarizing key actions at a glance.

## Troubleshooting
Common issues, error messages, and resolutions (3-5 items per chapter).

## Related Chapters
Cross-references to related features.
```

### Requirements per chapter:
- At least 2 Mermaid diagrams (one high-level process flow, one sub-workflow)
- Troubleshooting table with 3-5 common issues and resolutions
- Quick-reference checklist summarizing key actions
- Cross-references to related chapters
- Target length: 250-400 lines per chapter

---

## README.md Rewrite

The README will be rewritten to:
- Match the actual chapter files on disk
- Organize the table of contents by sidebar nav groups
- Update the quick-start checklist
- Update the Mermaid platform overview flow
- Add a "What's New" section for recently added features

---

## Implementation Strategy

### Phase 1: Scaffolding
- Delete old chapter files
- Create new file structure with all 27 files (26 chapters + glossary)
- Write the new README.md with correct TOC

### Phase 2: Rewrite Existing Chapters (22 chapters)
- Rewrite each chapter using the template
- Incorporate content from existing chapters where still accurate
- Add missing sections (troubleshooting, quick-reference, etc.)
- Verify process flow diagrams match current app behavior

### Phase 3: Write New Chapters (4 chapters)
- 05-excel-connections.md — from `apps/api/app/routers/excel.py` + `apps/web/app/(app)/excel-connections/page.tsx`
- 03-marketplace.md — from `apps/api/app/routers/marketplace.py` + `apps/web/app/(app)/marketplace/page.tsx`
- 13-changesets.md — from `apps/api/app/routers/changesets.py` + `apps/web/app/(app)/changesets/page.tsx`
- 21-ventures.md — from `apps/api/app/routers/ventures.py` + `apps/web/app/(app)/ventures/page.tsx`

### Phase 4: Glossary + Final Review
- Expand glossary with new terms from added chapters
- Cross-check all chapter cross-references
- Verify all Mermaid diagrams render correctly

---

## Source Material

Each chapter will be written by reading:
1. The existing chapter content (where applicable)
2. The frontend page component(s) for that feature
3. The backend API router(s) for that feature
4. Any relevant design docs in `docs/plans/`

This ensures documentation matches actual application behavior.
