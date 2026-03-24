# Virtual Analyst — Training Video Script

**Total runtime:** ~40 minutes across 12 modules
**Production URL:** https://www.virtual-analyst.ai
**Presenter note:** Record in one session per module. Pause at every `[SCREEN:]` tag to allow editor to sync screen recording. Speak at a measured pace — approximately 130 words per minute.

---

## Table of Contents

- [Module 1 — Welcome & Platform Overview (2 min)](#module-1--welcome--platform-overview-2-min)
- [Module 2 — Logging In & Account Setup (2 min)](#module-2--logging-in--account-setup-2-min)
- [Module 3 — Building Your First Financial Model (5 min)](#module-3--building-your-first-financial-model-5-min)
- [Module 4 — AI-Assisted Assumption Editing (4 min)](#module-4--ai-assisted-assumption-editing-4-min)
- [Module 5 — Monte Carlo & Sensitivity Analysis (4 min)](#module-5--monte-carlo--sensitivity-analysis-4-min)
- [Module 6 — Valuation (DCF) (3 min)](#module-6--valuation-dcf-3-min)
- [Module 7 — Budgeting Workflow (4 min)](#module-7--budgeting-workflow-4-min)
- [Module 8 — Annual Financial Statements (AFS) Module (6 min)](#module-8--annual-financial-statements-afs-module-6-min)
- [Module 9 — Board Packs (3 min)](#module-9--board-packs-3-min)
- [Module 10 — Team Collaboration & Roles (2 min)](#module-10--team-collaboration--roles-2-min)
- [Module 11 — Integrations (Xero / QuickBooks) (2 min)](#module-11--integrations-xero--quickbooks-2-min)
- [Module 12 — Tips, Shortcuts & Where to Get Help (1 min)](#module-12--tips-shortcuts--where-to-get-help-1-min)
- [A. Chapter Timestamps](#a-chapter-timestamps)
- [B. On-Screen Lower-Third Text](#b-on-screen-lower-third-text)
- [C. 60-Second Teaser Script](#c-60-second-teaser-script)
- [D. Quiz Questions](#d-quiz-questions)

---

## Module 1 — Welcome & Platform Overview (2 min)

**Narrator:**
> Welcome to Virtual Analyst. In this training series you'll learn how to use every major feature of the platform — from building your first three-statement financial model through to generating board-ready reports and annual financial statement disclosures.

`[SCREEN: Show the Virtual Analyst homepage at www.virtual-analyst.ai — dark theme, the VA logo visible, with the login prompt centred on screen]`

**Narrator:**
> Virtual Analyst is built for accountants and financial analysts. It combines a deterministic financial modeling engine — meaning the same inputs always produce the same outputs, with no randomness — with an AI layer that helps you draft assumptions, write disclosures, and generate narrative commentary. The AI assists. You decide. Nothing is published or committed without your explicit approval.

`[SCREEN: After login, show the main dashboard at /dashboard — KPI summary cards across the top, recent run history in the centre, sidebar visible on the left]`

> **[CALLOUT: "Deterministic engine + AI draft layer = speed without sacrificing control"]**

**Narrator:**
> When you log in, you land on the Dashboard. At a glance you can see your recent model runs, key financial metrics, and any pending workflow tasks. On the left is the main navigation sidebar, organised into four areas: Setup, Configure, Analyse, and Report. We'll work through each area in this series.

`[SCREEN: Slowly move the cursor down the sidebar — hover over each section label as it's mentioned]`

**Narrator:**
> The platform is designed so that every major workflow — financial modeling, budgeting, annual financial statements, board pack generation — follows the same pattern: you provide the data, the engine computes deterministically, and the AI helps you communicate the results. Let's start from the beginning.

`[SCREEN: Fade to black with "Module 2: Logging In & Account Setup" title card]`

---

## Module 2 — Logging In & Account Setup (2 min)

**Narrator:**
> Navigate to www.virtual-analyst.ai. You'll land on the login page.

`[SCREEN: Show the /login page — email field, password field, Google and Microsoft OAuth buttons visible]`

**Narrator:**
> You can sign in with an email address and password, or use your existing Google or Microsoft account. If your organisation uses a corporate identity provider — such as Microsoft Entra, Okta, or any SAML 2.0-compatible IdP — your administrator can configure Single Sign-On, and you'll sign in through your company's standard login page. We'll cover SSO configuration in the Settings section later.

`[SCREEN: Type the email address into the field, then the password, then click Sign In]`

> **[CALLOUT: "SSO available for enterprise tenants — contact your administrator"]**

**Narrator:**
> After signing in, you arrive at the Dashboard. Your account in Virtual Analyst has one of four roles: Owner, Admin, Analyst, or Investor. Owners and Admins can configure the workspace, manage users, and connect integrations. Analysts can build and run models, create budgets, and generate reports. Investors have read-only access to published outputs — useful for giving a board member or a client visibility into results without allowing them to modify anything.

`[SCREEN: Navigate to /teams — show the user list with role badges next to each name]`

> **[CALLOUT: "Roles: Owner · Admin · Analyst · Investor"]**

**Narrator:**
> Your role is set by the workspace owner. If you need a different level of access, speak to whoever manages your Virtual Analyst account. Now let's build something.

`[SCREEN: Fade to black with "Module 3: Building Your First Financial Model" title card]`

---

## Module 3 — Building Your First Financial Model (5 min)

**Narrator:**
> In Virtual Analyst, a financial model lives inside something called a Baseline. A Baseline is a versioned snapshot of your model's structure and assumptions — the nodes, the formulas, and the input values that drive your three financial statements.

`[SCREEN: Click "Baselines" in the sidebar. Show the /baselines list page — empty or with existing baselines]`

> **[CALLOUT: "Baseline = versioned model configuration"]**

**Narrator:**
> Let's create a new baseline. Click "New Baseline" and give it a name — in this example we'll call it "FY2026 Operating Model."

`[SCREEN: Click "New Baseline". A form or modal appears. Type "FY2026 Operating Model" in the name field. Click Create.]`

**Narrator:**
> You're now in the Baseline editor. On the left you'll see a node panel — this is where you define the structure of your model. Each node represents either an input assumption, a formula, or an output line item. Think of it like a spreadsheet where every cell knows what it depends on, and the engine evaluates the entire graph in the correct dependency order every time you run it.

`[SCREEN: Show the baseline editor — a visual graph or table of nodes, with the node panel on the left. Hover over one node to show its expression.]`

> **[CALLOUT: "Nodes = inputs, formulas, or outputs. The engine evaluates the full dependency graph."]**

**Narrator:**
> Let's add a simple revenue line. Click "Add Node," choose type "Input," and name it "Annual Revenue." Set the value to 5,000,000. This is your top-line assumption.

`[SCREEN: Click "Add Node." Select Input type. Type "Annual Revenue" in the name field. Enter 5000000 as the value. Save the node.]`

**Narrator:**
> Now add a formula node for COGS. Click "Add Node," choose "Formula," name it "Cost of Goods Sold," and enter the expression: Annual Revenue multiplied by 0.55 — meaning COGS is 55% of revenue.

`[SCREEN: Add another node. Select Formula type. Name it "Cost of Goods Sold." In the expression field type: Annual_Revenue * 0.55. Save.]`

> **[CALLOUT: "Formula nodes reference other nodes by name. The engine handles evaluation order automatically."]**

**Narrator:**
> Add one more formula node for Gross Profit: Annual Revenue minus Cost of Goods Sold. With just three nodes, you've defined a basic P&L structure. In a real model you'd add many more lines — operating expenses, depreciation, interest, tax — but the pattern is the same throughout.

`[SCREEN: Add a third node named "Gross Profit" with expression: Annual_Revenue - Cost_of_Goods_Sold. Save.]`

**Narrator:**
> Now let's run the model. Click "Run" at the top of the page.

`[SCREEN: Click the Run button. A loading state appears briefly. Then the run completes and a success notification appears.]`

**Narrator:**
> Virtual Analyst evaluates every formula in the correct order and produces your three financial statements. Click "View Run" to see the results.

`[SCREEN: Click "View Run" or navigate to /runs/[id]. Show the income statement tab — revenue, COGS, gross profit figures populated from the model.]`

**Narrator:**
> There's your income statement. Revenue of five million, COGS at two million seven-fifty, and a gross profit of two million two-fifty. Exactly what you'd expect from the inputs. Switch to the Balance Sheet and Cash Flow tabs to see the full three-statement output.

`[SCREEN: Click the Balance Sheet tab, then the Cash Flow tab. Both show their respective outputs.]`

> **[CALLOUT: "Three-statement output: Income Statement · Balance Sheet · Cash Flow"]**

**Narrator:**
> Everything you see here is computed deterministically from the nodes you defined. Change an input, run again, and the output updates. No manual cell-linking. No version confusion. One model, one run, one set of outputs. In the next module we'll see how the AI layer helps you explore changes without touching the model directly.

`[SCREEN: Fade to black with "Module 4: AI-Assisted Assumption Editing" title card]`

---

## Module 4 — AI-Assisted Assumption Editing (4 min)

**Narrator:**
> Virtual Analyst includes a drafting layer — an AI assistant that lets you explore changes to your model assumptions in plain English, without editing the baseline directly. This is one of the most powerful features in the platform, and it's important to understand what it does and what it doesn't do.

`[SCREEN: Click "Drafts" in the sidebar. Show the /drafts list. Click "New Draft" or open an existing one linked to the FY2026 baseline.]`

> **[CALLOUT: "Drafts let you explore changes safely — nothing affects your baseline until you commit"]**

**Narrator:**
> A Draft is a sandbox. It holds a working copy of your model assumptions. You can edit freely, chat with the AI, accept or reject proposals, and when you're happy, commit the draft to create a new baseline version. Until you commit, nothing changes.

`[SCREEN: Show the draft workspace — assumption fields on one side, an AI chat panel on the right]`

**Narrator:**
> Let's use the chat interface. In the message box, type: "Increase Year 2 revenue by 15% and reduce the COGS margin to 52%."

`[SCREEN: Click the chat input at the bottom of the AI panel. Type the instruction. Press Send. Show the AI thinking indicator for 1–2 seconds.]`

**Narrator:**
> The AI reads your instruction, identifies which assumptions it affects, and returns a set of structured proposals. Each proposal tells you exactly what it's changing, by how much, and with a confidence rating.

`[SCREEN: The AI response appears — a list of two proposals. Each shows: node name, current value, proposed value, confidence percentage. Example: "Annual Revenue Year 2: $5,000,000 → $5,750,000 (confidence: high)" and "COGS Margin: 55% → 52% (confidence: high)"]`

> **[CALLOUT: "Proposals show: what changes, from what, to what, and how confident the AI is"]**

**Narrator:**
> Review each proposal carefully. The AI is interpreting your instruction — it will almost always be correct for straightforward requests, but you are the analyst and you make the final call. Click "Accept" on the revenue proposal.

`[SCREEN: Click the green "Accept" button on the first proposal. The assumption field on the left updates to show the new value.]`

**Narrator:**
> Now let's say the COGS change doesn't align with your cost structure analysis. Click "Reject" on the COGS proposal.

`[SCREEN: Click the red "Reject" button on the second proposal. It's dismissed without updating the assumption.]`

**Narrator:**
> The AI accepted your instruction, proposed the changes, and you chose which ones to keep. That's the workflow: you direct, it proposes, you decide. Now let's commit this draft to create a new baseline version. Click "Commit Draft."

`[SCREEN: Click the "Commit Draft" button at the top. A confirmation modal appears summarising the accepted changes. Click Confirm.]`

> **[CALLOUT: "Committing creates a new, immutable baseline version — the old one is preserved"]**

**Narrator:**
> The draft is now committed. A new baseline version has been created with your accepted change — the Year 2 revenue increase — applied. The COGS margin remains as it was. The previous baseline version is still there, untouched, if you ever need to roll back. Every committed version is retained in the baseline history.

`[SCREEN: Navigate back to /baselines and show the version history — two versions listed with timestamps]`

**Narrator:**
> In the next module we'll run a Monte Carlo simulation to understand the range of possible outcomes for this model.

`[SCREEN: Fade to black with "Module 5: Monte Carlo & Sensitivity Analysis" title card]`

---

## Module 5 — Monte Carlo & Sensitivity Analysis (4 min)

**Narrator:**
> A standard model run gives you one answer — a deterministic output based on your specific input values. But in the real world, revenue doesn't hit exactly 5.75 million. It might be higher or lower depending on conditions outside your control. Monte Carlo simulation helps you understand the range of plausible outcomes.

`[SCREEN: Navigate to a run from the FY2026 baseline. Click the "Monte Carlo" tab or navigate to /runs/[id]/mc]`

> **[CALLOUT: "Monte Carlo: run the model thousands of times with varied inputs to see the distribution of outcomes"]**

**Narrator:**
> Here's how it works. You define a range of uncertainty for your key inputs — for example, revenue could be anywhere between 5% below and 15% above your base case. Virtual Analyst then runs your model thousands of times, sampling randomly from those ranges each time, and plots the full distribution of outcomes. You're not changing your model — you're stress-testing it.

`[SCREEN: Show the Monte Carlo configuration panel — input nodes listed with sliders or fields for min/max variance percentages. Set revenue variance to -5% / +15%.]`

**Narrator:**
> Configure the variance for Annual Revenue — let's say minus 5% on the downside and plus 15% on the upside. Leave other assumptions at their base case for now. Set the number of simulations to 1,000 and click Run Simulation.

`[SCREEN: Enter variance values. Set simulations to 1000. Click Run Simulation. A progress indicator appears. After a few seconds the results load.]`

**Narrator:**
> The results show you three key percentile outcomes: P10, P50, and P90. P50 is your median outcome — half of all simulated runs landed above this, half below. P10 means only 10% of simulations produced a result this low or lower. P90 means 90% of simulations were at or below this level. These percentiles help you have an honest conversation about risk — not "this is what will happen" but "this is the realistic range."

`[SCREEN: Show the Monte Carlo results — a bell curve or probability distribution chart for Gross Profit. Three vertical lines mark P10, P50, P90. Values labeled below each line.]`

> **[CALLOUT: "P10 = downside · P50 = median · P90 = upside"]**

**Narrator:**
> Now let's look at sensitivity. Click the Sensitivity tab.

`[SCREEN: Click the Sensitivity tab or navigate to /runs/[id]/sensitivity. A tornado chart loads.]`

**Narrator:**
> The tornado chart shows you which inputs have the greatest impact on your output — in this case Gross Profit. The longest bar is the assumption whose variance moves the needle most. This tells you where to focus your analytical attention and where to challenge your clients or your management team.

`[SCREEN: Show the tornado chart — horizontal bars for each assumption, sorted by absolute impact. Revenue bar is longest. COGS margin bar is second.]`

> **[CALLOUT: "The longer the bar, the more that assumption drives your outcome"]**

**Narrator:**
> A model with ten assumptions might have two or three that account for 80% of the variance. The tornado chart makes that visible immediately. In financial analysis, knowing what matters most is as important as knowing the numbers themselves.

`[SCREEN: Fade to black with "Module 6: Valuation (DCF)" title card]`

---

## Module 6 — Valuation (DCF) (3 min)

**Narrator:**
> Discounted Cash Flow valuation — DCF — is the most widely used intrinsic valuation method in finance. The core idea is straightforward: money you expect to receive in the future is worth less than money you have today, because of the time value of money and the risk that those future cash flows might not materialise. DCF converts your projected future cash flows into a present value using a discount rate.

`[SCREEN: Navigate to /runs/[id]/valuation. Show the valuation results page loading.]`

> **[CALLOUT: "DCF: future cash flows discounted to present value using WACC"]**

**Narrator:**
> Virtual Analyst computes the DCF from your model run automatically. The discount rate — known as the Weighted Average Cost of Capital, or WACC — is configurable in your valuation settings. The engine projects free cash flows from your model, discounts each year's cash flow back to today, and sums them to give you the Enterprise Value.

`[SCREEN: Show the DCF output — a table of projected free cash flows by year, the terminal value, and the sum showing Enterprise Value. The WACC is displayed prominently.]`

**Narrator:**
> Below the Enterprise Value you'll see the Equity Bridge. This converts the enterprise value — which represents the whole business, debt included — into the equity value, which is what shareholders actually own. The bridge subtracts net debt and adds back any surplus cash.

`[SCREEN: Scroll down to show the equity bridge — enterprise value, minus net debt, plus cash, equals equity value. Formatted as a simple waterfall.]`

> **[CALLOUT: "Equity Value = Enterprise Value − Net Debt + Cash"]**

**Narrator:**
> You can also run an exit multiples valuation as an alternative to the perpetuity growth model for terminal value. Toggle to Exit Multiples, enter an EBITDA multiple, and the terminal value recalculates accordingly. Many analysts run both methods and triangulate between them.

`[SCREEN: Toggle or click "Exit Multiples." Enter an EBITDA multiple, for example 8x. Watch the terminal value and enterprise value figures update.]`

> **[CALLOUT: "Exit multiple method: Terminal Value = EBITDA × multiple"]**

**Narrator:**
> The mid-year convention — which assumes cash flows arrive at the mid-point of each year rather than the end — is applied by default, which is standard practice and consistent with the CFA Institute's recommended DCF approach. You can see this reflected in the discount period exponents in the underlying calculation. All of this is transparent — there's no black box.

`[SCREEN: Fade to black with "Module 7: Budgeting Workflow" title card]`

---

## Module 7 — Budgeting Workflow (4 min)

**Narrator:**
> Virtual Analyst has a full budgeting module that takes a budget from initial draft through to an approved, active plan — with department allocations, actuals comparison, variance analysis, reforecasting, and AI-powered querying.

`[SCREEN: Click "Budgets" in the sidebar. Show the /budgets list page.]`

**Narrator:**
> Click "New Budget." Give it a name — "FY2026 Annual Budget" — select the financial year, and choose which departments are in scope. Click Create.

`[SCREEN: Click New Budget. Fill in the name field and year selector. Select two or three departments from a checklist. Click Create.]`

> **[CALLOUT: "Budget lifecycle: Draft → Submitted → Under Review → Approved → Active → Closed"]**

**Narrator:**
> Your budget starts in Draft status. You can add line items for each department — revenue targets, payroll, marketing spend, overheads — and allocate the annual total across monthly or quarterly periods. The platform enforces the structure: a submitted budget can't be re-opened to editing without moving back through the workflow.

`[SCREEN: Show the budget detail page in draft status. Add a line item — "Marketing Spend" — with an annual value of 480,000. Show the period allocation split across 12 months at 40,000 each.]`

**Narrator:**
> Once you've added all your line items, click "Submit for Review." The budget moves to Submitted status, a reviewer is notified, and the preparer can no longer edit it.

`[SCREEN: Click "Submit for Review." The status badge changes from Draft to Submitted. A toast notification confirms.]`

**Narrator:**
> The reviewer — typically a Finance Manager or CFO — opens the budget, reviews line items, and either approves or sends it back with comments. Let's jump ahead to the approved stage.

`[SCREEN: Navigate to the budget in Approved/Active status — or change the status via the reviewer workflow. Show the status badge now reading "Active."]`

**Narrator:**
> With the budget active, you can upload actual figures against each line item. The platform computes variance automatically — the difference between what you budgeted and what actually happened — both in absolute value and as a percentage. This is your live budget monitoring view.

`[SCREEN: Show the variance report — a table with columns: Line Item, Budget, Actual, Variance (£), Variance (%). Marketing Spend row shows budget 40,000 vs actual 47,000, variance -7,000 or -17.5%.]`

> **[CALLOUT: "Variance = Actual vs Budget — updated as actuals are uploaded"]**

**Narrator:**
> If conditions change mid-year, you can reforecast. A reforecast doesn't overwrite the original approved budget — it creates a revised projection alongside it, so you always have the audit trail of what was originally approved versus what you now expect.

`[SCREEN: Click "Reforecast." Show a side-by-side view — original budget column, reforecast column, variance between the two.]`

**Narrator:**
> Finally, try the AI query field at the top of the budget view. Type: "What is Marketing's projected full-year spend versus the approved budget?"

`[SCREEN: Type the query in the natural language input field. Press enter. A result panel returns a formatted answer with the numbers pulled from the budget data.]`

> **[CALLOUT: "Natural language queries — ask budget questions in plain English"]**

**Narrator:**
> The AI reads your live budget data and returns a direct, structured answer. No pivot tables. No VLOOKUP. Just ask the question and get the number.

`[SCREEN: Fade to black with "Module 8: Annual Financial Statements Module" title card]`

---

## Module 8 — Annual Financial Statements (AFS) Module (6 min)

**Narrator:**
> The Annual Financial Statements module — AFS — is built for accountants preparing statutory financial statements. It covers the full engagement lifecycle: framework selection, trial balance import, AI-assisted disclosure drafting, tax computation, multi-entity consolidation, multi-stage review, and output generation in PDF, Word, or iXBRL format for regulatory filing.

`[SCREEN: Click "AFS" in the sidebar. Show the /afs engagement list.]`

**Narrator:**
> Click "New Engagement." Enter the entity name, select the reporting framework — IFRS, IFRS for SMEs, US GAAP, or SA GAAP — and set the reporting period.

`[SCREEN: Click New Engagement. Type "Acme Holdings Ltd" as entity name. Select "IFRS" from the framework dropdown. Set period start 1 Jan 2025, period end 31 Dec 2025. Click Create.]`

> **[CALLOUT: "Frameworks: IFRS · IFRS-SME · US GAAP · SA GAAP"]**

**Narrator:**
> The engagement opens on the Setup tab. The first task is importing your trial balance. Click "Import Trial Balance" and upload a CSV file. The system expects account code, account name, and net balance columns. Once uploaded, the platform maps your accounts against the IFRS taxonomy automatically, and you can review and adjust any mappings before proceeding.

`[SCREEN: Click Import Trial Balance. A file upload dialog appears. Select a CSV file. It uploads and a mapping table appears — account names in the left column, IFRS category in the right column.]`

**Narrator:**
> With the trial balance imported and mapped, navigate to the Sections tab. This is where the AI Disclosure Drafter lives. Your AFS engagement has a set of required disclosure notes, pre-populated from the framework you selected. Each section shows its completion status.

`[SCREEN: Click the Sections tab. Show a list of sections: Revenue Recognition, Property Plant & Equipment, Related Party Transactions, Going Concern, etc. All showing "Not started" status.]`

**Narrator:**
> Click on "Revenue Recognition." The system shows the required disclosures for IFRS 15 for this section. Click "Draft Section" and watch what happens.

`[SCREEN: Click Revenue Recognition. Show the section detail page. Click Draft Section. A loading state appears with text "Drafting disclosure from trial balance data..."]`

> **[CALLOUT: "All figures in AI-drafted disclosures come from your trial balance — the AI writes the narrative"]**

**Narrator:**
> The AI reads your trial balance data — specifically the revenue accounts and their balances — and drafts a compliant disclosure note in plain prose. It never invents numbers. Every figure in the draft is sourced from the trial balance you uploaded. What the AI contributes is the language, structure, and compliance framework — the narrative and the form.

`[SCREEN: The drafted section appears — several paragraphs of disclosure text. References to IFRS 15 paragraph numbers are visible. Revenue figures match the TB amounts.]`

**Narrator:**
> Read through the draft. Edit any paragraph directly in the editor. If you want the AI to revise a section, type an instruction in the chat field — for example, "Add a paragraph on the timing of revenue recognition for long-term contracts." The AI revises and you approve. Repeat until the note is complete.

`[SCREEN: Type an instruction in the revision chat field. The AI returns a revised paragraph. Click Accept.]`

**Narrator:**
> When the section is satisfactory, mark it as complete and move to the next one. Now let's look at tax.

`[SCREEN: Click the Tax tab. Show the tax computation form.]`

**Narrator:**
> On the Tax tab, enter the entity's taxable income and the statutory tax rate. The platform computes current tax liability immediately. Below that, you can add temporary differences — items where the accounting carrying amount differs from the tax base — and the platform calculates the resulting deferred tax asset or liability per IAS 12.

`[SCREEN: Enter taxable income of 2,400,000. Enter statutory rate of 27%. Current tax appears as 648,000. Add a temporary difference — Depreciation timing difference, carrying amount 500,000, tax base 200,000. Deferred tax appears.]`

> **[CALLOUT: "Deferred tax: IAS 12 (IFRS) or ASC 740 (US GAAP) — computed automatically"]**

**Narrator:**
> Navigate to Review. The review workflow has three stages: Preparer, Manager, and Partner. Submit the engagement for manager review.

`[SCREEN: Click Review tab. Click "Submit for Review." Status changes. A reviewer notification is shown.]`

**Narrator:**
> The manager logs in, reviews each section and the tax computation, adds comments, and either approves or returns the engagement for corrections. This creates a full audit trail of who reviewed what and when.

`[SCREEN: Show the review interface — sections listed with reviewer comments. One section has a comment. Show the approve button.]`

**Narrator:**
> Once all stages are approved, go to the Output tab. Choose your format — PDF for client delivery, DOCX for further editing in Word, or iXBRL if you're preparing a machine-readable regulatory filing such as for CIPC or HMRC. Click Generate.

`[SCREEN: Click Output tab. Select PDF. Click Generate. A loading indicator. Then a download button appears. Click Download — the PDF preview shows a cover page with entity name, period, and framework. Scroll to show a table of contents and the Revenue Recognition note.]`

> **[CALLOUT: "Output formats: PDF · DOCX · iXBRL (XBRL-tagged for regulatory filing)"]**

**Narrator:**
> Finally, the Analytics tab. This shows sixteen financial ratios computed from your trial balance — current ratio, debt-to-equity, gross margin, return on equity, and more — alongside industry benchmark comparisons and an AI-generated going concern assessment. If any ratio falls outside the expected range, the platform flags it for your attention.

`[SCREEN: Click Analytics tab. Show the ratio dashboard — a grid of ratio cards, each with the computed value, the industry benchmark, and a status indicator (green/amber/red). Scroll to the Going Concern Assessment section — a paragraph of AI-generated text.]`

> **[CALLOUT: "Analytics: 16 ratios + industry benchmarks + AI going concern assessment"]**

**Narrator:**
> That is the full AFS workflow — from trial balance to signed-off, ready-to-file annual financial statements, with AI assistance at every step that requires judgment and language, and deterministic computation at every step that requires precision.

`[SCREEN: Fade to black with "Module 9: Board Packs" title card]`

---

## Module 9 — Board Packs (3 min)

**Narrator:**
> Board Packs brings together your financial model outputs, budget performance, and narrative commentary into a single, branded, board-ready document — and automates its distribution to board members on a schedule.

`[SCREEN: Click "Board Packs" in the sidebar. Show the /board-packs list.]`

**Narrator:**
> Click "New Board Pack." Give it a name — "Q1 2026 Board Report" — and select the data sources: the FY2026 model baseline and the FY2026 budget.

`[SCREEN: Click New Board Pack. Name it "Q1 2026 Board Report." Select the baseline and budget from dropdown lists. Click Create.]`

**Narrator:**
> The Board Pack composer opens. On the left is a section palette — Executive Summary, Income Statement, Balance Sheet, Cash Flow Statement, KPIs, Budget Variance, and more. Drag the sections you want into the report.

`[SCREEN: Show the composer. Drag "Executive Summary" into the report area. Then drag "Income Statement," "KPI Dashboard," and "Budget Variance." The sections stack in the report preview.]`

> **[CALLOUT: "Drag sections from the palette to build your pack"]**

**Narrator:**
> Click on the Executive Summary section and click "Generate Narrative." The AI reads your financial data — revenue, margins, cash position, variance against budget — and writes a board-appropriate commentary paragraph. Edit it as you see fit. The AI gives you a first draft; the final words are yours.

`[SCREEN: Click Executive Summary section. Click Generate Narrative. Loading state. A paragraph appears summarising the quarter's financial performance. Edit one sentence directly in the editor.]`

**Narrator:**
> Apply your branding. Upload a logo, set the primary colour, and choose a font. These settings persist across all future board packs for your organisation.

`[SCREEN: Click Settings/Branding. Upload a logo file. Set a hex colour. Preview updates to show branded header.]`

> **[CALLOUT: "Branding persists — set once, apply to every board pack"]**

**Narrator:**
> When the pack is ready, click Export. Choose PDF for print, PPTX to use in PowerPoint, or HTML for online sharing. Set up a scheduled distribution — for example, send this pack to the full board on the 15th of each month — and Virtual Analyst will generate and email it automatically.

`[SCREEN: Click Export. Select PDF. Click Download. Then navigate to the Schedule tab — set distribution to the 15th of each month. Add three email addresses. Click Save Schedule.]`

**Narrator:**
> Board Packs removes the manual effort of assembling a board report from scratch each quarter. The data updates automatically from your model and budget. The AI narrates the story. You focus on the analysis.

`[SCREEN: Fade to black with "Module 10: Team Collaboration & Roles" title card]`

---

## Module 10 — Team Collaboration & Roles (2 min)

**Narrator:**
> Virtual Analyst is built for teams. Multiple analysts can work in the same workspace, collaborate on models, assign tasks, and review each other's work — all within a structured workflow.

`[SCREEN: Click "Teams" in the sidebar. Show the /teams page — a list of current team members with their role badges.]`

**Narrator:**
> To add a team member, click "Invite User." Enter their email address and select a role. They'll receive an email invitation and join your workspace with the permissions appropriate to that role.

`[SCREEN: Click Invite User. Enter an email address. Select "Analyst" from the role dropdown. Click Send Invitation.]`

> **[CALLOUT: "Roles: Owner (full access) · Admin (manage workspace) · Analyst (build & run) · Investor (read only)"]**

**Narrator:**
> Workflow templates let you define repeatable processes — for example, a Month-End Close workflow with tasks for trial balance reconciliation, management accounts preparation, and sign-off. Create a template once and instantiate it each month.

`[SCREEN: Click "Workflows" in the sidebar. Show the /workflows list. Click on an existing template. Show the task list — each task has an assignee, due date, and status.]`

**Narrator:**
> Assign a task to an analyst. They receive a notification in their inbox. When they mark it complete, the next task in the workflow activates and the relevant reviewer is notified. The full history of who did what and when is retained.

`[SCREEN: Click on a task. Assign it to a team member from a dropdown. Save. Navigate to /inbox or notifications. Show a notification card for the assigned task.]`

> **[CALLOUT: "Full audit trail — who did what, when, and in what order"]**

**Narrator:**
> Notifications appear in the inbox — task assignments, review requests, budget approvals, and board pack distributions all surface here, so nothing falls through the cracks.

`[SCREEN: Fade to black with "Module 11: Integrations — Xero & QuickBooks" title card]`

---

## Module 11 — Integrations (Xero / QuickBooks) (2 min)

**Narrator:**
> Virtual Analyst connects directly to Xero and QuickBooks Online, pulling your actual financial data into the platform so you can compare it against your models and budgets without manual exports.

`[SCREEN: Click "Integrations" in the sidebar. Show the /integrations page — Xero and QuickBooks tiles with Connect buttons.]`

**Narrator:**
> Click "Connect Xero." You'll be redirected to Xero's authentication page. Log in with your Xero credentials and authorise Virtual Analyst to read your financial data. You'll be returned to Virtual Analyst automatically.

`[SCREEN: Click Connect Xero. Show a mock Xero authorisation screen. Click Allow Access. Redirect back to /integrations. The Xero tile now shows "Connected" with a green status indicator.]`

> **[CALLOUT: "OAuth connection — your credentials never touch Virtual Analyst's servers"]**

**Narrator:**
> With Xero connected, click "Sync Now." Virtual Analyst pulls your chart of accounts, P&L actuals, and balance sheet figures from Xero and stores them as a canonical snapshot. A canonical snapshot is a point-in-time copy of your accounting data — it doesn't change as Xero updates, so you always know exactly what data your analysis is based on.

`[SCREEN: Click Sync Now. A progress indicator. Then a success message: "Sync complete — 847 transactions imported." Show the canonical snapshot record with date and record count.]`

> **[CALLOUT: "Canonical snapshot: immutable point-in-time copy of your accounting actuals"]**

**Narrator:**
> Once synced, your actuals flow automatically into the Budget Variance report — comparing what Xero shows against what you budgeted. No copy-paste. No CSV exports. No version mismatches. The same integration works for QuickBooks Online — the connect flow is identical.

`[SCREEN: Navigate to /budgets, open the FY2026 budget. Show the Actuals column now populated with real Xero figures. The Variance column shows computed differences.]`

**Narrator:**
> If your accounting system isn't Xero or QuickBooks, you can always import actuals manually via CSV. The integration is a convenience, not a requirement.

`[SCREEN: Fade to black with "Module 12: Tips, Shortcuts & Where to Get Help" title card]`

---

## Module 12 — Tips, Shortcuts & Where to Get Help (1 min)

**Narrator:**
> Three things that will save you significant time once you start using Virtual Analyst regularly.

`[SCREEN: Show the draft AI chat interface]`

**Narrator:**
> First: use the AI draft layer to explore before you commit. Before changing a baseline that others depend on, open a draft, ask the AI to model the scenario, review the impact, and only commit if it's right. It costs nothing to explore.

`[SCREEN: Navigate to /afs, show the engagement list]`

**Narrator:**
> Second: when preparing this year's AFS, use the Roll-Forward feature. One click copies last year's engagement — sections, framework, structure — into a new engagement for the current period. You edit and update rather than starting from scratch. It can cut AFS preparation time significantly.

> **[CALLOUT: "Roll-forward: copy last year's AFS engagement with one click"]**

`[SCREEN: Navigate to /runs/[id]/sensitivity, show the tornado chart]`

**Narrator:**
> Third: read the sensitivity tornado chart before you build a detailed model. It tells you which three assumptions will drive 80% of the variance in your output. Invest your modeling time there first.

> **[CALLOUT: "Focus your precision where the tornado chart tells you it matters most"]**

**Narrator:**
> If you get stuck, the in-app help icon in the bottom right corner opens contextual guidance for whatever page you're on. For technical support or to report an issue, contact your workspace administrator or reach the Virtual Analyst support team through the Settings page. Thank you for completing this training series — you're ready to build.

`[SCREEN: Show the support/help section in Settings. Fade to the VA logo on dark background. Hold for 3 seconds. Fade to black.]`

---

## A. Chapter Timestamps

```
00:00 — Module 1:  Welcome & Platform Overview
02:00 — Module 2:  Logging In & Account Setup
04:00 — Module 3:  Building Your First Financial Model
09:00 — Module 4:  AI-Assisted Assumption Editing
13:00 — Module 5:  Monte Carlo & Sensitivity Analysis
17:00 — Module 6:  Valuation (DCF)
20:00 — Module 7:  Budgeting Workflow
24:00 — Module 8:  Annual Financial Statements (AFS) Module
30:00 — Module 9:  Board Packs
33:00 — Module 10: Team Collaboration & Roles
35:00 — Module 11: Integrations — Xero & QuickBooks
37:00 — Module 12: Tips, Shortcuts & Where to Get Help
38:00 — End
```

---

## B. On-Screen Lower-Third Text

| Module | Key Terms (lower-thirds) |
|---|---|
| 1 — Overview | "Deterministic Engine" · "AI Draft Layer" · "Three-Statement Output" |
| 2 — Login | "RBAC Roles" · "SAML SSO" · "Supabase Auth" |
| 3 — First Model | "Baseline" · "Node" · "Run" |
| 4 — AI Drafting | "Draft Session" · "Proposal" · "Commit" |
| 5 — Monte Carlo | "P10 / P50 / P90" · "Monte Carlo Simulation" · "Tornado Chart" |
| 6 — Valuation | "DCF" · "WACC" · "Equity Bridge" |
| 7 — Budgeting | "Budget Lifecycle" · "Variance Analysis" · "Reforecast" |
| 8 — AFS | "Trial Balance" · "Disclosure Note" · "iXBRL" |
| 9 — Board Packs | "Composer" · "AI Narrative" · "Scheduled Distribution" |
| 10 — Teams | "Workflow Template" · "Task Assignment" · "Audit Trail" |
| 11 — Integrations | "OAuth" · "Canonical Snapshot" · "Actuals Sync" |
| 12 — Tips | "Roll-Forward" · "Sensitivity Tornado" · "Draft Before Commit" |

---

## C. 60-Second Teaser Script

*Standalone short-form version — suitable for a LinkedIn video post. Narration only, no screen directions required.*

---

> If you're a financial analyst or accountant who still builds models in spreadsheets, compiles board packs manually, or drafts AFS disclosures from scratch — this is for you.

> Virtual Analyst is a financial modeling platform that combines a deterministic three-statement engine with an AI assistant. Your model computes exactly the right answer, every time. The AI helps you get there faster — drafting assumptions, writing disclosure notes, generating board narrative — but you review every output and approve every change before anything is committed.

> You can run Monte Carlo simulations to stress-test your projections. You can value a business using DCF with a single click. You can import a trial balance and have an AI draft your IFRS revenue recognition note in under thirty seconds, referencing the right paragraphs of the right standard. You can connect Xero or QuickBooks and see your actuals against your budget in real time.

> It's built for professionals who need both speed and precision. The deterministic engine never approximates. The AI never publishes without your approval. And the audit trail captures everything — every version, every change, every sign-off.

> Virtual Analyst. www.virtual-analyst.ai. Free to try.

---

## D. Quiz Questions

*One multiple-choice question per module. For use in an LMS or post-module knowledge check.*

---

### Module 1 — Welcome & Platform Overview

What best describes the relationship between the deterministic engine and the AI layer in Virtual Analyst?

- A) The AI replaces manual calculations entirely
- B) The engine and AI are interchangeable depending on task type
- **C) The engine computes deterministically; the AI assists with drafting and narrative** ✓
- D) The AI runs the financial model and the engine formats the output

> **Explanation:** The engine always produces the same output from the same inputs — no randomness, no approximation. The AI layer assists with language, proposals, and narrative, but every AI output requires human review before it affects a baseline or a filed document.

---

### Module 2 — Logging In & Account Setup

An external investor needs read-only access to your published model outputs but must not be able to edit any model or budget. Which role should they be assigned?

- A) Analyst
- B) Admin
- **C) Investor** ✓
- D) Owner

> **Explanation:** The Investor role provides read-only access to published outputs. Analyst, Admin, and Owner roles all have write permissions of varying scope.

---

### Module 3 — Building Your First Financial Model

What is a Baseline in Virtual Analyst?

- A) A budget approved by the CFO
- **B) A versioned snapshot of a model's structure and assumptions** ✓
- C) The actual financial results imported from Xero
- D) A Monte Carlo simulation configuration

> **Explanation:** A Baseline contains the node graph, formulas, and input values that define your model. Each committed Draft creates a new Baseline version, preserving all previous versions.

---

### Module 4 — AI-Assisted Assumption Editing

An analyst uses the AI draft chat to request a change to revenue assumptions. The AI returns two proposals. The analyst accepts one and rejects the other, then closes the draft without committing. What happens to the baseline?

- A) The accepted proposal is applied to the baseline immediately
- B) Both proposals are discarded
- **C) Nothing — the baseline is unchanged until the draft is explicitly committed** ✓
- D) The accepted proposal is saved but requires a second approval step

> **Explanation:** Drafts are sandboxes. Nothing affects the baseline until the analyst explicitly clicks Commit Draft. Closing a draft without committing leaves the baseline exactly as it was.

---

### Module 5 — Monte Carlo & Sensitivity Analysis

In a Monte Carlo simulation result, what does P10 represent?

- A) The most likely outcome based on your base case inputs
- B) The outcome if the top 10% of assumptions are used
- **C) The level at or below which 10% of all simulated outcomes fell** ✓
- D) A 10% probability that the business will fail

> **Explanation:** P10 is the 10th percentile — meaning only 10% of simulated runs produced an outcome at or below this level. It represents the downside scenario within the range of modeled uncertainty.

---

### Module 6 — Valuation (DCF)

What does the Equity Bridge in the DCF output calculate?

- A) The present value of future dividends
- B) The WACC adjusted for the debt-to-equity ratio
- **C) The equity value derived by subtracting net debt and adding cash to enterprise value** ✓
- D) The difference between book value and market value of equity

> **Explanation:** Enterprise Value represents the whole business including debt. The Equity Bridge subtracts net debt and adds surplus cash to arrive at the value attributable to equity holders specifically.

---

### Module 7 — Budgeting Workflow

A budget has been submitted for review. Can the preparer edit line items at this stage?

- **A) No — a submitted budget is locked from editing until returned by the reviewer** ✓
- B) Yes — the preparer retains edit access throughout the review
- C) Yes — but only if the reviewer has not yet opened the budget
- D) No — and the budget must be recreated from scratch if changes are needed

> **Explanation:** The budget lifecycle is a one-way state machine. Once submitted, the preparer loses edit access. If the reviewer requires changes, they return the budget to Draft status, at which point the preparer can edit again.

---

### Module 8 — Annual Financial Statements (AFS)

When the AI drafts a disclosure note in the AFS module, where do the financial figures in the draft come from?

- A) The AI estimates figures based on industry benchmarks
- B) The AI requests figures from the connected Xero integration
- **C) All figures come from the trial balance the preparer uploaded** ✓
- D) The AI generates indicative figures that the preparer must replace manually

> **Explanation:** The AI disclosure drafter reads the trial balance data directly. It never invents or estimates figures — every number in the draft is sourced from the TB. The AI's role is to write the compliant narrative around those figures.

---

### Module 9 — Board Packs

What is the purpose of a Canonical Snapshot in the context of Board Packs and Integrations?

- A) A live feed of data from Xero that updates in real time
- **B) An immutable, point-in-time copy of accounting data that the analysis is based on** ✓
- C) A PDF snapshot of a board pack at the time of distribution
- D) A version-controlled copy of the financial model baseline

> **Explanation:** A canonical snapshot captures accounting data at a specific moment and freezes it. This ensures that the analysis in a board pack is always traceable to a known, unchanging dataset — critical for audit and governance purposes.

---

### Module 10 — Team Collaboration & Roles

A workflow task has been assigned to an analyst and is now marked as complete. What happens next?

- A) The workflow is closed and archived automatically
- **B) The next task in the workflow activates and the relevant reviewer is notified** ✓
- C) The task returns to the preparer for self-review
- D) Nothing — workflow progression requires manual intervention from the Owner

> **Explanation:** Workflows are sequential. Completing one task automatically activates the next and triggers a notification to the assigned person. The Owner does not need to intervene in normal task-to-task transitions.

---

### Module 11 — Integrations

After connecting Xero and running a sync, an analyst notices that an invoice posted to Xero three days later is not reflected in Virtual Analyst's budget actuals. Why?

- **A) Syncs create canonical snapshots at a point in time — the invoice wasn't in Xero at sync time** ✓
- B) Xero only syncs invoices, not journal entries
- C) Virtual Analyst only syncs data from the previous financial year
- D) The analyst needs to reconnect the Xero integration to refresh

> **Explanation:** Canonical snapshots are immutable — they capture the state of Xero data at the moment of sync. Data added to Xero after the sync is not retroactively included. The analyst must run a new sync to capture recent transactions.

---

### Module 12 — Tips, Shortcuts & Where to Get Help

What does the AFS Roll-Forward feature do?

- A) Automatically files the previous year's AFS with the relevant regulator
- B) Generates a comparative column in the current year's financial statements from the prior year's TB
- **C) Copies the prior year's AFS engagement structure into a new engagement for the current period** ✓
- D) Rolls forward the budget actuals into the new financial year's opening balances

> **Explanation:** Roll-Forward creates a new AFS engagement pre-populated with last year's sections, framework selection, and structure. The preparer updates the trial balance and reviews each section rather than starting from a blank engagement.
