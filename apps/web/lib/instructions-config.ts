/**
 * Maps page routes to structured manual content for the Instructions drawer.
 * Content is derived from docs/user-manual/ chapters and should be kept in sync.
 */

export interface InstructionPrerequisite {
  label: string;
  href: string;
}

export interface InstructionSection {
  /** Chapter title shown at the top of the drawer */
  title: string;
  /** Chapter number for reference */
  chapter: string;
  /** Brief overview of what this page does */
  overview: string;
  /** Step-by-step guide for using the page */
  steps: string[];
  /** Pages/processes that must be completed before this one */
  prerequisites: InstructionPrerequisite[];
  /** Related pages the user might want to visit next */
  relatedPages: InstructionPrerequisite[];
  /** Quick tips for power users */
  tips?: string[];
}

/**
 * Match a pathname to its instruction config.
 * Routes are matched from most specific to least specific.
 */
export function getInstructionsForPath(pathname: string): InstructionSection | null {
  // Normalize: strip trailing slash
  const p = pathname.replace(/\/$/, "") || "/dashboard";

  // Try exact match first, then progressively broader patterns
  for (const [pattern, config] of Object.entries(INSTRUCTIONS_MAP)) {
    if (pattern === p) return config;
  }

  // Dynamic route matching: /runs/[id]/mc → check /runs/*/mc pattern
  for (const [pattern, config] of Object.entries(INSTRUCTIONS_MAP)) {
    const regex = new RegExp(
      "^" + pattern.replace(/\*/g, "[^/]+") + "$"
    );
    if (regex.test(p)) return config;
  }

  return null;
}

// ─── Route → Instructions Map ───────────────────────────────────────

const INSTRUCTIONS_MAP: Record<string, InstructionSection> = {
  // ── SETUP ──────────────────────────────────────

  "/dashboard": {
    title: "Dashboard",
    chapter: "02",
    overview:
      "Your home screen showing summary cards for recent runs, pending tasks, unread notifications, and performance metrics. Use it to quickly navigate to your most important items.",
    steps: [
      "Review the summary cards at the top for a snapshot of your account activity.",
      "Check Recent Runs to see your latest model executions and their status.",
      "View Pending Assignments for tasks that need your attention.",
      "Click any item to navigate directly to the relevant detail page.",
    ],
    prerequisites: [
      { label: "Create an account and log in", href: "/login" },
    ],
    relatedPages: [
      { label: "Runs", href: "/runs" },
      { label: "Baselines", href: "/baselines" },
      { label: "Inbox", href: "/inbox" },
    ],
    tips: [
      "The dashboard auto-refreshes when you navigate back to it.",
      "Click notification badges to jump straight to unread items.",
    ],
  },

  "/marketplace": {
    title: "Marketplace",
    chapter: "03",
    overview:
      "Browse and apply pre-built financial templates by industry and type. Each template creates a baseline with pre-configured revenue streams, cost items, and assumptions.",
    steps: [
      "Browse or search templates by industry (SaaS, Consulting, Retail, etc.).",
      "Click a template card to view its details and structure.",
      "Click \"Use Template\" to create a new baseline from the template.",
      "Enter a label and fiscal year for your new baseline.",
      "The system creates the baseline with all template line items pre-populated.",
    ],
    prerequisites: [],
    relatedPages: [
      { label: "Baselines", href: "/baselines" },
      { label: "Import Excel", href: "/excel-import" },
      { label: "Ventures", href: "/ventures" },
    ],
    tips: [
      "Templates are organized by industry — use the search bar to filter.",
      "After applying a template, customize the baseline's assumptions in a draft.",
    ],
  },

  "/excel-import": {
    title: "Import Excel",
    chapter: "04",
    overview:
      "Upload Excel workbooks through an AI-assisted multi-step import wizard. The system detects revenue streams, cost items, and CapEx lines, then lets you review and confirm mappings before creating a baseline.",
    steps: [
      "Click \"Upload\" and select your Excel (.xlsx) file.",
      "The AI analyzes your spreadsheet structure and identifies financial line items.",
      "Review the detected mappings: revenue streams, costs, and capital expenditures.",
      "Adjust any mis-categorized items using the dropdown selectors.",
      "Confirm mappings and provide a baseline label and fiscal year.",
      "Click \"Create Baseline\" to finalize the import.",
    ],
    prerequisites: [],
    relatedPages: [
      { label: "Baselines", href: "/baselines" },
      { label: "Excel Connections", href: "/excel-connections" },
      { label: "Marketplace Templates", href: "/marketplace" },
    ],
    tips: [
      "Use clean, well-structured Excel files for the best AI mapping results.",
      "You can re-upload and re-map if the initial detection isn't correct.",
    ],
  },

  "/excel-connections": {
    title: "Excel Live Connections",
    chapter: "05",
    overview:
      "Create persistent bidirectional sync links between Excel workbooks and your financial model runs or baselines. Pull live values from Excel or push changes back.",
    steps: [
      "Click \"New Connection\" to start linking an Excel workbook.",
      "Select the source workbook and target baseline or run.",
      "Map Excel cells/ranges to financial model fields.",
      "Configure sync direction (pull, push, or bidirectional).",
      "Save the connection — it syncs automatically on the configured schedule.",
    ],
    prerequisites: [
      { label: "Create a baseline first", href: "/baselines" },
    ],
    relatedPages: [
      { label: "Import Excel", href: "/excel-import" },
      { label: "Baselines", href: "/baselines" },
    ],
  },

  "/afs": {
    title: "AFS Module",
    chapter: "06",
    overview:
      "Annual Financial Statements module. Create engagements for IFRS or GAAP-compliant disclosure drafting, manage sections, run tax computations, consolidate multi-entity structures, and generate PDF/DOCX/iXBRL output.",
    steps: [
      "Click \"New Engagement\" to create a new AFS engagement.",
      "Complete the setup wizard: select framework (IFRS/GAAP), fiscal year, and entities.",
      "Use the AI Disclosure Drafter to generate initial section content.",
      "Review and edit sections in the section editor.",
      "Run tax computations and generate AI tax notes.",
      "For multi-entity structures, use the consolidation module.",
      "Generate final output in PDF, DOCX, or iXBRL format.",
    ],
    prerequisites: [],
    relatedPages: [
      { label: "AFS Review & Tax", href: "/afs" },
      { label: "AFS Consolidation & Output", href: "/afs" },
      { label: "Org Structures", href: "/org-structures" },
    ],
  },

  "/afs/*/setup": {
    title: "AFS Setup",
    chapter: "06",
    overview:
      "Configure your AFS engagement: select the reporting framework, fiscal year, reporting entity, and applicable disclosure sections.",
    steps: [
      "Select the reporting framework (IFRS or GAAP).",
      "Set the fiscal year and reporting period.",
      "Choose the reporting entity (or group for consolidation).",
      "Select which disclosure sections to include.",
      "Save the configuration to proceed to section editing.",
    ],
    prerequisites: [
      { label: "Create an AFS engagement", href: "/afs" },
    ],
    relatedPages: [
      { label: "AFS Sections", href: "/afs" },
      { label: "Org Structures (for groups)", href: "/org-structures" },
    ],
  },

  "/afs/*/sections": {
    title: "AFS Section Editor",
    chapter: "06",
    overview:
      "Edit disclosure sections with AI assistance. Each section corresponds to a specific IFRS or GAAP disclosure requirement. Use the AI drafter to generate initial content, then review and refine.",
    steps: [
      "Select a section from the list to open it in the editor.",
      "Click \"AI Draft\" to generate initial content using the AI Disclosure Drafter.",
      "Review the generated content for accuracy and completeness.",
      "Edit the text directly in the editor to make adjustments.",
      "Mark sections as complete when you're satisfied with the content.",
    ],
    prerequisites: [
      { label: "Complete AFS setup", href: "/afs" },
    ],
    relatedPages: [
      { label: "AFS Review", href: "/afs" },
      { label: "AFS Tax", href: "/afs" },
    ],
  },

  "/afs/*/review": {
    title: "AFS Review Workflow",
    chapter: "07",
    overview:
      "Three-stage review workflow for AFS sections. Route sections through preparer, reviewer, and approver stages with role-based sign-off and feedback.",
    steps: [
      "Submit completed sections for review.",
      "Reviewers receive notifications and can approve or request changes.",
      "Address any feedback and resubmit.",
      "Final approver signs off on the section.",
      "Track review status across all sections on the review dashboard.",
    ],
    prerequisites: [
      { label: "Complete AFS sections", href: "/afs" },
    ],
    relatedPages: [
      { label: "AFS Tax Computation", href: "/afs" },
      { label: "AFS Output", href: "/afs" },
    ],
  },

  "/afs/*/tax": {
    title: "AFS Tax Computation",
    chapter: "07",
    overview:
      "Run tax computations and generate AI-powered tax notes. The system calculates current and deferred tax based on your financial data and generates disclosure-ready tax notes.",
    steps: [
      "Review the pre-populated financial data for tax computation.",
      "Configure tax rates and jurisdiction-specific rules.",
      "Click \"Run Tax Computation\" to calculate current and deferred tax.",
      "Review the computed figures and adjustment entries.",
      "Click \"Generate Tax Notes\" for AI-drafted disclosure notes.",
      "Edit and finalize the tax notes in the section editor.",
    ],
    prerequisites: [
      { label: "Complete AFS sections", href: "/afs" },
    ],
    relatedPages: [
      { label: "AFS Review", href: "/afs" },
      { label: "AFS Output", href: "/afs" },
    ],
  },

  "/afs/*/consolidation": {
    title: "AFS Multi-Entity Consolidation",
    chapter: "08",
    overview:
      "Consolidate financial statements across multiple entities in a group structure. Define intercompany eliminations and generate consolidated disclosures.",
    steps: [
      "Ensure all subsidiary entities have completed their individual AFS.",
      "Select the parent entity and subsidiaries for consolidation.",
      "Define intercompany eliminations and adjustments.",
      "Run the consolidation process.",
      "Review the consolidated trial balance and financial statements.",
    ],
    prerequisites: [
      { label: "Complete individual entity AFS", href: "/afs" },
      { label: "Set up Org Structures", href: "/org-structures" },
    ],
    relatedPages: [
      { label: "AFS Output", href: "/afs" },
      { label: "Org Structures", href: "/org-structures" },
    ],
  },

  "/afs/*/output": {
    title: "AFS Output Generation",
    chapter: "08",
    overview:
      "Generate final financial statement outputs in PDF, DOCX, or iXBRL format. Customize formatting, select included sections, and download or share the generated documents.",
    steps: [
      "Select the output format: PDF, DOCX, or iXBRL.",
      "Choose which sections to include in the output.",
      "Configure formatting options (cover page, headers, numbering).",
      "Click \"Generate\" to create the output document.",
      "Download the generated file or share it directly.",
    ],
    prerequisites: [
      { label: "Complete and review all AFS sections", href: "/afs" },
    ],
    relatedPages: [
      { label: "Documents", href: "/documents" },
      { label: "AFS Review", href: "/afs" },
    ],
  },

  "/afs/*/analytics": {
    title: "AFS Analytics",
    chapter: "06",
    overview:
      "View analytics and benchmarking data for your AFS engagement. Compare key financial metrics against industry peers and track engagement progress.",
    steps: [
      "Review the engagement progress dashboard.",
      "Explore financial ratio comparisons against industry benchmarks.",
      "Export analytics data for external reporting.",
    ],
    prerequisites: [
      { label: "Complete AFS sections with financial data", href: "/afs" },
    ],
    relatedPages: [
      { label: "Benchmarking", href: "/benchmark" },
      { label: "AFS Sections", href: "/afs" },
    ],
  },

  "/afs/frameworks": {
    title: "AFS Frameworks",
    chapter: "06",
    overview:
      "Manage reporting frameworks (IFRS, GAAP, and custom frameworks) used across your AFS engagements. View available frameworks, their sections, and configuration options.",
    steps: [
      "Browse available frameworks (IFRS, GAAP, etc.).",
      "Click a framework to view its disclosure sections and requirements.",
      "Custom frameworks can be configured in Settings.",
    ],
    prerequisites: [],
    relatedPages: [
      { label: "AFS Module", href: "/afs" },
      { label: "Settings", href: "/settings" },
    ],
  },

  "/org-structures": {
    title: "Organizational Structures",
    chapter: "09",
    overview:
      "Manage organizational hierarchies — define parent-subsidiary relationships, entity groupings, and consolidation rules for multi-entity reporting.",
    steps: [
      "Click \"New Group\" to create an organizational structure.",
      "Add the parent entity and subsidiaries.",
      "Define ownership percentages and consolidation methods.",
      "Set up intercompany relationship rules.",
      "Save the structure for use in AFS consolidation and group reporting.",
    ],
    prerequisites: [],
    relatedPages: [
      { label: "AFS Consolidation", href: "/afs" },
      { label: "Entity Comparison", href: "/compare" },
    ],
  },

  // ── CONFIGURE ──────────────────────────────────

  "/baselines": {
    title: "Baselines",
    chapter: "10",
    overview:
      "Your master data records. Each baseline holds a complete set of financial line items and assumptions. Baselines are the foundation of every financial model — all drafts, scenarios, and runs originate from a baseline.",
    steps: [
      "Browse your baselines in the list view with search and pagination.",
      "Click a baseline to view its detail page with configuration and version history.",
      "To create a new baseline, use the Marketplace, Import Excel, or Ventures page.",
      "Baselines are immutable — to make changes, create a draft from a baseline.",
    ],
    prerequisites: [
      { label: "Import data via Marketplace, Excel Import, or Ventures", href: "/marketplace" },
    ],
    relatedPages: [
      { label: "Drafts", href: "/drafts" },
      { label: "Scenarios", href: "/scenarios" },
      { label: "Runs", href: "/runs" },
    ],
    tips: [
      "Baselines are versioned — committing a draft creates a new baseline version.",
      "Use search to quickly find baselines by label or entity name.",
    ],
  },

  "/baselines/*": {
    title: "Baseline Detail",
    chapter: "10",
    overview:
      "View a baseline's complete configuration: line items, assumptions, version history, and associated drafts. From here you can create a new draft or view run history.",
    steps: [
      "Review the baseline's financial line items and assumptions.",
      "Check the version history to see how the baseline has evolved.",
      "Click \"New Draft\" to create a working copy for modifications.",
      "View associated runs and their results.",
    ],
    prerequisites: [
      { label: "Create a baseline", href: "/baselines" },
    ],
    relatedPages: [
      { label: "Drafts", href: "/drafts" },
      { label: "Runs", href: "/runs" },
      { label: "Changesets", href: "/changesets" },
    ],
  },

  "/drafts": {
    title: "Drafts",
    chapter: "11",
    overview:
      "Working copies of baselines where you adjust assumptions, tweak drivers, and prepare for analysis runs. Drafts include AI chat assistance for exploring your financial model.",
    steps: [
      "View your active drafts in the list.",
      "Click a draft to open the editor.",
      "To create a new draft, go to a Baseline detail page and click \"New Draft\".",
      "Adjust assumptions and line items in the draft editor.",
      "Use the AI Chat panel to ask questions about your model.",
      "When ready, click \"Mark Ready\" then \"Commit Draft\" to save as a new baseline version.",
    ],
    prerequisites: [
      { label: "Create a baseline first", href: "/baselines" },
    ],
    relatedPages: [
      { label: "Baselines", href: "/baselines" },
      { label: "Scenarios", href: "/scenarios" },
      { label: "Runs", href: "/runs" },
    ],
    tips: [
      "Run Integrity Checks before committing to catch errors early.",
      "The AI chat can explain line items and suggest assumption adjustments.",
    ],
  },

  "/drafts/*": {
    title: "Draft Editor",
    chapter: "11",
    overview:
      "Edit a draft's assumptions, review integrity checks, use AI chat for guidance, and commit changes to create a new baseline version. The editor shows all line items organized by category.",
    steps: [
      "Review and adjust assumptions in the line item table.",
      "Use the AI Chat panel (right side) to ask questions about your model.",
      "Add comments in the Comments section for collaboration.",
      "Click \"Run Integrity Checks\" to validate your changes.",
      "Resolve any errors or warnings flagged by the checks.",
      "Click \"Mark Ready\" to indicate the draft is ready for review.",
      "Click \"Commit Draft\" to save as a new baseline version.",
    ],
    prerequisites: [
      { label: "Create a baseline", href: "/baselines" },
      { label: "Create a draft from a baseline", href: "/drafts" },
    ],
    relatedPages: [
      { label: "Baselines", href: "/baselines" },
      { label: "Scenarios", href: "/scenarios" },
      { label: "Runs", href: "/runs" },
    ],
    tips: [
      "The comment thread is shared with your team — use it for review discussions.",
      "Integrity checks catch formula errors, missing drivers, and data inconsistencies.",
      "Committing is irreversible — it creates a permanent new baseline version.",
    ],
  },

  "/scenarios": {
    title: "Scenarios",
    chapter: "12",
    overview:
      "Define alternative assumption sets (best case, worst case, base case) to compare outcomes side by side. Scenarios let you test different business conditions against the same baseline.",
    steps: [
      "Click \"New Scenario\" to create a scenario.",
      "Select the base baseline to build your scenario from.",
      "Override specific assumptions (e.g., revenue growth, cost ratios).",
      "Name and describe the scenario (e.g., \"Optimistic Q3\").",
      "Save and compare scenario results against base case in Runs.",
    ],
    prerequisites: [
      { label: "Create a baseline", href: "/baselines" },
    ],
    relatedPages: [
      { label: "Baselines", href: "/baselines" },
      { label: "Drafts", href: "/drafts" },
      { label: "Runs", href: "/runs" },
      { label: "Entity Comparison", href: "/compare" },
    ],
  },

  "/changesets": {
    title: "Changesets",
    chapter: "13",
    overview:
      "Create immutable snapshots of targeted overrides, test them with dry-runs, and merge them into new baseline versions. Changesets provide a controlled way to make batch changes.",
    steps: [
      "Click \"New Changeset\" to start creating overrides.",
      "Select the target baseline and the fields to override.",
      "Define the new values for each override.",
      "Run a dry-run to preview the impact of the changes.",
      "If satisfied, merge the changeset to create a new baseline version.",
    ],
    prerequisites: [
      { label: "Create a baseline", href: "/baselines" },
    ],
    relatedPages: [
      { label: "Baselines", href: "/baselines" },
      { label: "Drafts", href: "/drafts" },
    ],
  },

  "/changesets/*": {
    title: "Changeset Detail",
    chapter: "13",
    overview:
      "View and manage a specific changeset's overrides. Run dry-runs to preview changes and merge when ready.",
    steps: [
      "Review the list of overrides in this changeset.",
      "Add or remove specific field overrides.",
      "Click \"Dry Run\" to preview the impact on the baseline.",
      "Review dry-run results for accuracy.",
      "Click \"Merge\" to apply changes and create a new baseline version.",
    ],
    prerequisites: [
      { label: "Create a changeset", href: "/changesets" },
    ],
    relatedPages: [
      { label: "Baselines", href: "/baselines" },
      { label: "Drafts", href: "/drafts" },
    ],
  },

  // ── ANALYZE ────────────────────────────────────

  "/runs": {
    title: "Runs",
    chapter: "14",
    overview:
      "Execute financial model runs against a draft. Each run produces financial statements, KPIs, Monte Carlo distributions, sensitivity analyses, and valuation outputs.",
    steps: [
      "View your run history in the list with status indicators.",
      "Click a run to view its detailed results.",
      "To create a new run, navigate to a Draft and click \"Execute Run\".",
      "Each run is immutable — results are preserved for audit and comparison.",
    ],
    prerequisites: [
      { label: "Create a baseline", href: "/baselines" },
      { label: "Create and commit a draft", href: "/drafts" },
    ],
    relatedPages: [
      { label: "Monte Carlo & Sensitivity", href: "/runs" },
      { label: "Valuation", href: "/runs" },
      { label: "Board Packs", href: "/board-packs" },
      { label: "Entity Comparison", href: "/compare" },
    ],
  },

  "/runs/*": {
    title: "Run Results",
    chapter: "14",
    overview:
      "Detailed results for a model run: financial statements, KPIs, and links to Monte Carlo, sensitivity, and valuation analyses.",
    steps: [
      "Review the financial statements (Income Statement, Balance Sheet, Cash Flow).",
      "Check KPI cards for key metrics.",
      "Navigate to Monte Carlo for probability distributions.",
      "Navigate to Sensitivity for tornado diagrams.",
      "Navigate to Valuation for DCF and multiples-based analysis.",
      "Export results or include them in a Board Pack.",
    ],
    prerequisites: [
      { label: "Execute a run from a draft", href: "/drafts" },
    ],
    relatedPages: [
      { label: "Monte Carlo", href: "/runs" },
      { label: "Sensitivity Analysis", href: "/runs" },
      { label: "Valuation", href: "/runs" },
      { label: "Board Packs", href: "/board-packs" },
    ],
  },

  "/runs/*/mc": {
    title: "Monte Carlo Simulation",
    chapter: "15",
    overview:
      "Interpret Monte Carlo fan charts and probability distributions. The simulation runs thousands of iterations with randomized assumptions to show the range of possible outcomes.",
    steps: [
      "Review the fan chart showing probability bands (P10, P25, P50, P75, P90).",
      "Examine the histogram of simulated outcomes.",
      "Check the summary statistics table for key percentiles.",
      "Adjust the number of iterations or distribution parameters if needed.",
      "Export charts for use in reports and presentations.",
    ],
    prerequisites: [
      { label: "Execute a run", href: "/runs" },
    ],
    relatedPages: [
      { label: "Sensitivity Analysis", href: "/runs" },
      { label: "Run Results", href: "/runs" },
    ],
  },

  "/runs/*/sensitivity": {
    title: "Sensitivity Analysis",
    chapter: "15",
    overview:
      "View tornado diagrams showing which assumptions have the greatest impact on your model's outputs. Understand which drivers matter most for decision-making.",
    steps: [
      "Review the tornado diagram ranking assumptions by impact.",
      "Click on any bar to see the detailed sensitivity range.",
      "Examine the sensitivity table for exact values.",
      "Use insights to focus attention on high-impact assumptions.",
    ],
    prerequisites: [
      { label: "Execute a run", href: "/runs" },
    ],
    relatedPages: [
      { label: "Monte Carlo Simulation", href: "/runs" },
      { label: "Run Results", href: "/runs" },
    ],
  },

  "/runs/*/valuation": {
    title: "Valuation",
    chapter: "16",
    overview:
      "DCF and multiples-based valuation outputs from model runs. View enterprise value, equity value, and implied share prices based on your financial projections.",
    steps: [
      "Review the DCF valuation summary with WACC and terminal value.",
      "Examine the multiples-based valuation (EV/EBITDA, P/E ratios).",
      "Compare implied values across different methodologies.",
      "Adjust discount rates or terminal growth assumptions to test sensitivity.",
    ],
    prerequisites: [
      { label: "Execute a run with valuation enabled", href: "/runs" },
    ],
    relatedPages: [
      { label: "Run Results", href: "/runs" },
      { label: "Monte Carlo", href: "/runs" },
    ],
  },

  "/budgets": {
    title: "Budgets",
    chapter: "17",
    overview:
      "Track budget performance with variance analysis and visual charts. Compare actuals to projections period by period to monitor financial performance.",
    steps: [
      "View your budget list and select a budget to analyze.",
      "Review variance charts comparing actuals vs. projections.",
      "Drill into specific periods or line items for detailed analysis.",
      "Export budget reports for stakeholder presentations.",
    ],
    prerequisites: [
      { label: "Create a baseline with budget data", href: "/baselines" },
    ],
    relatedPages: [
      { label: "Runs", href: "/runs" },
      { label: "Covenants", href: "/covenants" },
    ],
  },

  "/budgets/*": {
    title: "Budget Detail",
    chapter: "17",
    overview:
      "Detailed budget view with period-by-period variance analysis, trend charts, and drill-down into specific line items.",
    steps: [
      "Review the period comparison table (actual vs. budget vs. variance).",
      "Examine trend charts for visual patterns.",
      "Click on specific line items to see detailed breakdowns.",
      "Add notes or explanations for significant variances.",
    ],
    prerequisites: [
      { label: "Create a budget", href: "/budgets" },
    ],
    relatedPages: [
      { label: "Runs", href: "/runs" },
      { label: "Covenants", href: "/covenants" },
    ],
  },

  "/covenants": {
    title: "Covenants",
    chapter: "18",
    overview:
      "Monitor debt covenant compliance. Set thresholds and receive alerts when financial ratios approach or breach limits. Essential for managing lending relationships.",
    steps: [
      "View your covenant monitors with current status (green/amber/red).",
      "Click a covenant to see its detail page with historical tracking.",
      "Set up new covenant monitors with threshold values.",
      "Configure alert notifications for approaching breaches.",
    ],
    prerequisites: [
      { label: "Create baselines with financial data", href: "/baselines" },
      { label: "Execute runs to generate ratios", href: "/runs" },
    ],
    relatedPages: [
      { label: "Runs", href: "/runs" },
      { label: "Budgets", href: "/budgets" },
    ],
  },

  "/benchmark": {
    title: "Benchmarking & Competitor Analysis",
    chapter: "19",
    overview:
      "Compare your metrics against anonymized industry peers. Opt in to share data and view percentile rankings across key financial metrics.",
    steps: [
      "Select your industry segment and peer group.",
      "Opt in to share anonymized data for benchmarking.",
      "View percentile rankings for key metrics (margins, growth, ratios).",
      "Compare specific KPIs against the industry median and quartiles.",
      "Export benchmark reports for board presentations.",
    ],
    prerequisites: [
      { label: "Execute runs to generate metrics", href: "/runs" },
    ],
    relatedPages: [
      { label: "Entity Comparison", href: "/compare" },
      { label: "Runs", href: "/runs" },
    ],
  },

  "/compare": {
    title: "Entity Comparison",
    chapter: "20",
    overview:
      "Side-by-side comparison of entities or runs. Analyze KPI differences and variance drivers to understand relative performance.",
    steps: [
      "Select two or more entities or runs to compare.",
      "Review the side-by-side KPI comparison table.",
      "Examine variance highlights showing the biggest differences.",
      "Drill into specific metrics for detailed analysis.",
      "Export comparison reports.",
    ],
    prerequisites: [
      { label: "Execute multiple runs", href: "/runs" },
    ],
    relatedPages: [
      { label: "Runs", href: "/runs" },
      { label: "Benchmarking", href: "/benchmark" },
    ],
  },

  "/ventures": {
    title: "Ventures",
    chapter: "21",
    overview:
      "Guided questionnaire-to-model wizard. Answer questions about your business, and AI generates initial financial assumptions as a draft. Perfect for startups and new business lines.",
    steps: [
      "Click \"New Venture\" to start the wizard.",
      "Answer the guided questionnaire about your business model.",
      "Provide key metrics: pricing, customer counts, growth expectations.",
      "The AI generates initial financial assumptions and line items.",
      "Review the generated draft and adjust any assumptions.",
      "Commit the draft to create a baseline for analysis.",
    ],
    prerequisites: [],
    relatedPages: [
      { label: "Baselines", href: "/baselines" },
      { label: "Drafts", href: "/drafts" },
      { label: "Marketplace Templates", href: "/marketplace" },
    ],
    tips: [
      "The AI uses industry benchmarks to generate realistic starting assumptions.",
      "You can always refine the generated model in the draft editor.",
    ],
  },

  // ── COLLABORATE & REPORT ───────────────────────

  "/workflows": {
    title: "Workflows, Tasks & Inbox",
    chapter: "22",
    overview:
      "Configure approval workflows for baselines, drafts, and reports. Route items through review chains with role-based sign-off. Manage your task queue and inbox.",
    steps: [
      "View active workflows and their current status.",
      "Create new approval workflows with defined stages.",
      "Assign reviewers and approvers to each stage.",
      "Track items as they progress through the workflow.",
      "Use your Inbox to see pending review requests.",
    ],
    prerequisites: [
      { label: "Set up team members in Settings", href: "/settings/teams" },
    ],
    relatedPages: [
      { label: "Inbox", href: "/inbox" },
      { label: "Collaboration", href: "/activity" },
    ],
  },

  "/workflows/*": {
    title: "Workflow Detail",
    chapter: "22",
    overview:
      "View and manage a specific workflow's stages, assignees, and current progress. Approve, reject, or request changes at each stage.",
    steps: [
      "Review the workflow stages and current status.",
      "Take action on items assigned to you (Approve / Request Changes).",
      "Add comments or feedback at each stage.",
      "Track the workflow's progress from creation to completion.",
    ],
    prerequisites: [
      { label: "Create a workflow", href: "/workflows" },
    ],
    relatedPages: [
      { label: "Inbox", href: "/inbox" },
    ],
  },

  "/inbox": {
    title: "Inbox",
    chapter: "22",
    overview:
      "Your centralized task queue. View review requests, feedback items, and assigned tasks from across the platform. Take action on items without navigating to each page.",
    steps: [
      "Review pending items in your inbox.",
      "Click an item to view its details and take action.",
      "Filter by type (reviews, assignments, feedback).",
      "Mark items as read or archive completed ones.",
    ],
    prerequisites: [],
    relatedPages: [
      { label: "Workflows", href: "/workflows" },
      { label: "Notifications", href: "/notifications" },
    ],
  },

  "/inbox/*": {
    title: "Inbox Item Detail",
    chapter: "22",
    overview:
      "View the detail of an inbox item and take action — approve, reject, provide feedback, or navigate to the relevant page.",
    steps: [
      "Review the item details and context.",
      "Take the appropriate action (Approve, Reject, Comment).",
      "Navigate to the linked page for full context if needed.",
    ],
    prerequisites: [],
    relatedPages: [
      { label: "Inbox", href: "/inbox" },
      { label: "Workflows", href: "/workflows" },
    ],
  },

  "/board-packs": {
    title: "Board Packs",
    chapter: "23",
    overview:
      "Assemble presentation-ready packages for board meetings. Use the builder to select sections, charts, and narratives from your runs. Schedule recurring generation.",
    steps: [
      "Click \"Create Board Pack\" to start a new package.",
      "Select the source run to pull data from.",
      "Choose sections to include (Executive Summary, Income Statement, etc.).",
      "Arrange sections in the desired order.",
      "Preview and generate the board pack.",
      "Download as PDF or share with stakeholders.",
    ],
    prerequisites: [
      { label: "Execute a run with results", href: "/runs" },
    ],
    relatedPages: [
      { label: "Runs", href: "/runs" },
      { label: "Memos", href: "/memos" },
      { label: "Documents", href: "/documents" },
    ],
  },

  "/board-packs/*": {
    title: "Board Pack Detail",
    chapter: "23",
    overview:
      "View and edit a board pack's sections, configuration, and generated output. Navigate to the builder for section customization.",
    steps: [
      "Review the board pack's current sections and content.",
      "Click \"Edit Report Sections\" to open the builder.",
      "Download the generated output.",
      "Share with stakeholders or schedule recurring generation.",
    ],
    prerequisites: [
      { label: "Create a board pack", href: "/board-packs" },
    ],
    relatedPages: [
      { label: "Board Pack Builder", href: "/board-packs" },
      { label: "Documents", href: "/documents" },
    ],
  },

  "/board-packs/*/builder": {
    title: "Board Pack Builder",
    chapter: "23",
    overview:
      "Visual builder for customizing board pack sections. Add, remove, and reorder sections. Configure section content and formatting.",
    steps: [
      "Select sections from the \"Available Sections\" panel.",
      "Click \"Add\" to include a section in the report.",
      "Use the up/down arrows to reorder sections.",
      "Preview the assembled board pack.",
      "Save your configuration.",
    ],
    prerequisites: [
      { label: "Create a board pack", href: "/board-packs" },
    ],
    relatedPages: [
      { label: "Board Packs", href: "/board-packs" },
      { label: "Runs", href: "/runs" },
    ],
  },

  "/board-packs/schedules": {
    title: "Board Pack Schedules",
    chapter: "23",
    overview:
      "Set up recurring board pack generation on a schedule. Automatically generate and distribute board packs at defined intervals.",
    steps: [
      "Create a new schedule with frequency (weekly, monthly, quarterly).",
      "Select the board pack template to use.",
      "Configure distribution (email recipients, auto-upload).",
      "Review and activate the schedule.",
    ],
    prerequisites: [
      { label: "Create a board pack template", href: "/board-packs" },
    ],
    relatedPages: [
      { label: "Board Packs", href: "/board-packs" },
      { label: "Documents", href: "/documents" },
    ],
  },

  "/memos": {
    title: "Memos & Documents",
    chapter: "24",
    overview:
      "Create investment memos with structured narratives and supporting data from your runs. Access the document library for all generated outputs.",
    steps: [
      "Click \"New Memo\" to create an investment memo.",
      "Select the source run for supporting data.",
      "Structure the memo with sections (thesis, risks, financials).",
      "Add narrative text and supporting charts.",
      "Generate and download the final memo as PDF.",
    ],
    prerequisites: [
      { label: "Execute a run with results", href: "/runs" },
    ],
    relatedPages: [
      { label: "Documents", href: "/documents" },
      { label: "Board Packs", href: "/board-packs" },
      { label: "Runs", href: "/runs" },
    ],
  },

  "/documents": {
    title: "Document Library",
    chapter: "24",
    overview:
      "Central repository for all generated outputs — PDFs, spreadsheets, and exports. Search, filter, and download any document.",
    steps: [
      "Browse all documents with filtering by type and date.",
      "Click a document to preview or download.",
      "Use search to find specific documents.",
      "Organize documents with tags or categories.",
    ],
    prerequisites: [],
    relatedPages: [
      { label: "Board Packs", href: "/board-packs" },
      { label: "Memos", href: "/memos" },
      { label: "AFS Output", href: "/afs" },
    ],
  },

  "/activity": {
    title: "Collaboration & Activity",
    chapter: "25",
    overview:
      "View the platform-wide activity feed showing recent actions across your team. Track who made changes, when, and to which items.",
    steps: [
      "Review the chronological activity feed.",
      "Filter by user, action type, or entity.",
      "Click any activity item to navigate to the relevant page.",
    ],
    prerequisites: [],
    relatedPages: [
      { label: "Notifications", href: "/notifications" },
      { label: "Workflows", href: "/workflows" },
    ],
  },

  "/notifications": {
    title: "Notifications",
    chapter: "25",
    overview:
      "Manage your notification preferences and view all notifications. Configure which events trigger alerts and how you receive them.",
    steps: [
      "View all notifications (unread highlighted).",
      "Click a notification to navigate to the relevant item.",
      "Mark notifications as read or clear them.",
      "Configure notification preferences in Settings.",
    ],
    prerequisites: [],
    relatedPages: [
      { label: "Activity", href: "/activity" },
      { label: "Inbox", href: "/inbox" },
      { label: "Settings", href: "/settings" },
    ],
  },

  // ── ADMIN ──────────────────────────────────────

  "/settings": {
    title: "Settings & Administration",
    chapter: "26",
    overview:
      "Account and tenant configuration. Manage billing, integrations (Xero, QuickBooks), audit log, currency, SSO/SAML, GDPR compliance, and team membership.",
    steps: [
      "Navigate between settings sections using the tabs.",
      "Configure billing and subscription plans.",
      "Set up integrations with external accounting systems.",
      "Manage team members and roles.",
      "Configure SSO/SAML for enterprise authentication.",
      "Review the audit log for security monitoring.",
    ],
    prerequisites: [],
    relatedPages: [
      { label: "Teams", href: "/settings/teams" },
      { label: "Billing", href: "/settings/billing" },
      { label: "Audit Log", href: "/settings/audit" },
    ],
  },

  "/settings/teams": {
    title: "Team Management",
    chapter: "26",
    overview:
      "Manage team members — invite new users, assign roles, and configure permissions. Teams determine who can access and modify which areas of the platform.",
    steps: [
      "View current team members and their roles.",
      "Click \"Invite Member\" to add a new team member.",
      "Set roles: Owner, Admin, Analyst, Viewer.",
      "Remove or deactivate members as needed.",
    ],
    prerequisites: [],
    relatedPages: [
      { label: "Settings", href: "/settings" },
      { label: "Workflows", href: "/workflows" },
    ],
  },

  "/settings/billing": {
    title: "Billing",
    chapter: "26",
    overview: "Manage your subscription plan, view invoices, and update payment methods.",
    steps: [
      "Review your current plan and usage.",
      "Upgrade or downgrade your subscription.",
      "View past invoices and payment history.",
      "Update payment methods.",
    ],
    prerequisites: [],
    relatedPages: [
      { label: "Settings", href: "/settings" },
    ],
  },

  "/settings/audit": {
    title: "Audit Log",
    chapter: "26",
    overview: "Review a chronological log of all actions taken in your tenant for security and compliance monitoring.",
    steps: [
      "Browse the audit log entries sorted by date.",
      "Filter by user, action type, or date range.",
      "Export audit logs for compliance reporting.",
    ],
    prerequisites: [],
    relatedPages: [
      { label: "Settings", href: "/settings" },
    ],
  },

  "/settings/integrations": {
    title: "Integrations",
    chapter: "26",
    overview: "Connect external accounting systems like Xero and QuickBooks to sync financial data with Virtual Analyst.",
    steps: [
      "Select an integration to configure (Xero, QuickBooks, etc.).",
      "Follow the OAuth flow to authorize the connection.",
      "Map accounts and data fields between systems.",
      "Configure sync frequency and direction.",
    ],
    prerequisites: [],
    relatedPages: [
      { label: "Settings", href: "/settings" },
      { label: "Excel Connections", href: "/excel-connections" },
    ],
  },

  "/settings/sso": {
    title: "SSO / SAML Configuration",
    chapter: "26",
    overview: "Set up Single Sign-On with your organization's identity provider for enterprise authentication.",
    steps: [
      "Enter your IdP metadata URL or upload the metadata XML.",
      "Configure attribute mappings (email, name, role).",
      "Test the SSO connection.",
      "Enable SSO enforcement for your tenant.",
    ],
    prerequisites: [],
    relatedPages: [
      { label: "Settings", href: "/settings" },
      { label: "Teams", href: "/settings/teams" },
    ],
  },

  "/settings/currency": {
    title: "Currency Management",
    chapter: "26",
    overview: "Configure base currency and exchange rates for multi-currency financial modeling.",
    steps: [
      "Set your tenant's base (reporting) currency.",
      "Add additional currencies used in your models.",
      "Configure exchange rate sources (manual or API).",
      "View and update current exchange rates.",
    ],
    prerequisites: [],
    relatedPages: [
      { label: "Settings", href: "/settings" },
    ],
  },

  "/settings/compliance": {
    title: "GDPR Compliance",
    chapter: "26",
    overview: "Manage data protection and GDPR compliance settings including data retention policies and user data requests.",
    steps: [
      "Review current data retention policies.",
      "Configure data deletion schedules.",
      "Process data subject access requests (DSARs).",
      "Export compliance reports.",
    ],
    prerequisites: [],
    relatedPages: [
      { label: "Settings", href: "/settings" },
      { label: "Audit Log", href: "/settings/audit" },
    ],
  },
};
