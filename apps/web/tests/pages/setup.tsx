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
    get: vi.fn(async () => ({ org_id: "org-1", group_name: "Test", entities: [] })),
  },
  notifications: {
    list: vi.fn(async () => ({ items: [], total: 0, unread_count: 0 })),
    markRead: vi.fn(async () => ({ ok: true })),
  },
  assignments: {
    list: vi.fn(async () => ({ assignments: [], total: 0 })),
  },
  activity: {
    list: vi.fn(async () => ({ items: [], total: 0 })),
  },
  scenarios: {
    list: vi.fn(emptyList),
  },
  boardPacks: {
    list: vi.fn(emptyList),
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
  },
  ventures: {
    templates: vi.fn(async () => []),
    create: vi.fn(async () => ({ venture_id: "v-1", question_plan: [] })),
    submitAnswers: vi.fn(async () => ({ ok: true })),
    generateDraft: vi.fn(async () => ({ draft_session_id: "draft-v1" })),
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
