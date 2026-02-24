# AFS Module — Annual Financial Statement Generation

> Design Document | 2026-02-24
> Status: Approved for backlog

---

## Overview

A comprehensive Annual Financial Statements (AFS) generation module for Virtual Analyst that combines traditional financial reporting automation with AI-powered disclosure drafting. The module analyses prior-year statements, allows users to describe updates in natural language, and generates complete draft financial statements compliant with the user's chosen accounting framework.

**Key differentiator:** AI-first approach — LLM + RAG generates disclosure text from natural language instructions with the applicable standard as context, unlike template-only tools (Caseware, Workiva, Silverfin).

---

## Research: Competitive Landscape

| Tool | Strengths | Gaps (that VA fills) |
|------|-----------|----------------------|
| **Caseware Africa** | IFRS/IPSAS templates, 60+ accounting package imports, iXBRL for CIPC, roll-forward, consolidation | No AI drafting, template-bound, no NL interaction |
| **Workiva** | Real-time co-authoring, SEC compliance, audit trails, 90% automation once connected | US-focused, no AI disclosure generation, expensive |
| **Silverfin** | Cloud-native, analytics/KPIs, bookkeeping integration | Limited to EU/UK standards, no AFS generation |
| **EY/KPMG Checklists** | Authoritative IFRS disclosure checklists | Manual — no automation, no statement generation |

---

## Architecture: 7 Sub-Modules

### 1. AFS Framework Engine

Manages accounting standards, disclosure checklists, and statement templates.

**Capabilities:**
- Pre-built frameworks: IFRS (full), IFRS for SMEs, US GAAP, SA Companies Act / GAAP
- Custom frameworks: user uploads own disclosure checklist + statement templates
- AI-inferred frameworks: user describes jurisdiction/requirements in natural language, AI builds a framework dynamically using RAG over IFRS/GAAP knowledge base
- Regulatory updates: framework version management — when standards update (e.g., IFRS 18 replacing IAS 1), system flags affected statements and disclosure notes
- Interactive disclosure checklist per framework, tracking which disclosures are applicable, completed, or N/A

**Data model:**
- `afs_frameworks` — id, name, standard (ifrs/gaap/custom), version, jurisdiction, disclosure_schema_json, statement_templates_json, created_by, tenant_id
- `afs_disclosure_items` — id, framework_id, section, reference (e.g. "IAS 1.10"), description, required (bool), applicable_entity_types

### 2. Data Ingestion & Mapping

Imports financial data and maps to the standard chart of accounts.

**Capabilities:**
- Sources: VA baselines/runs (internal), Excel/CSV trial balance upload, Xero/QuickBooks via existing connectors
- Account mapping: map trial balance accounts to standard chart of accounts for the selected framework. AI-assisted mapping suggestions based on account names
- Multi-entity consolidation: aggregate trial balances from multiple entities, intercompany elimination, minority interest calculations, currency translation
- Roll-forward: auto-populate comparatives from prior period, carry forward prior-year disclosure notes with flags for required updates

**Data model:**
- `afs_engagements` — id, tenant_id, entity_name, framework_id, period_start, period_end, prior_engagement_id, status, created_by
- `afs_trial_balances` — id, engagement_id, entity_id, source (va_baseline/upload/connector), data_json, mapped_accounts_json
- `afs_consolidation_rules` — id, engagement_id, parent_entity_id, child_entity_id, ownership_pct, elimination_rules_json

### 3. AI Disclosure Drafter

The core AI-powered module that analyses prior AFS and generates new disclosures.

**Capabilities:**
- Prior AFS analysis: upload prior-year AFS (PDF → AI extraction, or structured Excel). System identifies each section, note, and disclosure
- Section-by-section NL prompting: for each section/note, user describes in natural language what has changed (e.g., "We adopted IFRS 16 this year, add the transition disclosure" or "Revenue increased 15% due to new contracts in mining sector")
- Full draft generation: LLM generates complete disclosure text using:
  - (a) the applicable standard as RAG context
  - (b) the entity's financial data from trial balance
  - (c) the user's NL instructions
  - (d) prior-year AFS as reference
- Iteration loop: user reviews draft → provides feedback in NL → AI regenerates → repeat until acceptable → lock section
- Compliance validation: AI cross-references generated disclosures against the framework's disclosure checklist, flagging gaps

**Technical approach:**
- RAG pipeline: ingest IFRS/GAAP standards as vector embeddings, retrieve relevant sections when drafting
- Structured output: LLM produces JSON-structured note content (paragraphs, tables, cross-references) that feeds into the statement generator
- Guard rails: financial figures in disclosures must tie back to trial balance data (deterministic check, not LLM-generated numbers)

**Data model:**
- `afs_sections` — id, engagement_id, section_type (note/statement/directors_report), section_number, title, content_json, status (draft/reviewed/locked), version
- `afs_section_history` — id, section_id, version, content_json, changed_by, changed_at, nl_instruction
- `afs_prior_afs` — id, engagement_id, source_type (pdf/excel), extracted_json, upload_path

### 4. Statement Generator

Produces the complete AFS package in multiple output formats.

**Statement types:**
- Statement of Financial Position (Balance Sheet)
- Statement of Comprehensive Income (Income Statement)
- Statement of Cash Flows
- Statement of Changes in Equity
- Notes to the Financial Statements
- Directors' Report
- Auditor's Report template
- Accounting Policies

**Output formats:**
- PDF: print-ready with branding (cover page, headers, footers, logo, colour scheme)
- DOCX: editable Word document for manual review and redlining
- iXBRL/XBRL: machine-readable regulatory filing format (CIPC in SA, SEC in US)
- Excel: supporting workpapers with formulas and cross-references

**Capabilities:**
- Automatic note numbering and internal cross-references
- Table of contents generation
- Branding configuration (leveraging existing board pack branding system)
- Comparative columns (current year vs prior year, with optional 3-year trend)

### 5. Review Workflow

Multi-stage approval process with full audit trail.

**Stages:**
1. Draft — preparer creates/generates the AFS
2. Preparer Review — self-review, mark sections as ready
3. Manager Review — manager reviews, adds review comments, requests changes
4. Partner/Director Sign-off — final approval, locks the AFS

**Capabilities:**
- Version control: full version history with diff between versions
- Redlining: track changes between review stages
- Audit trail: who changed what, when, with comments
- Lock mechanism: once signed off, statement is locked; unlock requires authorised override with reason logged
- Review comments: threaded comments per section, with resolve/unresolve

### 6. AFS Analytics

Financial analysis and benchmarking computed from the generated statements.

**Capabilities:**
- Ratio analysis: liquidity (current, quick), solvency (debt-to-equity, interest coverage), profitability (gross margin, net margin, ROE, ROA), efficiency (asset turnover, inventory days)
- Trend comparison: year-on-year trends with visual charts
- Industry benchmarking: compare key metrics against industry averages (where data available)
- Anomaly detection: AI flags unusual movements or ratios that may require additional disclosure
- Management commentary suggestions: AI suggests key talking points for directors' report based on the financial data
- Going concern indicators: automated assessment of going concern risk factors

### 7. Tax Computation

Deferred tax computation and tax note generation.

**Capabilities:**
- Current tax computation: calculate current tax liability based on taxable income, applying jurisdiction-specific tax rates and rules
- Deferred tax calculation: identify temporary differences between carrying amounts and tax bases, compute deferred tax assets/liabilities
- Tax reconciliation: effective tax rate reconciliation (statutory rate → effective rate, showing each reconciling item)
- Tax note generation: AI-assisted drafting of the income tax note per the applicable framework (IAS 12 for IFRS, ASC 740 for US GAAP)
- Multi-jurisdiction support: handle different tax rates and rules per entity in consolidated groups
- Tax loss carry-forwards: track and apply assessed losses, with recoverability assessment
- Transfer pricing adjustments: flag intercompany transactions for transfer pricing disclosure

**Data model:**
- `afs_tax_computations` — id, engagement_id, entity_id, jurisdiction, statutory_rate, taxable_income, current_tax, deferred_tax_json, reconciliation_json
- `afs_temporary_differences` — id, computation_id, description, carrying_amount, tax_base, difference, deferred_tax_effect, type (asset/liability)

---

## Implementation Phasing

| Phase | Sub-modules | Effort |
|-------|-------------|--------|
| **Phase 1** | Framework Engine + Data Ingestion (single entity) + Statement Generator (PDF/DOCX) | XL |
| **Phase 2** | AI Disclosure Drafter + Prior AFS Analysis | XL |
| **Phase 3** | Review Workflow + Tax Computation | L |
| **Phase 4** | Multi-entity Consolidation + iXBRL/XBRL output | L |
| **Phase 5** | AFS Analytics + Industry Benchmarking | M |
| **Phase 6** | Custom/AI-inferred frameworks + Roll-forward | M |

---

## Database Tables Summary

New tables required (all tenant-scoped with RLS):

| Table | Purpose |
|-------|---------|
| `afs_frameworks` | Accounting standard definitions |
| `afs_disclosure_items` | Disclosure checklist items per framework |
| `afs_engagements` | AFS engagement (one per entity per period) |
| `afs_trial_balances` | Imported trial balance data |
| `afs_consolidation_rules` | Multi-entity consolidation config |
| `afs_sections` | Generated statement sections/notes |
| `afs_section_history` | Version history per section |
| `afs_prior_afs` | Prior-year AFS uploads |
| `afs_tax_computations` | Tax computation per entity |
| `afs_temporary_differences` | Deferred tax temporary differences |
| `afs_reviews` | Review workflow stages and sign-offs |
| `afs_review_comments` | Threaded review comments |

---

## API Endpoints (high-level)

```
# Frameworks
GET    /api/v1/afs/frameworks
POST   /api/v1/afs/frameworks          (custom framework)
GET    /api/v1/afs/frameworks/{id}
GET    /api/v1/afs/frameworks/{id}/checklist

# Engagements
POST   /api/v1/afs/engagements
GET    /api/v1/afs/engagements
GET    /api/v1/afs/engagements/{id}
PATCH  /api/v1/afs/engagements/{id}

# Trial Balance & Mapping
POST   /api/v1/afs/engagements/{id}/trial-balance     (upload or link to VA baseline)
POST   /api/v1/afs/engagements/{id}/trial-balance/map  (AI-assisted account mapping)
GET    /api/v1/afs/engagements/{id}/trial-balance

# Consolidation
POST   /api/v1/afs/engagements/{id}/consolidate
GET    /api/v1/afs/engagements/{id}/consolidation

# Prior AFS
POST   /api/v1/afs/engagements/{id}/prior-afs          (upload PDF or Excel)
GET    /api/v1/afs/engagements/{id}/prior-afs

# AI Disclosure Drafting
POST   /api/v1/afs/engagements/{id}/sections/{section}/draft   (NL instruction → AI draft)
PATCH  /api/v1/afs/engagements/{id}/sections/{section}         (manual edit or re-draft)
POST   /api/v1/afs/engagements/{id}/sections/{section}/lock
GET    /api/v1/afs/engagements/{id}/sections
POST   /api/v1/afs/engagements/{id}/validate                   (compliance check)

# Tax
POST   /api/v1/afs/engagements/{id}/tax/compute
GET    /api/v1/afs/engagements/{id}/tax

# Statement Generation
POST   /api/v1/afs/engagements/{id}/generate    (body: { format: "pdf"|"docx"|"ixbrl"|"excel" })
GET    /api/v1/afs/engagements/{id}/outputs

# Review Workflow
POST   /api/v1/afs/engagements/{id}/reviews/submit
POST   /api/v1/afs/engagements/{id}/reviews/approve
POST   /api/v1/afs/engagements/{id}/reviews/reject
GET    /api/v1/afs/engagements/{id}/reviews
POST   /api/v1/afs/engagements/{id}/reviews/comments

# Analytics
GET    /api/v1/afs/engagements/{id}/analytics/ratios
GET    /api/v1/afs/engagements/{id}/analytics/trends
GET    /api/v1/afs/engagements/{id}/analytics/anomalies
```

---

## Frontend Pages

| Page | Route | Purpose |
|------|-------|---------|
| AFS Dashboard | `/afs` | List engagements, create new |
| Engagement Setup | `/afs/{id}/setup` | Select framework, upload TB, configure entity |
| Account Mapping | `/afs/{id}/mapping` | Map TB accounts to chart of accounts |
| Prior AFS Review | `/afs/{id}/prior` | View extracted prior-year sections |
| Section Editor | `/afs/{id}/sections` | NL-instruction panel + generated draft side-by-side |
| Tax Computation | `/afs/{id}/tax` | Deferred tax worksheet |
| Consolidation | `/afs/{id}/consolidation` | Multi-entity consolidation view |
| Analytics | `/afs/{id}/analytics` | Ratios, trends, anomaly flags |
| Review | `/afs/{id}/review` | Review workflow, comments, sign-off |
| Output | `/afs/{id}/output` | Generate and download PDF/DOCX/iXBRL/Excel |

---

## Sources

- [Caseware Africa IFRS Financial Statements](https://www.casewareafrica.com/ifrs-financial-statements/)
- [Caseware Financial Reporting](https://www.caseware.com/solutions/activity/financial-reporting)
- [Workiva Financial Statement Automation](https://www.workiva.com/solutions/financial-statement-automation)
- [Silverfin vs Caseware](https://silverfin.com/en-gb/resources/caseware-vs-silverfin-best-value/)
- [EY IFRS Disclosure Checklist 2025](https://www.ey.com/en_gl/technical/ifrs-technical-resources/international-gaap-disclosure-checklist-for-annual-financial-statements-2025)
- [KPMG 2025 Disclosure Checklist](https://assets.kpmg.com/content/dam/kpmgsites/xx/pdf/ifrg/2025/isg-2025-disclosure-checklist.pdf)
- [LLMs in Financial Reporting](https://www.ema.co/additional-blogs/addition-blogs/llms-financial-reporting-oversight)
- [18 Best Financial Statement Software 2026](https://thecfoclub.com/tools/best-financial-statement-software/)
