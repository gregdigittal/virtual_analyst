# Glossary

Definitions of key terms used throughout the Virtual Analyst user manual.

---

## A

| Term | Definition | Reference |
|------|-----------|-----------|
| **ACS Callback** | The Assertion Consumer Service URL that your identity provider redirects to after authenticating a user via SAML single sign-on. You enter this URL in the SSO configuration panel within Settings. | [Ch. 26](26-settings-and-admin.md) |
| **AFS (Annual Financial Statements)** | The module for creating IFRS- or GAAP-compliant annual financial statements. AFS covers engagement setup, AI-assisted disclosure drafting, review workflows, tax computation, multi-entity consolidation, and output generation in PDF, DOCX, or iXBRL format. | [Ch. 06](06-afs-module.md) |
| **Approval Chain** | An ordered sequence of reviewers that a workflow item must pass through before it is approved. Each step in the chain can require one or more sign-offs from designated roles. | [Ch. 22](22-workflows-and-tasks.md) |
| **Assignee Rule** | A workflow configuration that determines how tasks are routed to specific users or roles. Assignee rules can match by entity, department, or custom criteria. | [Ch. 22](22-workflows-and-tasks.md) |
| **Assumption** | A named input parameter in a financial model, such as a growth rate, margin percentage, or cost escalation factor. Assumptions drive the calculations that produce projected financial statements. | [Ch. 11](11-drafts.md) |
| **Audit Log** | A chronological record of all significant actions taken within a tenant, including logins, data changes, approvals, and configuration updates. Accessible to administrators from the Settings page. | [Ch. 26](26-settings-and-admin.md) |

## B

| Term | Definition | Reference |
|------|-----------|-----------|
| **Baseline** | The foundational data record for a financial model. A baseline contains a complete set of line items, assumptions, and configuration and serves as the starting point from which drafts, scenarios, and runs are created. | [Ch. 10](10-baselines.md) |
| **Binding (Excel)** | A mapping between a cell or range in an Excel workbook and a specific value in a Virtual Analyst model. Bindings enable bidirectional data synchronization through Excel Connections. | [Ch. 05](05-excel-connections.md) |
| **Board Pack** | A presentation-ready package of financial results, charts, narratives, and commentary assembled for board meetings or stakeholder reviews. Board packs can be generated on demand or on a recurring schedule. | [Ch. 23](23-board-packs.md) |
| **Breach (Covenant)** | An event that occurs when a monitored financial ratio or metric crosses the threshold defined in a covenant. Breaches trigger alerts and are flagged on the covenant compliance dashboard. | [Ch. 18](18-covenants.md) |
| **Budget** | A financial plan that sets expected revenue, cost, and expenditure targets for a defined period. Virtual Analyst tracks budget performance through variance analysis and period-by-period comparison charts. | [Ch. 17](17-budgets.md) |

## C

| Term | Definition | Reference |
|------|-----------|-----------|
| **Capital Expenditure (CapEx)** | Funds spent on acquiring, upgrading, or maintaining physical assets such as equipment or property. In Virtual Analyst, CapEx lines are distinct from operating costs and are modeled separately during import and drafting. | [Ch. 04](04-data-import.md) |
| **Changeset** | An immutable snapshot of targeted overrides applied to a baseline. Changesets can be tested with dry-runs before being merged to create a new baseline version. | [Ch. 13](13-changesets.md) |
| **Compliance** | The status indicating whether an entity's financial metrics meet the requirements defined by its covenants or regulatory frameworks. The covenants dashboard shows compliance status at a glance. | [Ch. 18](18-covenants.md) |
| **Confidence Interval** | A statistical range, derived from Monte Carlo simulation, that indicates the probability of a result falling between two values. Common intervals displayed include P10-P90 and P25-P75. | [Ch. 15](15-monte-carlo-and-sensitivity.md) |
| **Consolidation** | The process of combining financial statements from multiple entities within a group into a single set of group-level statements. Consolidation includes intercompany eliminations and foreign exchange translation. | [Ch. 08](08-afs-consolidation-and-output.md) |
| **Correlation Matrix** | A table that defines the statistical relationships between pairs of assumptions in a Monte Carlo simulation. Positive correlations cause assumptions to move together; negative correlations cause them to move inversely. | [Ch. 15](15-monte-carlo-and-sensitivity.md) |
| **Cost Item** | A named operating expense line in a financial model, such as salaries, rent, or marketing spend. Cost items are categorized during data import and can be adjusted in drafts. | [Ch. 04](04-data-import.md) |
| **Covenant** | A financial condition or ratio that must be maintained, typically as part of a debt agreement. Virtual Analyst lets you define covenant thresholds and monitors them against run results. | [Ch. 18](18-covenants.md) |

## D

| Term | Definition | Reference |
|------|-----------|-----------|
| **Dashboard** | The home screen displayed after login. It shows summary cards for recent runs, pending tasks, unread notifications, and API performance metrics, with links to recent activity. | [Ch. 02](02-dashboard.md) |
| **DCF (Discounted Cash Flow)** | A valuation method that estimates the present value of a business by discounting its projected future free cash flows back to today using a weighted average cost of capital (WACC). | [Ch. 16](16-valuation.md) |
| **Deterministic Run** | A model run that uses fixed, single-point assumption values rather than probability distributions. Deterministic runs produce a single set of projected financial statements without Monte Carlo variation. | [Ch. 14](14-runs.md) |
| **Disclosure** | A required explanatory note within annual financial statements, such as accounting policies, related-party transactions, or segment reporting. The AFS module uses AI to draft disclosures from uploaded data. | [Ch. 06](06-afs-module.md) |
| **Draft** | A working copy of a baseline where you adjust assumptions, add scenarios, and prepare for analysis. Drafts support AI chat assistance and can be committed back to create new baseline versions. | [Ch. 11](11-drafts.md) |
| **Dry-Run** | A test execution of a changeset against a baseline that shows projected impacts without actually merging the changes. Dry-runs help you validate overrides before committing them. | [Ch. 13](13-changesets.md) |

## E

| Term | Definition | Reference |
|------|-----------|-----------|
| **Elimination (Intercompany)** | An adjustment made during consolidation to remove the effects of transactions between entities within the same group, preventing double-counting of revenue, expenses, assets, or liabilities. | [Ch. 08](08-afs-consolidation-and-output.md) |
| **Engagement (AFS)** | A container within the AFS module that represents a single annual financial statement preparation project. An engagement links an entity to a fiscal year and holds all sections, reviews, and outputs for that period. | [Ch. 06](06-afs-module.md) |
| **Entity** | A legal or organizational unit, such as a company, subsidiary, or division, that is modeled independently in Virtual Analyst. Entities can be grouped into organizational hierarchies for consolidation. | [Ch. 09](09-org-structures.md) |
| **EV/EBITDA** | Enterprise Value to Earnings Before Interest, Taxes, Depreciation, and Amortisation -- a valuation multiple used to compare the value of a business relative to its operating earnings. Available in the Valuation output. | [Ch. 16](16-valuation.md) |
| **Excel Connection** | A persistent, bidirectional synchronization link between an Excel workbook and a Virtual Analyst baseline or run. Connections allow you to pull live values into Excel or push updated values back into the model. | [Ch. 05](05-excel-connections.md) |
| **Exit Multiple** | A valuation assumption representing the multiple (e.g., EV/EBITDA) at which a business is expected to be sold or valued at the end of the projection period. Used to calculate terminal value. | [Ch. 16](16-valuation.md) |

## F

| Term | Definition | Reference |
|------|-----------|-----------|
| **Fan Chart** | A visualization that displays the range of possible outcomes from a Monte Carlo simulation over time. The shaded bands represent confidence intervals (e.g., P10-P90), with darker bands indicating higher-probability ranges. | [Ch. 15](15-monte-carlo-and-sensitivity.md) |
| **Fiscal Year** | The twelve-month accounting period used by an entity for financial reporting. When creating a baseline or AFS engagement, you specify the fiscal year to align projections and disclosures correctly. | [Ch. 10](10-baselines.md) |
| **FX Translation** | The process of converting financial statements from a subsidiary's functional currency into the group's presentation currency during consolidation. Virtual Analyst applies the appropriate exchange rates to each line item. | [Ch. 08](08-afs-consolidation-and-output.md) |

## G

| Term | Definition | Reference |
|------|-----------|-----------|
| **GAAP (Generally Accepted Accounting Principles)** | A set of accounting standards and procedures used primarily in the United States. The AFS module supports GAAP as one of two available reporting frameworks alongside IFRS. | [Ch. 06](06-afs-module.md) |
| **Gordon Growth Model** | A terminal value calculation method that assumes cash flows grow at a constant rate in perpetuity beyond the explicit projection period. Also known as the perpetuity growth method. | [Ch. 16](16-valuation.md) |
| **Group (Org Structure)** | A collection of related entities arranged in a parent-subsidiary hierarchy. Groups define the consolidation perimeter and determine which entities are included in combined financial reporting. | [Ch. 09](09-org-structures.md) |

## H

| Term | Definition | Reference |
|------|-----------|-----------|
| **Heat Map** | A color-coded matrix that visualizes the magnitude of values across two dimensions, such as sensitivity of a KPI to pairs of assumptions. Warmer colors indicate higher values; cooler colors indicate lower values. | [Ch. 15](15-monte-carlo-and-sensitivity.md) |

## I

| Term | Definition | Reference |
|------|-----------|-----------|
| **IFRS (International Financial Reporting Standards)** | A globally adopted set of accounting standards issued by the IASB. The AFS module supports IFRS as one of two available reporting frameworks and uses it to structure disclosure sections and notes. | [Ch. 06](06-afs-module.md) |
| **Inbox** | A centralized area within the platform that collects review requests, feedback items, assigned tasks, and notifications directed to the current user. | [Ch. 22](22-workflows-and-tasks.md) |
| **Integration** | A connection between Virtual Analyst and an external accounting or ERP system, such as Xero or QuickBooks. Integrations allow automatic data import and synchronization. Configured under Settings. | [Ch. 26](26-settings-and-admin.md) |
| **Investment Memo** | A structured document that presents the financial case for or against an investment. Memos draw data from model runs and include narrative sections, key metrics, and supporting charts. | [Ch. 24](24-memos-and-documents.md) |
| **iXBRL (Inline eXtensible Business Reporting Language)** | A digital reporting format that embeds machine-readable XBRL tags within a human-readable HTML document. The AFS module can generate iXBRL output for regulatory filing. | [Ch. 08](08-afs-consolidation-and-output.md) |

## K

| Term | Definition | Reference |
|------|-----------|-----------|
| **KPI (Key Performance Indicator)** | A quantifiable metric used to evaluate the financial performance of an entity, such as EBITDA margin, revenue growth rate, or debt-to-equity ratio. KPIs are calculated during runs and displayed on dashboards and reports. | [Ch. 14](14-runs.md) |

## L

| Term | Definition | Reference |
|------|-----------|-----------|
| **Learning Point** | An AI-generated insight surfaced during disclosure drafting or review that highlights a notable accounting treatment, risk factor, or area requiring attention. | [Ch. 06](06-afs-module.md) |
| **Line Item** | A single row in a financial model representing a specific revenue stream, cost item, or balance sheet entry. Line items are the building blocks of baselines and drafts. | [Ch. 10](10-baselines.md) |

## M

| Term | Definition | Reference |
|------|-----------|-----------|
| **Marketplace** | A library of pre-built financial model templates organized by industry and type. Users browse, search, and apply templates from the Marketplace to create new baselines. | [Ch. 03](03-marketplace.md) |
| **Memo** | See *Investment Memo*. | [Ch. 24](24-memos-and-documents.md) |
| **Monte Carlo Simulation** | A computational technique that runs thousands of iterations of a financial model, each time sampling assumption values from defined probability distributions. The resulting distribution of outcomes quantifies uncertainty and risk. | [Ch. 15](15-monte-carlo-and-sensitivity.md) |

## N

| Term | Definition | Reference |
|------|-----------|-----------|
| **Narrative (Board Pack)** | A text section within a board pack that provides qualitative commentary, executive summaries, or strategic context alongside the quantitative charts and tables. | [Ch. 23](23-board-packs.md) |
| **Notification** | An in-app alert delivered to a user when a relevant event occurs, such as a completed run, a new review assignment, or a covenant breach. Notifications appear under the bell icon and in the Inbox. | [Ch. 25](25-collaboration.md) |

## O

| Term | Definition | Reference |
|------|-----------|-----------|
| **OAuth** | An open authorization standard that allows users to sign in using their Google or Microsoft account without creating a separate password. OAuth is also used to connect external integrations like Xero and QuickBooks. | [Ch. 26](26-settings-and-admin.md) |
| **Override** | A targeted change to a specific assumption or line item value within a changeset. Overrides let you test adjustments in isolation before merging them into a baseline. | [Ch. 13](13-changesets.md) |
| **Ownership Percentage** | The share of a subsidiary held by its parent entity, expressed as a percentage. Ownership percentage determines the consolidation method applied (full consolidation, proportional, or equity method). | [Ch. 09](09-org-structures.md) |

## P

| Term | Definition | Reference |
|------|-----------|-----------|
| **P10 / P50 / P90** | Percentile markers from a Monte Carlo simulation. P10 means there is a 10% probability the result will be at or below that value; P50 is the median; P90 means a 90% probability the result will be at or below that value. | [Ch. 15](15-monte-carlo-and-sensitivity.md) |
| **Peer Group** | A set of comparable entities or industry benchmarks used for performance comparison. Peer groups are configured in the Benchmarking module by selecting industry, size, and geography criteria. | [Ch. 19](19-benchmarking.md) |
| **Percentile** | A statistical measure indicating the value below which a given percentage of observations fall. In Monte Carlo results, percentiles describe the distribution of possible outcomes. | [Ch. 15](15-monte-carlo-and-sensitivity.md) |
| **Perimeter (Consolidation)** | The set of entities included in a group consolidation. The perimeter is defined by the organizational structure and ownership thresholds, determining which subsidiaries are fully consolidated, proportionally consolidated, or equity-accounted. | [Ch. 08](08-afs-consolidation-and-output.md) |
| **Pool Task** | A workflow task that is not assigned to a specific individual but instead available for any qualified team member to claim. Pool tasks appear in the Inbox for all users who match the assignee rule. | [Ch. 22](22-workflows-and-tasks.md) |
| **Proposal (Draft)** | A draft that has been submitted for review through a workflow. Once submitted as a proposal, the draft enters the approval chain and cannot be further edited until the review is complete. | [Ch. 11](11-drafts.md) |
| **Pull (Excel Connection)** | The action of fetching the latest values from a Virtual Analyst model into a connected Excel workbook. A pull refreshes bound cells with current run results or baseline data. | [Ch. 05](05-excel-connections.md) |
| **Push (Excel Connection)** | The action of sending updated values from a connected Excel workbook back into a Virtual Analyst model. A push updates assumption values or line items in the linked baseline or draft. | [Ch. 05](05-excel-connections.md) |

## R

| Term | Definition | Reference |
|------|-----------|-----------|
| **Reforecast** | An updated projection created mid-period that replaces or supplements the original budget with revised assumptions based on actual results to date. Reforecasts are tracked alongside budgets for variance analysis. | [Ch. 17](17-budgets.md) |
| **Revenue Stream** | A distinct source of income for an entity, such as product sales, subscription fees, or service revenue. Revenue streams are defined during data import and modeled individually in baselines and drafts. | [Ch. 04](04-data-import.md) |
| **Run** | An execution of a financial model against a draft's configuration. A run produces projected financial statements, KPIs, Monte Carlo distributions, sensitivity analyses, and valuation outputs. | [Ch. 14](14-runs.md) |

## S

| Term | Definition | Reference |
|------|-----------|-----------|
| **SAML / SSO (Single Sign-On)** | An authentication protocol that allows users to log in to Virtual Analyst using their organization's identity provider (e.g., Okta, Azure AD). Configured by administrators under Settings. | [Ch. 26](26-settings-and-admin.md) |
| **Scenario** | An alternative set of assumptions that can be applied to a model to explore different outcomes. Common scenarios include best case, base case, and worst case. Multiple scenarios can be compared side by side. | [Ch. 12](12-scenarios.md) |
| **Section (AFS / Board Pack)** | A discrete, editable unit within an AFS engagement or board pack. In AFS, sections correspond to disclosure notes (e.g., revenue recognition, related parties). In board packs, sections hold charts, tables, or narratives. | [Ch. 06](06-afs-module.md) |
| **Sensitivity Analysis** | A technique that measures how changes in individual assumptions affect a specific output metric. Results are typically displayed as tornado charts showing the relative impact of each assumption. | [Ch. 15](15-monte-carlo-and-sensitivity.md) |
| **Stage (Workflow)** | A single step within an approval chain. Each stage specifies who must review and approve, along with any conditions or deadlines. Items advance through stages sequentially until fully approved. | [Ch. 22](22-workflows-and-tasks.md) |

## T

| Term | Definition | Reference |
|------|-----------|-----------|
| **Template** | A pre-built financial model structure available in the Marketplace. Templates include default line items, assumptions, and industry-specific configurations that can be applied to create a new baseline. | [Ch. 03](03-marketplace.md) |
| **Tenant** | The top-level organizational account in Virtual Analyst. A tenant encompasses all users, entities, baselines, and settings for a single organization. Administrators manage tenant-wide configuration from Settings. | [Ch. 26](26-settings-and-admin.md) |
| **Terminal Value** | The estimated value of a business beyond the explicit projection period in a DCF valuation. Terminal value is calculated using either the Gordon Growth Model (perpetuity growth) or an exit multiple approach. | [Ch. 16](16-valuation.md) |
| **Tornado Chart** | A horizontal bar chart used in sensitivity analysis to rank assumptions by their impact on a chosen output. The longest bars represent the assumptions with the greatest influence on the result. | [Ch. 15](15-monte-carlo-and-sensitivity.md) |
| **Trial Balance** | A listing of all general ledger account balances at a specific point in time. Trial balances can be uploaded as part of the AFS data import process to populate disclosure sections. | [Ch. 06](06-afs-module.md) |

## V

| Term | Definition | Reference |
|------|-----------|-----------|
| **Valuation** | The process of estimating the economic worth of a business or entity. Virtual Analyst supports DCF (discounted cash flow) and multiples-based valuation methods, with outputs generated as part of a model run. | [Ch. 16](16-valuation.md) |
| **Variance** | The difference between a budgeted or projected value and the corresponding actual result. Variance analysis highlights where performance deviates from plan and is displayed in budget tracking and entity comparison views. | [Ch. 17](17-budgets.md) |
| **Venture** | A business concept entered through the guided questionnaire wizard. Virtual Analyst uses AI to convert your answers into initial financial assumptions, which are saved as a draft for further refinement. | [Ch. 21](21-ventures.md) |
| **Version (Baseline)** | A numbered, immutable snapshot of a baseline created when changes are committed. Versions provide a full history of how a baseline has evolved, allowing you to compare or revert to any prior state. | [Ch. 10](10-baselines.md) |

## W

| Term | Definition | Reference |
|------|-----------|-----------|
| **WACC (Weighted Average Cost of Capital)** | The blended cost of a company's debt and equity financing, used as the discount rate in DCF valuations. WACC is configured as an assumption and directly affects the present value of projected cash flows. | [Ch. 16](16-valuation.md) |
| **Workflow** | A structured process that routes items (baselines, drafts, reports) through a defined approval chain. Workflows enforce review requirements, capture sign-offs, and maintain an audit trail of all approval decisions. | [Ch. 22](22-workflows-and-tasks.md) |

---

## Page Help

Every page in Virtual Analyst includes a floating **Instructions** button positioned in the bottom-right corner of the screen. While the Glossary itself does not have a dedicated application page, relevant term definitions and contextual guidance are surfaced within the help drawers throughout the platform. Clicking the **Instructions** button on any page opens a help drawer that provides:

- Step-by-step guidance specific to the page you are currently viewing.
- Definitions and explanations of key concepts relevant to that page's functionality.
- Prerequisites and links to related chapters in this manual.

The help drawer can be dismissed by clicking outside it or pressing the close button. It is available on every page, so you can access context-sensitive guidance wherever you are in the platform.
