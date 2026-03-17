/**
 * Shared mocks for page-level smoke tests.
 *
 * Every page follows the same pattern:
 *   1. getAuthContext() -> redirect to /login if null
 *   2. api.setAccessToken()
 *   3. api.<namespace>.list/get() -> populate state
 *   4. Render UI
 *
 * These mocks provide a minimal happy-path for all pages to render.
 */
import { vi } from "vitest";

// --- Next.js navigation ---
export const mockReplace = vi.fn();
export const mockPush = vi.fn();
export const mockRefresh = vi.fn();

// Stable object references prevent useEffect infinite re-trigger loops
// when effects depend on router/params/searchParams.
const stableRouter = { replace: mockReplace, push: mockPush, refresh: mockRefresh };
const stableParams = { id: "test-id-123" };
const stableSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => stableRouter,
  useParams: () => stableParams,
  usePathname: () => "/",
  useSearchParams: () => stableSearchParams,
}));

vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string; [k: string]: unknown }) => {
    return <a href={href} {...props}>{children}</a>;
  },
}));

vi.mock("next/image", () => ({
  __esModule: true,
  default: (props: Record<string, unknown>) => {
    return <img {...props} />;
  },
}));

// --- Auth ---
export const mockGetAuthContext = vi.fn();

vi.mock("@/lib/auth", () => ({
  getAuthContext: (...args: unknown[]) => mockGetAuthContext(...args),
  signOut: vi.fn(async () => {}),
}));

// Default: authenticated user
mockGetAuthContext.mockResolvedValue({
  tenantId: "tenant-test",
  userId: "user-test",
  accessToken: "mock-token",
  tenantIdIsFallback: false,
});

// --- API client ---
const emptyList = async () => ({ items: [], total: 0, limit: 50, offset: 0 });

export const mockApi = {
  setAccessToken: vi.fn(),
  baselines: {
    list: vi.fn(emptyList),
    get: vi.fn(async () => ({ model_config: {}, baseline_id: "b-1" })),
    listVersions: vi.fn(async () => ({ versions: [] })),
    getVersion: vi.fn(async () => ({ config: {} })),
  },
  runs: {
    list: vi.fn(async () => ({ items: [], total: 0, limit: 50, offset: 0 })),
    get: vi.fn(async () => ({
      run_id: "run-1",
      baseline_id: "b-1",
      status: "succeeded",
      created_at: "2026-01-01T00:00:00Z",
      statements: null,
      kpis: [],
      mc_summary: null,
    })),
    create: vi.fn(async () => ({ run_id: "new-run" })),
    getStatements: vi.fn(async () => null),
    getKpis: vi.fn(async () => []),
    getMc: vi.fn(async () => ({ num_simulations: 0, seed: 42, percentiles: {}, summary: {} })),
    getValuation: vi.fn(async () => ({ dcf: {}, multiples: {} })),
    getSensitivity: vi.fn(async () => ({ base_fcf: 0, pct: 0.1, drivers: [] })),
    postSensitivityHeatmap: vi.fn(async () => ({
      param_a: "a",
      param_b: "b",
      values_a: [],
      values_b: [],
      matrix: [],
      metric: "revenue",
    })),
  },
  budgets: {
    list: vi.fn(async () => ({ budgets: [], total: 0 })),
    get: vi.fn(async () => ({
      budget_id: "bud-1",
      label: "FY2026",
      fiscal_year: 2026,
      status: "draft",
      current_version_id: "v-1",
      period_type: "monthly",
      period_count: 12,
    })),
    listLineItems: vi.fn(async () => ({ line_items: [] })),
    getVariance: vi.fn(async () => ({ variances: [], materiality_pct: 10 })),
    getDashboard: vi.fn(async () => ({ widgets: [] })),
    reforecast: vi.fn(async () => ({})),
  },
  workflows: {
    listTemplates: vi.fn(async () => ({ templates: [] })),
    listInstances: vi.fn(async () => ({ instances: [] })),
    getTemplate: vi.fn(async () => ({
      template_id: "tmpl-1",
      name: "Test Template",
      description: null,
      stages: [],
      created_at: null,
    })),
    getInstance: vi.fn(async () => ({
      instance_id: "inst-1",
      template_id: "tmpl-1",
      entity_type: "baseline",
      entity_id: "b-1",
      current_stage_index: 0,
      status: "active",
      created_at: null,
      created_by: null,
      updated_at: null,
    })),
  },
  metrics: {
    getSummary: vi.fn(async () => ({
      total_baselines: 0,
      total_runs: 0,
      total_budgets: 0,
      total_scenarios: 0,
      latency_p50_ms: 42.5,
      latency_p95_ms: 120.3,
      request_count: 100,
      by_endpoint: {},
    })),
  },
  orgStructures: {
    list: vi.fn(async () => ({ items: [], total: 0 })),
    get: vi.fn(async () => ({
      org_id: "org-1",
      group_name: "Test",
      reporting_currency: "USD",
      status: "active",
      consolidation_method: "full",
      eliminate_intercompany: true,
      minority_interest_treatment: "proportional",
      created_at: null,
      entities: [],
      ownership: [],
      intercompany: [],
    })),
    update: vi.fn(async () => ({ org_id: "org-1", updated: [] })),
    validate: vi.fn(async () => ({ status: "valid", checks: [] })),
    hierarchy: vi.fn(async () => ({ org_id: "org-1", roots: [] })),
    runs: vi.fn(async () => ({ items: [] })),
    run: vi.fn(async () => ({ consolidated_run_id: "crun-1", status: "pending" })),
    getRun: vi.fn(async () => ({
      consolidated_run_id: "crun-1",
      status: "completed",
      result: null,
      created_at: null,
      completed_at: null,
      error_message: null,
    })),
  },
  notifications: {
    list: vi.fn(async () => ({ items: [], total: 0, unread_count: 0 })),
    markRead: vi.fn(async () => ({ ok: true })),
  },
  assignments: {
    list: vi.fn(async () => ({ assignments: [], total: 0 })),
    listPool: vi.fn(async () => ({ assignments: [], total: 0 })),
    get: vi.fn(async () => ({
      assignment_id: "asgn-1",
      workflow_instance_id: null as string | null,
      entity_type: "baseline",
      entity_id: "b-1",
      assignee_user_id: null as string | null,
      assigned_by_user_id: null as string | null,
      status: "open",
      deadline: null as string | null,
      instructions: null as string | null,
      created_at: null as string | null,
      updated_at: null as string | null,
    })),
    create: vi.fn(async () => ({
      assignment_id: "asgn-new",
      workflow_instance_id: null,
      entity_type: "baseline",
      entity_id: "b-1",
      assignee_user_id: null,
      assigned_by_user_id: null,
      status: "open",
      deadline: null,
      instructions: null,
      created_at: null,
      updated_at: null,
    })),
    claim: vi.fn(async () => ({
      assignment_id: "asgn-1",
      workflow_instance_id: null,
      entity_type: "baseline",
      entity_id: "b-1",
      assignee_user_id: "user-1",
      assigned_by_user_id: null,
      status: "in_progress",
      deadline: null,
      instructions: null,
      created_at: null,
      updated_at: null,
    })),
    submit: vi.fn(async () => ({
      assignment_id: "asgn-1",
      workflow_instance_id: null,
      entity_type: "baseline",
      entity_id: "b-1",
      assignee_user_id: "user-1",
      assigned_by_user_id: null,
      status: "submitted",
      deadline: null,
      instructions: null,
      created_at: null,
      updated_at: null,
    })),
    update: vi.fn(async () => ({
      assignment_id: "asgn-1",
      workflow_instance_id: null,
      entity_type: "baseline",
      entity_id: "b-1",
      assignee_user_id: null,
      assigned_by_user_id: null,
      status: "open",
      deadline: null,
      instructions: null,
      created_at: null,
      updated_at: null,
    })),
    submitReview: vi.fn(async () => ({
      review_id: "rev-1",
      assignment_id: "asgn-1",
      reviewer_user_id: "user-1",
      decision: "approved" as const,
      notes: null,
      corrections: [],
      created_at: null,
    })),
  },
  feedback: {
    list: vi.fn(async () => ({ items: [], total: 0, unread_count: 0 })),
    acknowledge: vi.fn(async () => ({ summary_id: "s-1", acknowledged: true })),
  },
  activity: {
    list: vi.fn(async () => ({ items: [], total: 0 })),
  },
  scenarios: {
    list: vi.fn(emptyList),
  },
  boardPacks: {
    list: vi.fn(emptyList),
    get: vi.fn(async () => ({
      pack_id: "pack-1",
      label: "Q1 Board Pack",
      run_id: "run-1",
      budget_id: null,
      section_order: [],
      status: "draft",
      branding_json: {},
      created_at: null,
      narrative_json: {},
      error_message: null,
    })),
    update: vi.fn(async () => ({
      pack_id: "pack-1",
      label: "Q1 Board Pack",
      run_id: "run-1",
      budget_id: null,
      section_order: [],
      status: "draft",
      branding_json: {},
      created_at: null,
    })),
    generate: vi.fn(async () => ({ pack_id: "pack-1", status: "generated", narrative_json: {} })),
  },
  boardPackSchedules: {
    list: vi.fn(async () => ({ items: [], total: 0, limit: 20, offset: 0 })),
    history: vi.fn(async () => ({ items: [], total: 0, limit: 20, offset: 0 })),
    create: vi.fn(async () => ({
      schedule_id: "sched-1",
      label: "Monthly",
      run_id: "run-1",
      cron_expr: "0 9 1 * *",
      distribution_emails: [],
    })),
    runNow: vi.fn(async () => ({ pack_id: "pack-1", history_id: "h-1", status: "running" })),
    delete: vi.fn(async () => undefined),
  },
  drafts: {
    list: vi.fn(async () => ({ items: [], total: 0, limit: 50, offset: 0 })),
    get: vi.fn(async () => ({
      draft_session_id: "draft-1",
      parent_baseline_id: "b-1",
      parent_baseline_version: null,
      status: "active",
      created_at: "2026-01-01T00:00:00Z",
      workspace: { assumptions: {}, distributions: [], correlation_matrix: [] },
    })),
    create: vi.fn(async () => ({ draft_session_id: "draft-new", status: "active", storage_path: "/tmp" })),
    patch: vi.fn(async () => ({ draft_session_id: "draft-1" })),
    chat: vi.fn(async () => ({ messages: [], proposals: [] })),
    acceptProposal: vi.fn(async () => ({ proposal_id: "p-1", status: "accepted" })),
    rejectProposal: vi.fn(async () => ({ proposal_id: "p-1", status: "rejected" })),
    commit: vi.fn(async () => ({ baseline_id: "b-1", baseline_version: "v-2" })),
  },
  versions: {
    list: vi.fn(async () => ({ versions: [] })),
    diff: vi.fn(async () => ({})),
  },
  comments: {
    list: vi.fn(async () => ({ items: [], comments: [], total: 0 })),
    create: vi.fn(async () => ({ comment_id: "c-1" })),
  },
  marketplace: {
    list: vi.fn(async () => ({ items: [], total: 0 })),
    useTemplate: vi.fn(async () => ({ baseline_id: "b-new" })),
  },
  memos: {
    list: vi.fn(async () => ({ items: [], total: 0 })),
    create: vi.fn(async () => ({ memo_id: "memo-1" })),
  },
  documents: {
    list: vi.fn(async () => ({ items: [], total: 0 })),
    upload: vi.fn(async () => ({ document_id: "doc-1" })),
  },
  covenants: {
    list: vi.fn(async () => ({ items: [], total: 0 })),
    metricRefs: vi.fn(async () => ({ metric_refs: [] })),
    create: vi.fn(async () => ({ covenant_id: "cov-1" })),
    delete: vi.fn(async () => ({ ok: true })),
  },
  benchmark: {
    getOptIn: vi.fn(async () => ({ opted_in: false })),
    getSummary: vi.fn(async () => ({ metrics: [] })),
    setOptIn: vi.fn(async () => ({ ok: true })),
    deleteOptIn: vi.fn(async () => ({ ok: true })),
  },
  pim: {
    universe: {
      list: vi.fn(async () => ({ items: [], total: 0, limit: 50, offset: 0 })),
      add: vi.fn(async () => ({ company_id: "co-1", company_name: "Test Co", ticker: "TEST" })),
      remove: vi.fn(async () => ({ deleted: true })),
      get: vi.fn(async () => ({ company_id: "co-1", company_name: "Test Co", ticker: "TEST" })),
    },
    sentiment: {
      dashboard: vi.fn(async (): Promise<{ items: unknown[]; total: number }> => ({ items: [], total: 0 })),
      companyDetail: vi.fn(async () => ({
        company: { company_id: "co-1", company_name: "Test Co", ticker: "TEST" },
        aggregates: [],
        recent_signals: [],
      })),
      scores: vi.fn(async () => ({ items: [], total: 0, limit: 50, offset: 0 })),
      aggregates: vi.fn(async () => ({ items: [] })),
    },
    pe: {
      list: vi.fn(async () => ({
        items: [] as {
          assessment_id: string; tenant_id: string; fund_name: string; vintage_year: number;
          currency: string; commitment_usd: number; cash_flows: unknown[];
          nav_usd: number | null; nav_date: string | null; paid_in_capital: number | null;
          distributed: number | null; dpi: number | null; tvpi: number | null;
          moic: number | null; irr: number | null; irr_computed_at: string | null;
          j_curve_json: unknown[] | null; notes: string | null;
          created_at: string | null; updated_at: string | null;
        }[],
        total: 0, limit: 20, offset: 0,
      })),
      get: vi.fn(async () => ({
        assessment_id: "a-1",
        tenant_id: "t-1",
        fund_name: "Test Fund",
        vintage_year: 2020,
        currency: "USD",
        commitment_usd: 1_000_000,
        cash_flows: [],
        nav_usd: null,
        nav_date: null,
        paid_in_capital: null,
        distributed: null,
        dpi: null,
        tvpi: null,
        moic: null,
        irr: null,
        irr_computed_at: null,
        j_curve_json: [],
        notes: null,
        created_at: null,
        updated_at: null,
      })),
      create: vi.fn(async () => ({ assessment_id: "a-new" })),
      update: vi.fn(async () => ({ assessment_id: "a-1" })),
      delete: vi.fn(async () => ({ deleted: true })),
      compute: vi.fn(async () => ({
        assessment_id: "a-1",
        paid_in_capital: 1_000_000,
        distributed: 500_000,
        dpi: 0.5,
        tvpi: 1.0,
        moic: 1.0,
        irr: 0.1,
        irr_converged: true,
        j_curve: [],
        limitations: "",
      })),
      memo: vi.fn(async () => ({
        assessment_id: "a-1",
        fund_name: "Test Fund",
        title: "Test Memo",
        executive_summary: "Summary",
        performance_analysis: "Analysis",
        risk_factors: "Risks",
        recommendation: "Hold",
        disclaimer: "Disclaimer",
        model_used: "claude-sonnet",
      })),
      summary: vi.fn(async () => ({
        total_assessments: 0,
        assessments_with_irr: 0,
        avg_dpi: null,
        avg_tvpi: null,
        avg_irr: null,
      })),
    },
    peer: {
      createBenchmark: vi.fn(async () => ({ benchmark_id: "b-1" })),
      listBenchmarks: vi.fn(async () => ({ items: [], total: 0, limit: 20, offset: 0 })),
      deleteBenchmark: vi.fn(async () => ({ deleted: true })),
      rankAssessment: vi.fn(async () => ({
        assessment_id: "a-1",
        vintage_year: 2020,
        strategy: "buyout",
        geography: "global",
        benchmark_id: null,
        fund_count: null,
        data_source: null,
        rankings: [],
        warning: "No benchmark data available.",
      })),
    },
    economic: {
      current: vi.fn(async () => ({
        snapshot_id: "snap-1",
        tenant_id: "t-1",
        regime: "expansion",
        gdp_growth: 0.025,
        inflation: 0.032,
        unemployment: 0.038,
        yield_10y: 0.042,
        vix: 18.5,
        captured_at: "2026-01-01T00:00:00Z",
      } as {
        snapshot_id: string; tenant_id: string; regime: string;
        gdp_growth: number; inflation: number; unemployment: number;
        yield_10y: number; vix: number; captured_at: string;
      } | null)),
      snapshots: vi.fn(async () => ({ snapshots: [] })),
    },
    cis: {
      compute: vi.fn(async () => ({ companies: [] })),
      factorAttribution: vi.fn(async () => ({
        narrative: "CIS driven by sentiment.",
        top_driver: "sentiment",
        risk_note: "Low momentum.",
      })),
    },
    portfolio: {
      build: vi.fn(async () => ({
        run_id: "run-1",
        tenant_id: "t-1",
        strategy_label: "test-strategy",
        built_at: "2026-01-01T00:00:00Z",
        holdings: [],
        constraints: {},
        narrative: null,
      })),
      runs: vi.fn(async () => ({ runs: [], total: 0 })),
      get: vi.fn(async () => ({
        run_id: "run-1",
        tenant_id: "t-1",
        strategy_label: "test-strategy",
        built_at: "2026-01-01T00:00:00Z",
        holdings: [],
        constraints: {},
        narrative: null,
      })),
      delete: vi.fn(async () => ({ deleted: true })),
    },
    backtest: {
      run: vi.fn(async () => ({ backtest_id: "bt-1" })),
      results: vi.fn(async () => ({ items: [], total: 0, limit: 20, offset: 0 })),
      get: vi.fn(async () => ({
        backtest_id: "bt-1",
        tenant_id: "t-1",
        strategy_label: "momentum",
        status: "completed",
        config: { strategy_label: "momentum", lookback_periods: 12, rebalance_freq: "monthly", universe_ids: [] },
        ic_mean: 0.08,
        ic_std: 0.05,
        icir: 1.6,
        cumulative_return: 0.42,
        sharpe_ratio: 1.2,
        max_drawdown: -0.15,
        periods: [],
        created_at: "2026-01-01T00:00:00Z",
        completed_at: "2026-01-01T00:01:00Z",
      })),
      commentary: vi.fn(async () => ({
        backtest_id: "bt-1",
        narrative: "Strong momentum signal.",
        key_driver: "momentum",
        risk_note: "High drawdown periods.",
        model_used: "claude-sonnet",
      })),
      addCost: vi.fn(async () => ({ cost_id: "c-1" })),
      listCosts: vi.fn(async () => ({ items: [], total: 0 })),
      summary: vi.fn(async () => ({
        items: [] as {
          strategy_label: string; run_count: number; latest_run_at: string | null;
          avg_cumulative_return: number | null; avg_annualised_return: number | null;
          avg_sharpe_ratio: number | null; avg_max_drawdown: number | null;
          avg_ic_mean: number | null; avg_ic_std: number | null; avg_icir: number | null;
          best_cumulative_return: number | null; worst_cumulative_return: number | null;
        }[],
        total: 0,
        note: "",
      })),
    },
    markov: {
      states: vi.fn(async () => ({ items: [] })),
      steadyState: vi.fn(async () => ({
        top_states: [] as { state_index: number; label: string; probability: number }[],
        is_ergodic: true,
        quantecon_available: true,
        n_observations: 0,
        matrix_id: "m-1",
        limitations: "Test mode.",
        ci_lower: null as number[] | null,
        ci_upper: null as number[] | null,
      })),
      topTransitions: vi.fn(async () => ({
        edges: [] as { from_state: number; from_label: string; to_state: number; to_label: string; probability: number }[],
        top_state_indices: [] as number[],
        limitations: "Test mode.",
      })),
    },
  },
  ventures: {
    templates: vi.fn(async () => []),
    create: vi.fn(async () => ({ venture_id: "v-1", question_plan: [] })),
    submitAnswers: vi.fn(async () => ({ ok: true })),
    generateDraft: vi.fn(async () => ({ draft_session_id: "draft-v1" })),
    list: vi.fn(async () => ({ items: [], total: 0 })),
    get: vi.fn(async () => ({ venture_id: "v-1", entity_name: "", template_id: "", answers: {} })),
  },
  changesets: {
    list: vi.fn(async () => ({ items: [], total: 0 })),
    create: vi.fn(async () => ({ changeset_id: "cs-1" })),
  },
  excelIngestion: {
    upload: vi.fn(async () => ({
      ingestion_id: "ing-1",
      status: "parsed",
      classification: { sheets: [], model_summary: {} },
    })),
    get: vi.fn(async () => ({
      classification: { sheets: [] },
      mapping: {},
      unmapped_items: [],
      questions: [],
    })),
    analyze: vi.fn(async () => ({ mapping: {}, questions: [] })),
    answer: vi.fn(async () => ({ mapping: {}, questions: [] })),
    createDraft: vi.fn(async () => ({ draft_session_id: "draft-1" })),
    list: vi.fn(async () => ({ items: [], total: 0 })),
    delete: vi.fn(async () => ({ ok: true })),
    getUploadStreamUrl: vi.fn(() => "http://localhost:8000/api/v1/excel-ingestion/upload-stream"),
    getAnswerStreamUrl: vi.fn(() => "http://localhost:8000/api/v1/excel-ingestion/test-id/answer-stream"),
  },
};

vi.mock("@/lib/api", () => ({
  api: mockApi,
  API_URL: "http://localhost:8000",
  getAccessToken: vi.fn(() => "mock-token"),
}));
