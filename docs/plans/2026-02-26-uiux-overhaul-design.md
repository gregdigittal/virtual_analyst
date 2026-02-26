# UI/UX Overhaul Design

**Date:** 2026-02-26
**Workstream:** 1 of 3 (UI/UX Overhaul → Excel Import → Training Docs)
**Approach:** Full Navigation Restructure with guided flow, template system, and landing page remodel

---

## 1. Navigation Architecture

### Current State

Flat horizontal nav bar with 18 items inline: Baselines, Drafts, Runs, Scenarios, Changesets, Budgets, Workflows, Covenants, Memos, Documents, Board packs, Import Excel, Groups, Marketplace, Dashboard, Settings, Notifications, Inbox. No grouping, no workflow indication.

### Proposed: Collapsible Vertical Sidebar

Replace the horizontal nav with a vertical sidebar grouped by workflow stage:

```
┌─────────────────────────┐
│  [VA Logo]              │
│                         │
│  ▸ SETUP                │
│    Dashboard            │
│    Marketplace          │
│    Import Excel         │
│    Groups               │
│                         │
│  ▸ CONFIGURE            │
│    Baselines            │
│    Drafts               │
│    Scenarios            │
│                         │
│  ▸ ANALYZE              │
│    Runs                 │
│    Budgets              │
│    Covenants            │
│                         │
│  ▸ REPORT               │
│    Board Packs          │
│    Memos                │
│    Documents            │
│                         │
│  ─────────────────────  │
│    Workflows            │
│    Changesets           │
│    Inbox          (3)   │
│    Notifications  (2)   │
│    Settings             │
│                         │
│  [Sign out]             │
└─────────────────────────┘
```

### Design Decisions

- **Vertical sidebar** instead of horizontal bar — room for grouping and future growth.
- **4 workflow groups** map to the model creation flow: Setup → Configure → Analyze → Report.
- **Collapsible groups** — each section header toggles open/close, persisted in local storage.
- **Progress indicators** on group headers — small badge showing completion state (e.g., "2/3") for the current model context.
- **Utility items** (Workflows, Changesets, Inbox, Notifications, Settings) sit below a divider — cross-cutting, not part of the linear flow.
- **Rail mode** — sidebar collapses to icon-only for users who want more screen space.
- **Soft gates** — clicking a CONFIGURE item without completing SETUP loads the page but shows a contextual banner: "No baseline created yet — [Start setup →]".

---

## 2. Progress Stepper & Soft Gates

### Contextual Progress Stepper

A horizontal stepper appears at the top of pages within a model context (baseline, draft, or run):

```
 ① Start  →  ② Company  →  ③ Historical  →  ④ Assumptions  →  ⑤ Correlations  →  ⑥ Run  →  ⑦ Review
   ✓ done      ✓ done       ● current        ○ pending        ○ pending          ○ locked   ○ locked
```

### Behavior

- **Context-aware:** Only shown when working within a specific baseline/draft. Not shown on Dashboard, Marketplace, or utility pages.
- **State derivation:** Computed from existing data (no new state to store).
- **Clickable steps:** Each step navigates to the relevant page.
- **Soft locks:** Steps 6 (Run) and 7 (Review) show as "locked" with tooltip until prerequisites are met. Users can still click through — the target page shows a contextual banner.

### Completion Criteria

| Step | Complete When |
|------|--------------|
| 1. Start | Baseline created (template, import, or blank) |
| 2. Company | Entity name and industry classification set |
| 3. Historical | At least one AFS document uploaded |
| 4. Assumptions | ≥1 revenue stream AND ≥1 funding source configured |
| 5. Correlations | Correlation matrix has ≥1 entry (or explicitly marked "none") |
| 6. Run | At least one completed run exists |
| 7. Review | User has viewed the results page |

### Shared Component

Renders in the baseline/draft/run page layouts, positioned between the sidebar and the page content. Implemented as a reusable `<ModelStepper baselineId={id} />` component.

---

## 3. Template System

Three template sources with AI-driven detection.

### 3a. Pre-built Industry Templates

Expand the existing marketplace from ~5 to 12-15 templates:

| Category | Templates | Key Drivers |
|----------|-----------|-------------|
| Technology | SaaS, Hardware/IoT | MRR, churn, CAC/LTV, R&D spend |
| Services | Consulting, Legal, Software Dev, Staffing | Utilization rate, billable hours, headcount |
| Manufacturing | Discrete, Process | Raw materials, capacity utilization, yield |
| Distribution | Wholesale (local), Wholesale (import), Retail | Inventory turnover, gross margin, freight |
| Construction | General Contractor, Specialty Trade | Project pipeline, completion %, retention |
| Healthcare | Medical Practice, Healthcare Services | Patient volume, reimbursement rates, payer mix |

Each template includes:
- Industry classification (NAICS code mapping)
- Default revenue stream types with typical distributions
- Default OpEx categories and growth drivers
- Suggested correlation matrix
- Question plan for customization

### 3b. User-Created Templates

- "Save as Template" button on a completed baseline.
- User provides: template name, industry tag, description.
- System captures: assumption structure, revenue stream types, distribution shapes, correlation matrix (NOT actual values).
- Tenant-scoped (private) by default, with option to publish to marketplace.

### 3c. AI-Driven Industry & Driver Detection

**Trigger:** User uploads AFS documents in step 3 of the flow.

**Pipeline:**
1. **Upload & parse** — existing Excel ingestion pipeline extracts line items.
2. **Industry classification** — Claude analyzes chart of accounts, revenue mix, expense structure → NAICS code.
3. **Driver detection** — year-over-year analysis identifies:
   - Revenue drivers (growth patterns, seasonality, segment mix)
   - Cost drivers (fixed vs variable, correlation to revenue)
   - Working capital patterns (DSO, DPO, inventory days)
4. **Template matching** — matches detected industry/drivers against pre-built templates, presents best match.
5. **User confirmation** — "This looks like a **professional services** business with **3 revenue segments** and **consulting-driven** cost structure. [Use Services template] [Customize] [Start blank]"

### Multi-Entity Detection

- When multiple entity names appear in uploaded AFS (consolidated + subsidiaries), the AI proposes an org hierarchy.
- Each entity gets its own industry classification.
- User confirms/adjusts the tree structure via a visual editor before proceeding.

---

## 4. Landing Page Remodel

### 4a. Hero Section

```
┌──────────────────────────────────────────────────────┐
│                                                      │
│         [VA Logo - large, prominent]                 │
│                                                      │
│    One Platform for the Full Financial                │
│    Modeling Workflow                                  │
│                                                      │
│    From AFS upload to board pack —                   │
│    AI-powered modeling, Monte Carlo                  │
│    simulation, and automated reporting               │
│                                                      │
│    [Get Started Free]  [See How It Works →]          │
│                                                      │
│    ┌─────────────────────────────────────┐           │
│    │  Product screenshot / animation     │           │
│    │  showing the 7-step workflow        │           │
│    └─────────────────────────────────────┘           │
│                                                      │
└──────────────────────────────────────────────────────┘
```

- Logo at 2-3x current size, centered.
- Tagline: "One Platform for the Full Financial Modeling Workflow."
- Secondary CTA links to how-it-works section.
- Hero image shows actual product (stepper + dashboard).

### 4b. Feature Showcase

Organized by workflow stages (matching the sidebar groups):

**SETUP** — Import Excel models, upload AFS, choose from industry templates, AI-detected industry classification.

**CONFIGURE** — Structured assumption editor, scenario comparison, correlation matrix, AI-assisted driver detection.

**ANALYZE** — Monte Carlo simulation, sensitivity analysis, budget tracking, covenant monitoring.

**REPORT** — Auto-generated board packs, executive memos, document management.

Each section: screenshot/mockup + 2-3 bullet points.

### 4c. Competitor Comparison Page (`/compare`)

**Tier 1: vs. Spreadsheets (Excel / Google Sheets)**

| Feature | Spreadsheets | Virtual Analyst |
|---------|-------------|-----------------|
| Monte Carlo simulation | Manual/VBA | Built-in, 1-click |
| Scenario comparison | Copy worksheets | Side-by-side diff |
| Collaboration | File sharing | Real-time, versioned |
| AI assistance | None | Industry detection, driver analysis |
| Audit trail | None | Full version history |

**Tier 2: vs. Enterprise FP&A (Anaplan, Adaptive, Vena)**

| Feature | Enterprise FP&A | Virtual Analyst |
|---------|----------------|-----------------|
| Setup time | Weeks/months | Minutes |
| Pricing | $50K-500K/yr | Fraction of the cost |
| AI-native | Bolt-on | Built from ground up |
| Monte Carlo | Limited/add-on | Core feature |
| Template marketplace | Vendor-locked | Open, community-driven |

### 4d. Additional Sections

- **How It Works** — illustrated/animated 7-step flow.
- **Social Proof** — testimonial placeholder for future use.
- **Pricing** section or link.
- **Footer** — docs, support, comparison page links.

---

## Implementation Order

This design should be implemented in this sequence:

1. **Navigation restructure** — sidebar component, route grouping, responsive behavior
2. **Progress stepper** — shared component, completion criteria logic
3. **Soft gates** — contextual banners on pages
4. **Pre-built templates** — expand marketplace with 7-10 new templates
5. **User-created templates** — "Save as Template" flow
6. **AI detection pipeline** — industry classification and driver detection from AFS
7. **Multi-entity detection** — org hierarchy extraction
8. **Landing page hero** — redesign with prominent logo and new tagline
9. **Feature showcase** — workflow-organized feature sections
10. **Comparison page** — `/compare` with two-tier layout
