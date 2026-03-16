/**
 * API client for Virtual Analyst backend.
 * Uses NEXT_PUBLIC_API_URL and X-Tenant-ID from caller.
 * When setAccessToken() is set, requests include Authorization: Bearer for API auth (C1).
 */

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Module-level access token. ONLY safe in client-side ("use client") contexts. R6-09.
 * Do NOT import api.ts from server components or getServerSideProps — the token
 * would persist across requests in the Node.js process.
 */
let _accessToken: string | null = null;

/** Set the Supabase access token so all API requests send Authorization: Bearer (C1). Clear with setAccessToken(null) on logout. */
export function setAccessToken(token: string | null): void {
  _accessToken = token;
}

/** Read the current access token (needed for direct fetch calls like Excel export). */
export function getAccessToken(): string | null {
  return _accessToken;
}

export interface ApiOptions {
  tenantId: string;
  userId?: string;
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public statusCode: number,
    public body: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  { tenantId, userId, method = "GET", body }: ApiOptions
): Promise<T> {
  const headers: Record<string, string> = {
    "X-Tenant-ID": tenantId,
    "Content-Type": "application/json",
    ...(userId && { "X-User-ID": userId }),
    ...(_accessToken && { Authorization: `Bearer ${_accessToken}` }),
  };
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      ...(body !== undefined && { body: JSON.stringify(body) }),
    });
  } catch (err) {
    // Network-level failures: Safari reports "Load failed", Chrome "Failed to fetch".
    // Replace with a user-friendly message so pages don't show cryptic browser errors.
    throw new ApiError(
      "Unable to connect to the server. Please check your connection and try again.",
      0,
      { originalError: err instanceof Error ? err.message : String(err) }
    );
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({ detail: res.statusText }));
  if (!res.ok) {
    throw new ApiError(
      typeof data.detail === "string" ? data.detail : JSON.stringify(data),
      res.status,
      data
    );
  }
  return data as T;
}

/** POST with FormData (e.g. file upload). Do not set Content-Type so browser sets multipart boundary. */
async function requestForm<T>(
  path: string,
  { tenantId, userId, body }: { tenantId: string; userId?: string; body: FormData }
): Promise<T> {
  const headers: Record<string, string> = {
    "X-Tenant-ID": tenantId,
    ...(userId && { "X-User-ID": userId }),
    ...(_accessToken && { Authorization: `Bearer ${_accessToken}` }),
  };
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers,
      body,
    });
  } catch (err) {
    throw new ApiError(
      "Unable to connect to the server. Please check your connection and try again.",
      0,
      { originalError: err instanceof Error ? err.message : String(err) }
    );
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({ detail: res.statusText }));
  if (!res.ok) {
    throw new ApiError(
      typeof data.detail === "string" ? data.detail : JSON.stringify(data),
      res.status,
      data
    );
  }
  return data as T;
}

export interface BaselineSummary {
  baseline_id: string;
  baseline_version: string;
  status: string;
  is_active: boolean;
  created_at: string | null;
}

export interface ModelConfigMetadata {
  entity_name: string;
  horizon_months: number;
  tax_rate?: number;
  currency?: string;
  [key: string]: unknown;
}

export interface ModelConfig {
  metadata: ModelConfigMetadata;
  blueprints?: Record<string, unknown>[];
  scenarios?: Record<string, unknown>[];
  distributions?: Record<string, unknown>[];
  nol_carry_forward?: boolean;
  [key: string]: unknown;
}

export interface BaselineDetail extends BaselineSummary {
  model_config: ModelConfig;
  [key: string]: unknown;
}

export interface BaselineVersion {
  model_config: ModelConfig;
  baseline_version: string;
  is_active: boolean;
  created_at: string | null;
}

export interface BaselinesResponse {
  items: BaselineSummary[];
  limit: number;
  offset: number;
}

export interface RunSummary {
  run_id: string;
  baseline_id: string;
  baseline_version: string;
  scenario_id: string | null;
  status: string;
  covenant_breached: boolean;
  created_at: string | null;
}

export interface RunsResponse {
  items: RunSummary[];
  limit: number;
  offset: number;
}

export interface RunDetail extends RunSummary {
  task_id?: string | null;
  mc_enabled?: boolean;
  num_simulations?: number | null;
  seed?: number | null;
  mc_progress?: number | null;
}

/** A single period row from the three-statement engine. */
export interface StatementRow {
  period_index: number;
  [key: string]: string | number;
}

export interface StatementsData {
  income_statement?: StatementRow[];
  balance_sheet?: StatementRow[];
  cash_flow?: StatementRow[];
  periods?: string[];
  revenue_by_segment?: Record<string, number[]>;
}

export interface KpiItem {
  period?: number;
  [key: string]: string | number | undefined;
}

export interface DraftSummary {
  draft_session_id: string;
  parent_baseline_id: string | null;
  parent_baseline_version: string | null;
  status: string;
  created_at: string | null;
}

export interface DraftsResponse {
  items: DraftSummary[];
  limit: number;
  offset: number;
}

export interface DraftWorkspace {
  draft_session_id?: string;
  template_id?: string | null;
  parent_baseline_id?: string | null;
  parent_baseline_version?: string | null;
  assumptions?: Record<string, unknown>;
  driver_blueprint?: Record<string, unknown>;
  distributions?: unknown[];
  scenarios?: unknown[];
  evidence?: unknown[];
  chat_history?: { role: string; content: string }[];
  pending_proposals?: PendingProposal[];
  [key: string]: unknown;
}

export interface PendingProposal {
  id: string;
  path: string;
  value: number | string | boolean | null;
  evidence?: string;
  confidence?: string;
  reasoning?: string;
}

export interface DraftDetail {
  draft_session_id: string;
  parent_baseline_id: string | null;
  parent_baseline_version: string | null;
  status: string;
  created_at: string | null;
  workspace: DraftWorkspace;
}

export interface ChatResponse {
  proposals?: PendingProposal[];
  clarification?: string | null;
  commentary?: string | null;
}

export interface IntegrityCheck {
  check: string;
  status: "pass" | "fail" | "warning";
  message?: string;
}

export interface CommitResult {
  baseline_id: string;
  baseline_version: string;
  integrity?: { status: string; checks: IntegrityCheck[] };
}

export interface BudgetSummary {
  budget_id: string;
  label: string;
  fiscal_year: string;
  status: string;
  created_at?: string | null;
}

export interface BudgetDetail extends BudgetSummary {
  current_version_id: string | null;
  workflow_instance_id?: string | null;
  updated_at?: string | null;
  created_by?: string | null;
}

export interface BudgetVarianceItem {
  account_ref: string;
  period_ordinal: number;
  budget_amount: number;
  actual_amount: number;
  variance_absolute: number;
  variance_percent: number;
  favourable: boolean;
  material: boolean;
}

export interface BudgetDashboardWidget {
  budget_id: string;
  label: string;
  burn_rate: number | null;
  runway_months: number | null;
  utilisation_pct: number | null;
  variance_trend: { period_ordinal: number; budget_total: number; actual_total: number; variance_pct: number }[];
  department_ranking: { department_ref: string; actual_total: number }[];
  alerts: { type: string; message: string; threshold_pct?: number; period_ordinal?: number }[];
}

export interface BudgetDashboardResponse {
  widgets: BudgetDashboardWidget[];
  cfo_view: boolean;
}

export interface BoardPackSummary {
  pack_id: string;
  label: string;
  run_id: string | null;
  budget_id: string | null;
  section_order: string[];
  status: string;
  branding_json: Record<string, unknown>;
  created_at: string | null;
}

export interface BoardPackDetail extends BoardPackSummary {
  narrative_json: Record<string, unknown>;
  error_message: string | null;
}

export interface NotificationItem {
  id: string;
  tenant_id: string;
  user_id: string | null;
  type: string;
  title: string;
  body: string | null;
  entity_type: string | null;
  entity_id: string | null;
  read_at: string | null;
  created_at: string | null;
}

export interface NotificationsResponse {
  items: NotificationItem[];
  unread_count: number;
  limit: number;
  offset: number;
}

export const api = {
  setAccessToken,
  baselines: {
    list: (tenantId: string, opts?: { limit?: number; offset?: number }) =>
      request<BaselinesResponse>(
        `/api/v1/baselines?${new URLSearchParams({
          ...(opts?.limit != null && { limit: String(opts.limit) }),
          ...(opts?.offset != null && { offset: String(opts.offset) }),
        }).toString()}`,
        { tenantId }
      ),
    get: (tenantId: string, baselineId: string) =>
      request<BaselineDetail>(
        `/api/v1/baselines/${encodeURIComponent(baselineId)}`,
        { tenantId }
      ),
    create: (tenantId: string, modelConfig: object) =>
      request<{ baseline_id: string; baseline_version: string; status: string }>(
        "/api/v1/baselines",
        { tenantId, method: "POST", body: { model_config: modelConfig } }
      ),
    listVersions: (tenantId: string, baselineId: string) =>
      request<{ items: { baseline_id: string; baseline_version: string; status: string; is_active: boolean; created_at: string | null }[]; total: number }>(
        `/api/v1/baselines/${encodeURIComponent(baselineId)}/versions`,
        { tenantId }
      ),
    getVersion: (tenantId: string, baselineId: string, version: string) =>
      request<BaselineVersion>(
        `/api/v1/baselines/${encodeURIComponent(baselineId)}/versions/${encodeURIComponent(version)}`,
        { tenantId }
      ),
  },
  runs: {
    list: (tenantId: string, opts?: { limit?: number; offset?: number; status?: string; baseline_id?: string }) =>
      request<RunsResponse>(
        `/api/v1/runs?${new URLSearchParams({
          ...(opts?.status && { status: opts.status }),
          ...(opts?.baseline_id && { baseline_id: opts.baseline_id }),
          ...(opts?.limit != null && { limit: String(opts.limit) }),
          ...(opts?.offset != null && { offset: String(opts.offset) }),
        }).toString()}`,
        { tenantId }
      ),
    get: (tenantId: string, runId: string) =>
      request<RunDetail>(`/api/v1/runs/${encodeURIComponent(runId)}`, {
        tenantId,
      }),
    create: (
      tenantId: string,
      baselineId: string,
      opts?: { scenarioId?: string; mcEnabled?: boolean; numSimulations?: number; seed?: number; valuationConfig?: { wacc?: number; terminal_growth_rate?: number; comparables?: string[] } }
    ) =>
      request<{ run_id: string; status: string; task_id?: string } & Record<string, unknown>>("/api/v1/runs", {
        tenantId,
        method: "POST",
        body: {
          baseline_id: baselineId,
          ...(opts?.scenarioId && { scenario_id: opts.scenarioId }),
          ...(opts?.mcEnabled && { mode: "monte_carlo", num_simulations: opts.numSimulations ?? 1000, seed: opts.seed ?? 42 }),
          ...(opts?.valuationConfig && { valuation_config: opts.valuationConfig }),
        },
      }),
    getMc: (tenantId: string, runId: string) =>
      request<{ num_simulations: number; seed: number; percentiles: Record<string, Record<string, number[]>>; summary: Record<string, unknown> }>(
        `/api/v1/runs/${encodeURIComponent(runId)}/mc`,
        { tenantId }
      ),
    getValuation: (tenantId: string, runId: string) =>
      request<{ dcf?: Record<string, unknown>; multiples?: Record<string, unknown> }>(
        `/api/v1/runs/${encodeURIComponent(runId)}/valuation`,
        { tenantId }
      ),
    getSensitivity: (tenantId: string, runId: string, pct?: number) =>
      request<
        { base_fcf: number; pct: number; drivers: { ref: string; impact_low: number; impact_high: number }[] } & Record<string, unknown>
      >(`/api/v1/runs/${encodeURIComponent(runId)}/sensitivity?pct=${pct ?? 0.1}`, { tenantId }),
    postSensitivitySweep: (
      tenantId: string,
      runId: string,
      body: { parameter_path: string; low: number; high: number; steps: number; metric: string },
    ) =>
      request<{ parameter: string; base_value: number; values: number[]; metric_values: number[]; metric: string }>(
        `/api/v1/runs/${encodeURIComponent(runId)}/sensitivity/sweep`,
        { tenantId, method: "POST", body },
      ),
    postSensitivityHeatmap: (
      tenantId: string,
      runId: string,
      body: {
        param_a_path: string;
        param_a_range: [number, number, number];
        param_b_path: string;
        param_b_range: [number, number, number];
        metric: string;
      },
    ) =>
      request<{ param_a: string; param_b: string; values_a: number[]; values_b: number[]; matrix: number[][]; metric: string }>(
        `/api/v1/runs/${encodeURIComponent(runId)}/sensitivity/heatmap`,
        { tenantId, method: "POST", body },
      ),
    getStatements: (tenantId: string, runId: string) =>
      request<StatementsData>(
        `/api/v1/runs/${encodeURIComponent(runId)}/statements`,
        { tenantId }
      ),
    getKpis: (tenantId: string, runId: string) =>
      request<KpiItem[]>(
        `/api/v1/runs/${encodeURIComponent(runId)}/kpis`,
        { tenantId }
      ),
  },
  drafts: {
    list: (tenantId: string, opts?: { status?: string; parent_baseline_id?: string; limit?: number; offset?: number }) =>
      request<DraftsResponse>(
        `/api/v1/drafts?${new URLSearchParams({
          ...(opts?.status && { status: opts.status }),
          ...(opts?.parent_baseline_id && { parent_baseline_id: opts.parent_baseline_id }),
          ...(opts?.limit != null && { limit: String(opts.limit) }),
          ...(opts?.offset != null && { offset: String(opts.offset) }),
        }).toString()}`,
        { tenantId }
      ),
    get: (tenantId: string, draftSessionId: string) =>
      request<DraftDetail>(
        `/api/v1/drafts/${encodeURIComponent(draftSessionId)}`,
        { tenantId }
      ),
    create: (tenantId: string, body?: { template_id?: string; parent_baseline_id?: string; parent_baseline_version?: string }) =>
      request<{ draft_session_id: string; status: string; storage_path: string }>(
        "/api/v1/drafts",
        { tenantId, method: "POST", body: body ?? {} }
      ),
    patch: (tenantId: string, draftSessionId: string, body: { status?: string; workspace?: Record<string, unknown> }) =>
      request<{ draft_session_id: string; status?: string }>(
        `/api/v1/drafts/${encodeURIComponent(draftSessionId)}`,
        { tenantId, method: "PATCH", body }
      ),
    chat: (tenantId: string, draftSessionId: string, message: string) =>
      request<ChatResponse>(
        `/api/v1/drafts/${encodeURIComponent(draftSessionId)}/chat`,
        { tenantId, method: "POST", body: { message } }
      ),
    acceptProposal: (tenantId: string, draftSessionId: string, proposalId: string) =>
      request<{ proposal_id: string; status: string }>(
        `/api/v1/drafts/${encodeURIComponent(draftSessionId)}/proposals/${encodeURIComponent(proposalId)}/accept`,
        { tenantId, method: "POST" }
      ),
    rejectProposal: (tenantId: string, draftSessionId: string, proposalId: string) =>
      request<{ proposal_id: string; status: string }>(
        `/api/v1/drafts/${encodeURIComponent(draftSessionId)}/proposals/${encodeURIComponent(proposalId)}/reject`,
        { tenantId, method: "POST" }
      ),
    commit: (tenantId: string, draftSessionId: string, acknowledgeWarnings?: boolean) =>
      request<CommitResult>(
        `/api/v1/drafts/${encodeURIComponent(draftSessionId)}/commit`,
        { tenantId, method: "POST", body: { acknowledge_warnings: !!acknowledgeWarnings } }
      ),
    delete: (tenantId: string, draftSessionId: string) =>
      request<{ draft_session_id: string; status: string }>(
        `/api/v1/drafts/${encodeURIComponent(draftSessionId)}`,
        { tenantId, method: "DELETE" }
      ),
  },
  notifications: {
    list: (
      tenantId: string,
      userId: string | undefined,
      unreadOnly?: boolean,
      limit?: number,
      offset?: number
    ) =>
      request<NotificationsResponse>(
        `/api/v1/notifications?${new URLSearchParams({
          ...(unreadOnly && { unread_only: "true" }),
          ...(limit != null && { limit: String(limit) }),
          ...(offset != null && { offset: String(offset) }),
        }).toString()}`,
        { tenantId, userId }
      ),
    markRead: (tenantId: string, userId: string, notificationId: string) =>
      request<{ id: string; read_at: string | null }>(
        `/api/v1/notifications/${encodeURIComponent(notificationId)}`,
        { tenantId, userId, method: "PATCH" }
      ),
  },
  scenarios: {
    list: (tenantId: string, opts?: { baseline_id?: string; limit?: number; offset?: number }) =>
      request<{ items: ScenarioItem[]; limit: number; offset: number }>(
        `/api/v1/scenarios?${new URLSearchParams({
          ...(opts?.baseline_id && { baseline_id: opts.baseline_id }),
          ...(opts?.limit != null && { limit: String(opts.limit) }),
          ...(opts?.offset != null && { offset: String(opts.offset) }),
        }).toString()}`,
        { tenantId }
      ),
    get: (tenantId: string, scenarioId: string) =>
      request<ScenarioItem>(`/api/v1/scenarios/${encodeURIComponent(scenarioId)}`, { tenantId }),
    create: (tenantId: string, body: { baseline_id: string; label: string; overrides?: { ref: string; field: string; value: number }[]; description?: string }) =>
      request<ScenarioItem>("/api/v1/scenarios", { tenantId, method: "POST", body }),
    delete: (tenantId: string, scenarioId: string) =>
      request<unknown>(`/api/v1/scenarios/${encodeURIComponent(scenarioId)}`, { tenantId, method: "DELETE" }),
    compare: (tenantId: string, body: { baseline_id: string; scenario_ids: string[] }) =>
      request<{ baseline_id: string; baseline_version: string; scenarios: Record<string, unknown>[] }>(
        "/api/v1/scenarios/compare",
        { tenantId, method: "POST", body }
      ),
  },
  teams: {
    list: (tenantId: string, limit?: number, offset?: number) =>
      request<TeamsListResponse>(
        `/api/v1/teams?${new URLSearchParams({
          ...(limit != null && { limit: String(limit) }),
          ...(offset != null && { offset: String(offset) }),
        }).toString()}`,
        { tenantId }
      ),
    create: (
      tenantId: string,
      userId: string,
      body: { name: string; description?: string | null }
    ) =>
      request<{ team_id: string; name: string; description: string | null }>(
        "/api/v1/teams",
        {
          tenantId,
          userId,
          method: "POST",
          body: { name: body.name, description: body.description ?? null },
        }
      ),
    get: (tenantId: string, teamId: string) =>
      request<TeamDetail>(`/api/v1/teams/${encodeURIComponent(teamId)}`, {
        tenantId,
      }),
    update: (
      tenantId: string,
      teamId: string,
      body: { name?: string; description?: string | null }
    ) =>
      request<TeamDetail>(
        `/api/v1/teams/${encodeURIComponent(teamId)}`,
        { tenantId, method: "PATCH", body }
      ),
    delete: (tenantId: string, teamId: string) =>
      request<void>(
        `/api/v1/teams/${encodeURIComponent(teamId)}`,
        { tenantId, method: "DELETE" }
      ),
    listJobFunctions: (tenantId: string) =>
      request<JobFunctionsResponse>("/api/v1/teams/job-functions/list", {
        tenantId,
      }),
    listMembers: (tenantId: string, teamId: string, limit?: number, offset?: number) =>
      request<MembersResponse>(
        `/api/v1/teams/${encodeURIComponent(teamId)}/members?${new URLSearchParams({
          ...(limit != null && { limit: String(limit) }),
          ...(offset != null && { offset: String(offset) }),
        }).toString()}`,
        { tenantId }
      ),
    addMember: (
      tenantId: string,
      teamId: string,
      body: { user_id: string; job_function_id: string; reports_to?: string | null }
    ) =>
      request<TeamMember>(
        `/api/v1/teams/${encodeURIComponent(teamId)}/members`,
        { tenantId, method: "POST", body }
      ),
    updateMember: (
      tenantId: string,
      teamId: string,
      userId: string,
      body: { job_function_id?: string; reports_to?: string | null }
    ) =>
      request<TeamMember>(
        `/api/v1/teams/${encodeURIComponent(teamId)}/members/${encodeURIComponent(userId)}`,
        { tenantId, method: "PATCH", body }
      ),
    removeMember: (tenantId: string, teamId: string, userId: string) =>
      request<void>(
        `/api/v1/teams/${encodeURIComponent(teamId)}/members/${encodeURIComponent(userId)}`,
        { tenantId, method: "DELETE" }
      ),
  },
  workflows: {
    listTemplates: (tenantId: string, limit?: number, offset?: number) =>
      request<WorkflowTemplatesResponse>(
        `/api/v1/workflows/templates?${new URLSearchParams({
          ...(limit != null && { limit: String(limit) }),
          ...(offset != null && { offset: String(offset) }),
        }).toString()}`,
        { tenantId }
      ),
    getTemplate: (tenantId: string, templateId: string) =>
      request<WorkflowTemplate>(
        `/api/v1/workflows/templates/${encodeURIComponent(templateId)}`,
        { tenantId }
      ),
    createInstance: (
      tenantId: string,
      body: { template_id: string; entity_type: string; entity_id: string }
    ) =>
      request<WorkflowInstance>("/api/v1/workflows/instances", {
        tenantId,
        method: "POST",
        body,
      }),
    getInstance: (tenantId: string, instanceId: string) =>
      request<WorkflowInstance>(
        `/api/v1/workflows/instances/${encodeURIComponent(instanceId)}`,
        { tenantId }
      ),
    listInstances: (
      tenantId: string,
      opts?: { entity_type?: string; entity_id?: string; status?: string; limit?: number; offset?: number }
    ) =>
      request<WorkflowInstancesResponse>(
        `/api/v1/workflows/instances?${new URLSearchParams(
          opts
            ? Object.fromEntries(
                Object.entries(opts).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)])
              )
            : {}
        ).toString()}`,
        { tenantId }
      ),
    seedTemplates: (tenantId: string) =>
      request<{ seeded: number }>("/api/v1/workflows/templates/seed", {
        tenantId,
        method: "POST",
      }),
  },
  budgets: {
    list: (tenantId: string, opts?: { status?: string; limit?: number; offset?: number }) =>
      request<{ budgets: BudgetSummary[]; limit: number; offset: number }>(
        `/api/v1/budgets?${new URLSearchParams({
          ...(opts?.status && { status: opts.status }),
          ...(opts?.limit != null && { limit: String(opts.limit) }),
          ...(opts?.offset != null && { offset: String(opts.offset) }),
        }).toString()}`,
        { tenantId }
      ),
    get: (tenantId: string, budgetId: string) =>
      request<BudgetDetail>(`/api/v1/budgets/${encodeURIComponent(budgetId)}`, { tenantId }),
    getDashboard: (tenantId: string, budgetId?: string) =>
      request<BudgetDashboardResponse>(
        `/api/v1/budgets/dashboard${budgetId ? `?budget_id=${encodeURIComponent(budgetId)}` : ""}`,
        { tenantId }
      ),
    getVariance: (tenantId: string, budgetId: string, opts?: { period?: number; department?: string }) => {
      const params = new URLSearchParams();
      if (opts?.period != null) params.set("period", String(opts.period));
      if (opts?.department) params.set("department", opts.department);
      const qs = params.toString();
      return request<{ variances: BudgetVarianceItem[]; materiality_pct: number }>(
        `/api/v1/budgets/${encodeURIComponent(budgetId)}/variance${qs ? `?${qs}` : ""}`,
        { tenantId }
      );
    },
    reforecast: (tenantId: string, budgetId: string, body: { horizon_months?: number; department?: string }) =>
      request<{ budget_id: string; horizon_months: number; reforecast_rows: number; status: string }>(
        `/api/v1/budgets/${encodeURIComponent(budgetId)}/reforecast`,
        { tenantId, method: "POST", body }
      ),
  },
  boardPacks: {
    list: (tenantId: string, opts?: { status?: string; limit?: number; offset?: number }) =>
      request<{ items: BoardPackSummary[] }>(
        `/api/v1/board-packs?${new URLSearchParams({
          ...(opts?.status && { status: opts.status }),
          ...(opts?.limit != null && { limit: String(opts.limit) }),
          ...(opts?.offset != null && { offset: String(opts.offset) }),
        }).toString()}`,
        { tenantId }
      ),
    get: (tenantId: string, packId: string) =>
      request<BoardPackDetail>(`/api/v1/board-packs/${encodeURIComponent(packId)}`, { tenantId }),
    create: (
      tenantId: string,
      userId: string,
      body: { label: string; run_id: string; budget_id?: string | null; section_order?: string[]; branding_json?: Record<string, unknown> }
    ) =>
      request<BoardPackSummary>("/api/v1/board-packs", {
        tenantId,
        userId,
        method: "POST",
        body,
      }),
    generate: (tenantId: string, packId: string) =>
      request<{ pack_id: string; status: string; narrative_json: Record<string, unknown> }>(
        `/api/v1/board-packs/${encodeURIComponent(packId)}/generate`,
        { tenantId, method: "POST" }
      ),
    update: (
      tenantId: string,
      packId: string,
      body: { section_order?: string[]; label?: string; branding_json?: Record<string, unknown> }
    ) =>
      request<BoardPackSummary>(
        `/api/v1/board-packs/${encodeURIComponent(packId)}`,
        { tenantId, method: "PATCH", body }
      ),
    exportUrl: (packId: string, format: "html" | "pdf" | "pptx") =>
      `${API_URL}/api/v1/board-packs/${encodeURIComponent(packId)}/export?format=${format}`,
  },
  assignments: {
    list: (
      tenantId: string,
      opts?: { assignee_user_id?: string; status?: string; entity_type?: string; limit?: number; offset?: number },
      userId?: string
    ) =>
      request<AssignmentsResponse>(
        `/api/v1/assignments?${new URLSearchParams(
          opts
            ? Object.fromEntries(
                Object.entries(opts).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)])
              )
            : {}
        ).toString()}`,
        { tenantId, ...(userId && { userId }) }
      ),
    listPool: (tenantId: string, limit?: number, offset?: number) =>
      request<AssignmentsResponse>(
        `/api/v1/assignments/pool?${new URLSearchParams({
          ...(limit != null && { limit: String(limit) }),
          ...(offset != null && { offset: String(offset) }),
        }).toString()}`,
        { tenantId }
      ),
    get: (tenantId: string, assignmentId: string) =>
      request<AssignmentItem>(
        `/api/v1/assignments/${encodeURIComponent(assignmentId)}`,
        { tenantId }
      ),
    create: (
      tenantId: string,
      userId: string,
      body: {
        entity_type: string;
        entity_id: string;
        assignee_user_id?: string | null;
        workflow_instance_id?: string | null;
        instructions?: string | null;
        deadline?: string | null;
      }
    ) =>
      request<AssignmentItem>("/api/v1/assignments", {
        tenantId,
        userId,
        method: "POST",
        body,
      }),
    claim: (tenantId: string, userId: string, assignmentId: string) =>
      request<AssignmentItem>(
        `/api/v1/assignments/${encodeURIComponent(assignmentId)}/claim`,
        { tenantId, userId, method: "POST" }
      ),
    submit: (tenantId: string, userId: string, assignmentId: string) =>
      request<AssignmentItem>(
        `/api/v1/assignments/${encodeURIComponent(assignmentId)}/submit`,
        { tenantId, userId, method: "POST" }
      ),
    update: (
      tenantId: string,
      assignmentId: string,
      body: { status?: string; instructions?: string; deadline?: string }
    ) =>
      request<AssignmentItem>(
        `/api/v1/assignments/${encodeURIComponent(assignmentId)}`,
        { tenantId, method: "PATCH", body }
      ),
    submitReview: (
      tenantId: string,
      userId: string,
      assignmentId: string,
      body: {
        decision: "approved" | "request_changes" | "rejected";
        notes?: string | null;
        corrections?: { path: string; old_value?: string | null; new_value?: string | null; reason?: string | null }[];
      }
    ) =>
      request<ReviewItem>(
        `/api/v1/assignments/${encodeURIComponent(assignmentId)}/review`,
        { tenantId, userId, method: "POST", body }
      ),
    listReviews: (tenantId: string, assignmentId: string, limit?: number, offset?: number) => {
      const params = new URLSearchParams();
      if (limit != null) params.set("limit", String(limit));
      if (offset != null) params.set("offset", String(offset));
      const qs = params.toString();
      return request<{ reviews: ReviewItem[]; limit: number; offset: number }>(
        `/api/v1/assignments/${encodeURIComponent(assignmentId)}/reviews${qs ? `?${qs}` : ""}`,
        { tenantId }
      );
    },
  },
  feedback: {
    list: (
      tenantId: string,
      userId: string,
      opts?: { limit?: number; offset?: number; unacknowledgedOnly?: boolean }
    ) => {
      const params = new URLSearchParams();
      if (opts?.limit != null) params.set("limit", String(opts.limit));
      if (opts?.offset != null) params.set("offset", String(opts.offset));
      if (opts?.unacknowledgedOnly === true) params.set("unacknowledged_only", "true");
      const qs = params.toString();
      return request<FeedbackListResponse>(
        `/api/v1/feedback${qs ? `?${qs}` : ""}`,
        { tenantId, userId }
      );
    },
    acknowledge: (tenantId: string, userId: string, summaryId: string) =>
      request<{ summary_id: string; acknowledged: boolean }>(
        `/api/v1/feedback/${encodeURIComponent(summaryId)}/acknowledge`,
        { tenantId, userId, method: "POST" }
      ),
  },
  excelIngestion: {
    upload: (tenantId: string, userId: string | undefined, file: File) => {
      const form = new FormData();
      form.append("file", file);
      return requestForm<{
        ingestion_id: string;
        status: string;
        sheet_count: number | null;
        formula_count: number | null;
        cross_ref_count: number | null;
        classification: Record<string, unknown>;
        model_summary: Record<string, unknown>;
      }>("/api/v1/excel-ingestion/upload", { tenantId, userId, body: form });
    },
    get: (tenantId: string, ingestionId: string) =>
      request<{
        ingestion_id: string;
        filename: string;
        status: string;
        sheet_count: number | null;
        formula_count: number | null;
        cross_ref_count: number | null;
        classification: Record<string, unknown>;
        mapping: Record<string, unknown>;
        unmapped_items: unknown[];
        questions: unknown[];
        draft_session_id: string | null;
        error_message: string | null;
        created_at: string | null;
      }>(`/api/v1/excel-ingestion/${encodeURIComponent(ingestionId)}`, { tenantId }),
    analyze: (tenantId: string, ingestionId: string) =>
      request<{
        status: string;
        mapping_summary: Record<string, unknown>;
        unmapped_count: number;
        question_count: number;
        questions: unknown[];
      }>(`/api/v1/excel-ingestion/${encodeURIComponent(ingestionId)}/analyze`, {
        tenantId,
        method: "POST",
      }),
    answer: (
      tenantId: string,
      ingestionId: string,
      answers: { question_index: number; answer: string }[]
    ) =>
      request<{ mapping: Record<string, unknown>; questions: unknown[] }>(
        `/api/v1/excel-ingestion/${encodeURIComponent(ingestionId)}/answer`,
        { tenantId, method: "POST", body: { answers } }
      ),
    createDraft: (tenantId: string, userId: string | undefined, ingestionId: string) =>
      request<{
        draft_session_id: string;
        ingestion_id: string;
        revenue_streams_count: number;
        cost_items_count: number;
        unmapped_count: number;
      }>(`/api/v1/excel-ingestion/${encodeURIComponent(ingestionId)}/create-draft`, {
        tenantId,
        userId,
        method: "POST",
      }),
    list: (tenantId: string, limit?: number, offset?: number) => {
      const params = new URLSearchParams();
      if (limit != null) params.set("limit", String(limit));
      if (offset != null) params.set("offset", String(offset));
      const qs = params.toString();
      return request<{
        items: {
          ingestion_id: string;
          filename: string;
          status: string;
          sheet_count: number | null;
          draft_session_id: string | null;
          created_at: string | null;
        }[];
      }>(`/api/v1/excel-ingestion${qs ? `?${qs}` : ""}`, { tenantId });
    },
    delete: (tenantId: string, ingestionId: string) =>
      request<{ ok: boolean }>(
        `/api/v1/excel-ingestion/${encodeURIComponent(ingestionId)}`,
        { tenantId, method: "DELETE" }
      ),
    /** Build the SSE upload stream URL for POST-based streaming. */
    getUploadStreamUrl(): string {
      return `${API_URL}/api/v1/excel-ingestion/upload-stream`;
    },
    /** Build the SSE answer-stream URL for POST-based streaming. */
    getAnswerStreamUrl(ingestionId: string): string {
      return `${API_URL}/api/v1/excel-ingestion/${encodeURIComponent(ingestionId)}/answer-stream`;
    },
  },
  orgStructures: {
    list: (tenantId: string, limit?: number, offset?: number, status?: string) => {
      const params = new URLSearchParams();
      if (limit != null) params.set("limit", String(limit));
      if (offset != null) params.set("offset", String(offset));
      if (status) params.set("status", status);
      const qs = params.toString();
      return request<{
        items: {
          org_id: string;
          group_name: string;
          reporting_currency: string;
          status: string;
          entity_count: number;
          created_at: string | null;
        }[];
      }>(`/api/v1/org-structures${qs ? `?${qs}` : ""}`, { tenantId });
    },
    create: (tenantId: string, userId: string | undefined, body: { group_name: string; reporting_currency?: string }) =>
      request<{ org_id: string; group_name: string; reporting_currency: string; status: string }>(
        "/api/v1/org-structures",
        { tenantId, userId, method: "POST", body }
      ),
    get: (tenantId: string, orgId: string) =>
      request<{
        org_id: string;
        group_name: string;
        reporting_currency: string;
        status: string;
        consolidation_method: string;
        eliminate_intercompany: boolean;
        minority_interest_treatment: string;
        created_at: string | null;
        entities: unknown[];
        ownership: unknown[];
        intercompany: unknown[];
      }>(`/api/v1/org-structures/${encodeURIComponent(orgId)}`, { tenantId }),
    update: (tenantId: string, orgId: string, body: Record<string, unknown>) =>
      request<{ org_id: string; updated?: string[] }>(
        `/api/v1/org-structures/${encodeURIComponent(orgId)}`,
        { tenantId, method: "PATCH", body }
      ),
    delete: (tenantId: string, orgId: string) =>
      request<{ ok: boolean }>(`/api/v1/org-structures/${encodeURIComponent(orgId)}`, { tenantId, method: "DELETE" }),
    validate: (tenantId: string, orgId: string) =>
      request<{ status: string; checks: unknown[] }>(
        `/api/v1/org-structures/${encodeURIComponent(orgId)}/validate`,
        { tenantId, method: "POST" }
      ),
    hierarchy: (tenantId: string, orgId: string) =>
      request<{ org_id: string; roots: unknown[] }>(
        `/api/v1/org-structures/${encodeURIComponent(orgId)}/hierarchy`,
        { tenantId }
      ),
    runs: (tenantId: string, orgId: string) =>
      request<{
        items: {
          consolidated_run_id: string;
          status: string;
          created_at: string | null;
          completed_at?: string | null;
          error_message?: string | null;
        }[];
      }>(`/api/v1/org-structures/${encodeURIComponent(orgId)}/runs`, { tenantId }),
    run: (
      tenantId: string,
      userId: string | undefined,
      orgId: string,
      opts?: {
        fx_avg_rates?: Record<string, number>;
        fx_closing_rates?: Record<string, number>;
        horizon_granularity?: "monthly" | "quarterly" | "annual";
      }
    ) =>
      request<{ consolidated_run_id: string; status: string }>(
        `/api/v1/org-structures/${encodeURIComponent(orgId)}/run`,
        { tenantId, userId, method: "POST", body: opts ?? {} }
      ),
    getRun: (tenantId: string, orgId: string, runId: string) =>
      request<{
        consolidated_run_id: string;
        status: string;
        result?: unknown;
        created_at: string | null;
        completed_at: string | null;
        error_message: string | null;
      }>(`/api/v1/org-structures/${encodeURIComponent(orgId)}/runs/${encodeURIComponent(runId)}`, { tenantId }),
    getStatements: (tenantId: string, orgId: string, runId: string) =>
      request<{ income_statement: unknown[]; balance_sheet: unknown[]; cash_flow: unknown[] }>(
        `/api/v1/org-structures/${encodeURIComponent(orgId)}/runs/${encodeURIComponent(runId)}/statements`,
        { tenantId }
      ),
  },
  covenants: {
    list: (tenantId: string, opts?: { limit?: number; offset?: number }) =>
      request<{ items: CovenantDefinition[]; total: number; limit: number; offset: number }>(
        `/api/v1/covenants?${new URLSearchParams({
          ...(opts?.limit != null && { limit: String(opts.limit) }),
          ...(opts?.offset != null && { offset: String(opts.offset) }),
        }).toString()}`,
        { tenantId }
      ),
    metricRefs: (tenantId: string) =>
      request<CovenantMetricRefs>("/api/v1/covenants/metric-refs", { tenantId }),
    create: (tenantId: string, body: { label: string; metric_ref: string; operator: string; threshold_value: number }) =>
      request<CovenantDefinition>("/api/v1/covenants", { tenantId, method: "POST", body }),
    delete: (tenantId: string, covenantId: string) =>
      request<void>(`/api/v1/covenants/${encodeURIComponent(covenantId)}`, { tenantId, method: "DELETE" }),
  },
  billing: {
    listPlans: (tenantId: string) =>
      request<{ plans: BillingPlan[] }>("/api/v1/billing/plans", { tenantId }),
    getSubscription: (tenantId: string) =>
      request<{ subscription: BillingSubscription }>("/api/v1/billing/subscription", { tenantId }),
    getUsage: (tenantId: string, period?: string) =>
      request<BillingUsageResponse>(
        `/api/v1/billing/usage${period ? `?period=${encodeURIComponent(period)}` : ""}`,
        { tenantId }
      ),
    createOrUpdateSubscription: (tenantId: string, userId: string | undefined, planId: string) =>
      request<{ subscription: BillingSubscription; updated: boolean }>(
        "/api/v1/billing/subscription",
        { tenantId, userId, method: "POST", body: { plan_id: planId } }
      ),
    cancelSubscription: (tenantId: string, userId: string | undefined) =>
      request<void>("/api/v1/billing/subscription", { tenantId, userId, method: "DELETE" }),
  },
  integrations: {
    list: (tenantId: string, opts?: { limit?: number; offset?: number }) =>
      request<{ items: IntegrationConnection[]; total: number; limit: number; offset: number }>(
        `/api/v1/integrations/connections?${new URLSearchParams({
          ...(opts?.limit != null && { limit: String(opts.limit) }),
          ...(opts?.offset != null && { offset: String(opts.offset) }),
        }).toString()}`,
        { tenantId }
      ),
    initiate: (tenantId: string, userId: string | undefined, provider: string) =>
      request<{ authorize_url: string; state: string }>(
        "/api/v1/integrations/connections",
        { tenantId, userId, method: "POST", body: { provider } }
      ),
    sync: (tenantId: string, connectionId: string, body: { period_start?: string; period_end?: string }) =>
      request<{ sync_run_id: string; status: string; snapshot_id: string; records_synced: number }>(
        `/api/v1/integrations/connections/${encodeURIComponent(connectionId)}/sync`,
        { tenantId, method: "POST", body }
      ),
    snapshots: (tenantId: string, connectionId: string, opts?: { limit?: number; offset?: number }) =>
      request<{ snapshots: IntegrationSnapshot[] }>(
        `/api/v1/integrations/connections/${encodeURIComponent(connectionId)}/snapshots?${new URLSearchParams({
          ...(opts?.limit != null && { limit: String(opts.limit) }),
          ...(opts?.offset != null && { offset: String(opts.offset) }),
        }).toString()}`,
        { tenantId }
      ),
    disconnect: (tenantId: string, connectionId: string) =>
      request<void>(
        `/api/v1/integrations/connections/${encodeURIComponent(connectionId)}`,
        { tenantId, method: "DELETE" }
      ),
  },
  audit: {
    catalog: (tenantId: string) =>
      request<AuditCatalogResponse>("/api/v1/audit/events/catalog", { tenantId }),
    list: (tenantId: string, filters?: { user_id?: string; event_type?: string; resource_type?: string; start_date?: string; end_date?: string; limit?: number; offset?: number }) =>
      request<{ events: AuditEvent[]; limit: number; offset: number }>(
        `/api/v1/audit/events?${new URLSearchParams({
          ...(filters?.user_id && { user_id: filters.user_id }),
          ...(filters?.event_type && { event_type: filters.event_type }),
          ...(filters?.resource_type && { resource_type: filters.resource_type }),
          ...(filters?.start_date && { start_date: filters.start_date }),
          ...(filters?.end_date && { end_date: filters.end_date }),
          ...(filters?.limit != null && { limit: String(filters.limit) }),
          ...(filters?.offset != null && { offset: String(filters.offset) }),
        }).toString()}`,
        { tenantId }
      ),
    exportUrl: (filters?: { format?: string; user_id?: string; event_type?: string; resource_type?: string; start_date?: string; end_date?: string }) => {
      const params = new URLSearchParams({
        ...(filters?.format && { format: filters.format }),
        ...(filters?.user_id && { user_id: filters.user_id }),
        ...(filters?.event_type && { event_type: filters.event_type }),
        ...(filters?.resource_type && { resource_type: filters.resource_type }),
        ...(filters?.start_date && { start_date: filters.start_date }),
        ...(filters?.end_date && { end_date: filters.end_date }),
      });
      return `${API_URL}/api/v1/audit/events/export?${params.toString()}`;
    },
  },
  memos: {
    list: (tenantId: string, opts?: { limit?: number; offset?: number; memo_type?: string }) =>
      request<{ items: MemoSummary[]; total: number; limit: number; offset: number }>(
        `/api/v1/memos?${new URLSearchParams({
          ...(opts?.memo_type && { memo_type: opts.memo_type }),
          ...(opts?.limit != null && { limit: String(opts.limit) }),
          ...(opts?.offset != null && { offset: String(opts.offset) }),
        }).toString()}`,
        { tenantId }
      ),
    create: (tenantId: string, userId: string | undefined, body: { run_id: string; memo_type?: string; title?: string }) =>
      request<{ memo_id: string; memo_type: string; run_id: string; status: string }>(
        "/api/v1/memos",
        { tenantId, userId, method: "POST", body }
      ),
    get: (tenantId: string, memoId: string) =>
      request<MemoSummary & { sections_json: unknown[]; outputs_json: Record<string, unknown> }>(
        `/api/v1/memos/${encodeURIComponent(memoId)}`,
        { tenantId }
      ),
    downloadUrl: (memoId: string, format: string = "html") =>
      `${API_URL}/api/v1/memos/${encodeURIComponent(memoId)}/download?format=${encodeURIComponent(format)}`,
    delete: (tenantId: string, memoId: string) =>
      request<void>(`/api/v1/memos/${encodeURIComponent(memoId)}`, { tenantId, method: "DELETE" }),
  },
  documents: {
    list: (tenantId: string, opts: { entity_type: string; entity_id: string; limit?: number; offset?: number }) =>
      request<{ items: DocumentItem[]; total: number; limit: number; offset: number }>(
        `/api/v1/documents?${new URLSearchParams({
          entity_type: opts.entity_type,
          entity_id: opts.entity_id,
          ...(opts.limit != null && { limit: String(opts.limit) }),
          ...(opts.offset != null && { offset: String(opts.offset) }),
        }).toString()}`,
        { tenantId }
      ),
    upload: (tenantId: string, userId: string | undefined, opts: { entity_type: string; entity_id: string; file: File }) => {
      const form = new FormData();
      form.append("file", opts.file);
      return requestForm<DocumentItem>(
        `/api/v1/documents?entity_type=${encodeURIComponent(opts.entity_type)}&entity_id=${encodeURIComponent(opts.entity_id)}`,
        { tenantId, userId, body: form }
      );
    },
    downloadUrl: (documentId: string) =>
      `${API_URL}/api/v1/documents/${encodeURIComponent(documentId)}`,
    delete: (tenantId: string, documentId: string) =>
      request<void>(`/api/v1/documents/${encodeURIComponent(documentId)}`, { tenantId, method: "DELETE" }),
  },
  comments: {
    list: (tenantId: string, opts: { entity_type: string; entity_id: string; limit?: number; offset?: number }) =>
      request<{ items: CommentItem[]; total: number; limit: number; offset: number }>(
        `/api/v1/comments?${new URLSearchParams({
          entity_type: opts.entity_type,
          entity_id: opts.entity_id,
          ...(opts.limit != null && { limit: String(opts.limit) }),
          ...(opts.offset != null && { offset: String(opts.offset) }),
        }).toString()}`,
        { tenantId }
      ),
    create: (tenantId: string, userId: string | undefined, body: { entity_type: string; entity_id: string; body: string; parent_comment_id?: string }) =>
      request<CommentItem>("/api/v1/comments", { tenantId, userId, method: "POST", body }),
    delete: (tenantId: string, userId: string | undefined, commentId: string) =>
      request<void>(`/api/v1/comments/${encodeURIComponent(commentId)}`, { tenantId, userId, method: "DELETE" }),
  },
  activity: {
    list: (tenantId: string, opts?: { user_id?: string; resource_type?: string; resource_id?: string; since?: string; limit?: number; offset?: number }) =>
      request<{ items: ActivityItem[]; total: number; limit: number; offset: number }>(
        `/api/v1/activity?${new URLSearchParams({
          ...(opts?.user_id && { user_id: opts.user_id }),
          ...(opts?.resource_type && { resource_type: opts.resource_type }),
          ...(opts?.resource_id && { resource_id: opts.resource_id }),
          ...(opts?.since && { since: opts.since }),
          ...(opts?.limit != null && { limit: String(opts.limit) }),
          ...(opts?.offset != null && { offset: String(opts.offset) }),
        }).toString()}`,
        { tenantId }
      ),
  },
  boardPackSchedules: {
    list: (tenantId: string, opts?: { limit?: number; offset?: number }) =>
      request<{ items: BoardPackSchedule[]; total: number; limit: number; offset: number }>(
        `/api/v1/board-packs/schedules?${new URLSearchParams({
          ...(opts?.limit != null && { limit: String(opts.limit) }),
          ...(opts?.offset != null && { offset: String(opts.offset) }),
        }).toString()}`,
        { tenantId }
      ),
    history: (tenantId: string, opts?: { schedule_id?: string; limit?: number; offset?: number }) =>
      request<{ items: BoardPackHistoryItem[]; total: number; limit: number; offset: number }>(
        `/api/v1/board-packs/schedules/history?${new URLSearchParams({
          ...(opts?.schedule_id && { schedule_id: opts.schedule_id }),
          ...(opts?.limit != null && { limit: String(opts.limit) }),
          ...(opts?.offset != null && { offset: String(opts.offset) }),
        }).toString()}`,
        { tenantId }
      ),
    create: (tenantId: string, userId: string | undefined, body: { label: string; run_id: string; cron_expr: string; distribution_emails?: string[]; budget_id?: string; section_order?: string[] }) =>
      request<{ schedule_id: string; label: string; run_id: string; cron_expr: string; distribution_emails: string[] }>(
        "/api/v1/board-packs/schedules",
        { tenantId, userId, method: "POST", body }
      ),
    runNow: (tenantId: string, userId: string | undefined, scheduleId: string) =>
      request<{ pack_id: string; history_id: string; status: string }>(
        `/api/v1/board-packs/schedules/${encodeURIComponent(scheduleId)}/run-now`,
        { tenantId, userId, method: "POST" }
      ),
    delete: (tenantId: string, scheduleId: string) =>
      request<void>(`/api/v1/board-packs/schedules/${encodeURIComponent(scheduleId)}`, { tenantId, method: "DELETE" }),
  },
  currency: {
    getSettings: (tenantId: string) =>
      request<CurrencySettings>("/api/v1/currency/settings", { tenantId }),
    updateSettings: (tenantId: string, body: { base_currency: string; reporting_currency: string; fx_source: string }) =>
      request<{ ok: boolean; base_currency: string; reporting_currency: string }>(
        "/api/v1/currency/settings",
        { tenantId, method: "PUT", body }
      ),
    listRates: (tenantId: string, opts?: { limit?: number; offset?: number; from_currency?: string; to_currency?: string }) =>
      request<{ rates: FxRate[]; total: number; limit: number; offset: number }>(
        `/api/v1/currency/rates?${new URLSearchParams({
          ...(opts?.from_currency && { from_currency: opts.from_currency }),
          ...(opts?.to_currency && { to_currency: opts.to_currency }),
          ...(opts?.limit != null && { limit: String(opts.limit) }),
          ...(opts?.offset != null && { offset: String(opts.offset) }),
        }).toString()}`,
        { tenantId }
      ),
    addRate: (tenantId: string, body: { from_currency: string; to_currency: string; effective_date: string; rate: number }) =>
      request<{ from_currency: string; to_currency: string; effective_date: string; rate: number }>(
        "/api/v1/currency/rates",
        { tenantId, method: "POST", body }
      ),
    deleteRate: (tenantId: string, fromCurrency: string, toCurrency: string, effectiveDate: string) =>
      request<void>(
        `/api/v1/currency/rates/${encodeURIComponent(fromCurrency)}/${encodeURIComponent(toCurrency)}/${encodeURIComponent(effectiveDate)}`,
        { tenantId, method: "DELETE" }
      ),
    convert: (tenantId: string, opts: { from_currency: string; to_currency: string; as_of?: string }) =>
      request<{ rate: number; from_currency: string; to_currency: string; as_of: string }>(
        `/api/v1/currency/convert?${new URLSearchParams({
          from_currency: opts.from_currency,
          to_currency: opts.to_currency,
          ...(opts.as_of && { as_of: opts.as_of }),
        }).toString()}`,
        { tenantId }
      ),
  },
  benchmark: {
    getOptIn: (tenantId: string) =>
      request<BenchmarkOptIn>("/api/v1/benchmark/opt-in", { tenantId }),
    setOptIn: (tenantId: string, body: { industry_segment?: string; size_segment?: string }) =>
      request<{ ok: boolean; industry_segment: string; size_segment: string }>(
        "/api/v1/benchmark/opt-in",
        { tenantId, method: "PUT", body }
      ),
    deleteOptIn: (tenantId: string) =>
      request<void>("/api/v1/benchmark/opt-in", { tenantId, method: "DELETE" }),
    getSummary: (tenantId: string, segmentKey?: string) =>
      request<BenchmarkSummary>(
        `/api/v1/benchmark/summary${segmentKey ? `?segment_key=${encodeURIComponent(segmentKey)}` : ""}`,
        { tenantId }
      ),
  },
  marketplace: {
    list: (tenantId: string, opts?: { industry?: string; template_type?: string; limit?: number; offset?: number }) =>
      request<{ items: MarketplaceTemplate[]; total: number; limit: number; offset: number }>(
        `/api/v1/marketplace/templates?${new URLSearchParams({
          ...(opts?.industry && { industry: opts.industry }),
          ...(opts?.template_type && { template_type: opts.template_type }),
          ...(opts?.limit != null && { limit: String(opts.limit) }),
          ...(opts?.offset != null && { offset: String(opts.offset) }),
        }).toString()}`,
        { tenantId }
      ),
    get: (tenantId: string, templateId: string) =>
      request<MarketplaceTemplate>(`/api/v1/marketplace/templates/${encodeURIComponent(templateId)}`, { tenantId }),
    useTemplate: (tenantId: string, userId: string | undefined, templateId: string, body: { label: string; fiscal_year: string; answers?: Record<string, unknown>; num_periods?: number }) =>
      request<{ ok: boolean; template_id: string; created: { type: string; budget_id?: string } }>(
        `/api/v1/marketplace/templates/${encodeURIComponent(templateId)}/use`,
        { tenantId, userId, method: "POST", body }
      ),
    saveAsTemplate: (tenantId: string, body: {
      source_baseline_id: string;
      name: string;
      industry: string;
      description?: string;
    }) =>
      request<{ template_id: string; name: string; industry: string; template_type: string }>(
        "/api/v1/marketplace/templates/from-baseline",
        { tenantId, method: "POST", body }
      ),
  },
  sso: {
    getConfig: (tenantId: string) =>
      request<SamlConfigResponse>("/api/v1/auth/saml/config", { tenantId }),
    updateConfig: (tenantId: string, body: { idp_metadata_url?: string | null; idp_metadata_xml?: string | null; entity_id?: string; acs_url?: string; idp_sso_url?: string | null; idp_certificate?: string | null; attribute_mapping?: Record<string, string> }) =>
      request<{ ok: boolean }>(
        "/api/v1/auth/saml/config",
        { tenantId, method: "PUT", body }
      ),
  },
  compliance: {
    export: (tenantId: string, userId: string | undefined, targetUserId: string) =>
      request<ComplianceExport>(
        `/api/v1/compliance/export?user_id=${encodeURIComponent(targetUserId)}`,
        { tenantId, userId }
      ),
    anonymize: (tenantId: string, userId: string | undefined, targetUserId: string) =>
      request<{ status: string; tenant_id: string; user_id: string }>(
        `/api/v1/compliance/anonymize-user?user_id=${encodeURIComponent(targetUserId)}`,
        { tenantId, userId, method: "POST" }
      ),
  },
  excelConnections: {
    list: (tenantId: string, opts?: { limit?: number; offset?: number }) =>
      request<{ items: ExcelConnection[]; total: number; limit: number; offset: number }>(
        `/api/v1/excel/connections?${new URLSearchParams({
          ...(opts?.limit != null && { limit: String(opts.limit) }),
          ...(opts?.offset != null && { offset: String(opts.offset) }),
        }).toString()}`,
        { tenantId }
      ),
    create: (tenantId: string, userId: string | undefined, body: { label?: string; mode: string; target_json: Record<string, unknown>; bindings_json: Record<string, unknown>[] }) =>
      request<{ excel_connection_id: string; label: string | null; mode: string; target_json: Record<string, unknown>; bindings_json: Record<string, unknown>[] }>(
        "/api/v1/excel/connections",
        { tenantId, userId, method: "POST", body }
      ),
    pull: (tenantId: string, userId: string | undefined, connectionId: string) =>
      request<{ values: ExcelPullValue[] }>(
        `/api/v1/excel/connections/${encodeURIComponent(connectionId)}/pull`,
        { tenantId, userId, method: "POST" }
      ),
    push: (tenantId: string, connectionId: string, changes: { binding_id: string; new_value: unknown }[]) =>
      request<{ received: number; status: string }>(
        `/api/v1/excel/connections/${encodeURIComponent(connectionId)}/push`,
        { tenantId, method: "POST", body: { changes } }
      ),
    delete: (tenantId: string, connectionId: string) =>
      request<void>(`/api/v1/excel/connections/${encodeURIComponent(connectionId)}`, { tenantId, method: "DELETE" }),
  },
  ventures: {
    templates: (tenantId: string) =>
      request<{ template_id: string; label: string }[]>(
        "/api/v1/ventures/templates",
        { tenantId }
      ),
    create: (tenantId: string, body: { template_id: string; entity_name?: string }) =>
      request<{ venture_id: string; template_id: string; entity_name: string; question_plan: Record<string, unknown>[] }>(
        "/api/v1/ventures",
        { tenantId, method: "POST", body }
      ),
    submitAnswers: (tenantId: string, ventureId: string, answers: Record<string, string>) =>
      request<{ venture_id: string; answers: Record<string, string> }>(
        `/api/v1/ventures/${encodeURIComponent(ventureId)}/answers`,
        { tenantId, method: "POST", body: { answers } }
      ),
    generateDraft: (tenantId: string, userId: string | undefined, ventureId: string) =>
      request<{ draft_session_id: string; venture_id: string; status: string }>(
        `/api/v1/ventures/${encodeURIComponent(ventureId)}/generate-draft`,
        { tenantId, userId, method: "POST" }
      ),
    list: (tenantId: string) =>
      request<{ items: VentureSummary[]; total: number }>(
        "/api/v1/ventures",
        { tenantId }
      ),
    get: (tenantId: string, ventureId: string) =>
      request<VentureDetail>(
        `/api/v1/ventures/${encodeURIComponent(ventureId)}`,
        { tenantId }
      ),
  },
  changesets: {
    list: (tenantId: string, opts?: { baseline_id?: string; status?: string; limit?: number; offset?: number }) =>
      request<{ items: { changeset_id: string; baseline_id: string; base_version: string; status: string; label?: string; created_at: string | null; overrides: unknown[] }[]; total: number; limit: number; offset: number }>(
        `/api/v1/changesets?${new URLSearchParams({
          ...(opts?.baseline_id && { baseline_id: opts.baseline_id }),
          ...(opts?.status && { status: opts.status }),
          ...(opts?.limit != null && { limit: String(opts.limit) }),
          ...(opts?.offset != null && { offset: String(opts.offset) }),
        }).toString()}`,
        { tenantId }
      ),
    create: (tenantId: string, userId: string | undefined, body: { baseline_id: string; base_version: string; overrides?: { path: string; value: unknown }[]; label?: string }) =>
      request<{ changeset_id: string; baseline_id: string; base_version: string; status: string; overrides: unknown[] }>(
        "/api/v1/changesets",
        { tenantId, userId, method: "POST", body }
      ),
    get: (tenantId: string, changesetId: string) =>
      request<{ changeset_id: string; baseline_id: string; base_version: string; status: string; created_at: string | null; overrides: unknown[] }>(
        `/api/v1/changesets/${encodeURIComponent(changesetId)}`,
        { tenantId }
      ),
    test: (tenantId: string, changesetId: string) =>
      request<{ time_series: Record<string, number[]>; applied_overrides: number }>(
        `/api/v1/changesets/${encodeURIComponent(changesetId)}/test`,
        { tenantId, method: "POST" }
      ),
    merge: (tenantId: string, userId: string | undefined, changesetId: string) =>
      request<{ changeset_id: string; baseline_id: string; new_version: string; status: string }>(
        `/api/v1/changesets/${encodeURIComponent(changesetId)}/merge`,
        { tenantId, userId, method: "POST" }
      ),
  },
  metrics: {
    getSummary: (tenantId: string) =>
      request<MetricsSummary>("/api/v1/metrics/summary", { tenantId }),
  },
  csvImport: {
    upload: (tenantId: string, userId: string | undefined, opts: { file: File; parent_baseline_id: string; parent_baseline_version?: string; label?: string; column_mapping?: Record<string, string> }) => {
      const form = new FormData();
      form.append("file", opts.file);
      const params = new URLSearchParams({
        parent_baseline_id: opts.parent_baseline_id,
        ...(opts.parent_baseline_version && { parent_baseline_version: opts.parent_baseline_version }),
        ...(opts.label && { label: opts.label }),
        ...(opts.column_mapping && { column_mapping: JSON.stringify(opts.column_mapping) }),
      });
      return requestForm<CsvImportResponse>(
        `/api/v1/import/csv?${params.toString()}`,
        { tenantId, userId, body: form }
      );
    },
  },

  // --- AFS (Annual Financial Statements) ---
  afs: {
    // Frameworks
    listFrameworks: (tenantId: string) =>
      request<{ items: AFSFramework[] }>("/api/v1/afs/frameworks", { tenantId }),
    seedFrameworks: (tenantId: string) =>
      request<{ seeded: number; message: string }>("/api/v1/afs/frameworks/seed", { tenantId, method: "POST" }),
    getFramework: (tenantId: string, frameworkId: string) =>
      request<AFSFramework>(`/api/v1/afs/frameworks/${encodeURIComponent(frameworkId)}`, { tenantId }),
    createFramework: (tenantId: string, body: { name: string; standard: string; version?: string; jurisdiction?: string | null; disclosure_schema_json?: Record<string, unknown> | null; statement_templates_json?: Record<string, unknown> | null }) =>
      request<AFSFramework>("/api/v1/afs/frameworks", { tenantId, method: "POST", body }),
    getChecklist: (tenantId: string, frameworkId: string) =>
      request<{ items: AFSDisclosureItem[] }>(`/api/v1/afs/frameworks/${encodeURIComponent(frameworkId)}/checklist`, { tenantId }),

    // Engagements
    listEngagements: (tenantId: string, opts?: { limit?: number; offset?: number; status?: string }) => {
      const p = new URLSearchParams();
      if (opts?.limit != null) p.set("limit", String(opts.limit));
      if (opts?.offset != null) p.set("offset", String(opts.offset));
      if (opts?.status) p.set("status", opts.status);
      const qs = p.toString();
      return request<{ items: AFSEngagement[]; total: number }>(`/api/v1/afs/engagements${qs ? `?${qs}` : ""}`, { tenantId });
    },
    createEngagement: (tenantId: string, body: { entity_name: string; framework_id: string; period_start: string; period_end: string; prior_engagement_id?: string }) =>
      request<AFSEngagement>("/api/v1/afs/engagements", { tenantId, method: "POST", body }),
    getEngagement: (tenantId: string, engagementId: string) =>
      request<AFSEngagement>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}`, { tenantId }),
    updateEngagement: (tenantId: string, engagementId: string, body: Record<string, unknown>) =>
      request<AFSEngagement>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}`, { tenantId, method: "PATCH", body }),
    deleteEngagement: (tenantId: string, engagementId: string) =>
      request<void>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}`, { tenantId, method: "DELETE" }),

    // Trial Balance
    uploadTrialBalance: (tenantId: string, engagementId: string, file: File) => {
      const form = new FormData();
      form.append("file", file);
      return requestForm<AFSTrialBalance>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/trial-balance`, { tenantId, body: form });
    },
    listTrialBalances: (tenantId: string, engagementId: string) =>
      request<{ items: AFSTrialBalance[] }>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/trial-balance`, { tenantId }),

    // Prior AFS
    uploadPriorAFS: (tenantId: string, engagementId: string, file: File, sourceType: "pdf" | "excel") => {
      const form = new FormData();
      form.append("file", file);
      return requestForm<AFSPriorAFS>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/prior-afs?source_type=${sourceType}`, { tenantId, body: form });
    },
    listPriorAFS: (tenantId: string, engagementId: string) =>
      request<{ items: AFSPriorAFS[] }>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/prior-afs`, { tenantId }),
    reconcile: (tenantId: string, engagementId: string) =>
      request<{ discrepancies: AFSDiscrepancy[]; message?: string }>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/prior-afs/reconcile`, { tenantId, method: "POST" }),
    setBaseSource: (tenantId: string, engagementId: string, baseSource: string) =>
      request<AFSEngagement>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/base-source`, { tenantId, method: "POST", body: { base_source: baseSource } }),

    // Discrepancies
    listDiscrepancies: (tenantId: string, engagementId: string) =>
      request<{ items: AFSDiscrepancy[] }>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/discrepancies`, { tenantId }),
    resolveDiscrepancy: (tenantId: string, engagementId: string, discrepancyId: string, body: { resolution: string; resolution_note: string }) =>
      request<AFSDiscrepancy>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/discrepancies/${encodeURIComponent(discrepancyId)}`, { tenantId, method: "PATCH", body }),

    // Projections
    createProjection: (tenantId: string, engagementId: string, body: { month: string; basis_description: string }) =>
      request<AFSProjection>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/projections`, { tenantId, method: "POST", body }),
    listProjections: (tenantId: string, engagementId: string) =>
      request<{ items: AFSProjection[] }>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/projections`, { tenantId }),

    // Sections
    listSections: (tenantId: string, engagementId: string) =>
      request<{ items: AFSSection[] }>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/sections`, { tenantId }),
    draftSection: (tenantId: string, engagementId: string, body: { section_type: string; title: string; nl_instruction: string }) =>
      request<AFSSection>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/sections/draft`, { tenantId, method: "POST", body }),
    getSection: (tenantId: string, engagementId: string, sectionId: string) =>
      request<AFSSection>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/sections/${encodeURIComponent(sectionId)}`, { tenantId }),
    updateSection: (tenantId: string, engagementId: string, sectionId: string, body: { nl_instruction?: string; content_json?: Record<string, unknown>; title?: string }) =>
      request<AFSSection>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/sections/${encodeURIComponent(sectionId)}`, { tenantId, method: "PATCH", body }),
    lockSection: (tenantId: string, engagementId: string, sectionId: string) =>
      request<AFSSection>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/sections/${encodeURIComponent(sectionId)}/lock`, { tenantId, method: "POST" }),
    unlockSection: (tenantId: string, engagementId: string, sectionId: string) =>
      request<AFSSection>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/sections/${encodeURIComponent(sectionId)}/unlock`, { tenantId, method: "POST" }),
    validateSections: (tenantId: string, engagementId: string) =>
      request<AFSValidationResult>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/validate`, { tenantId, method: "POST" }),

    // Reviews
    submitReview: (tenantId: string, engagementId: string, body: { stage: string; comments?: string }) =>
      request<AFSReview>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/reviews/submit`, { tenantId, method: "POST", body }),
    listReviews: (tenantId: string, engagementId: string) =>
      request<{ items: AFSReview[] }>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/reviews`, { tenantId }),
    approveReview: (tenantId: string, engagementId: string, reviewId: string, body?: { comments?: string }) =>
      request<AFSReview>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/reviews/${encodeURIComponent(reviewId)}/approve`, { tenantId, method: "POST", body }),
    rejectReview: (tenantId: string, engagementId: string, reviewId: string, body?: { comments?: string }) =>
      request<AFSReview>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/reviews/${encodeURIComponent(reviewId)}/reject`, { tenantId, method: "POST", body }),
    listReviewComments: (tenantId: string, engagementId: string, reviewId: string) =>
      request<{ items: AFSReviewComment[] }>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/reviews/${encodeURIComponent(reviewId)}/comments`, { tenantId }),
    createReviewComment: (tenantId: string, engagementId: string, body: { review_id: string; section_id?: string; parent_comment_id?: string; body: string }) =>
      request<AFSReviewComment>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/reviews/comments`, { tenantId, method: "POST", body }),

    // Tax
    computeTax: (tenantId: string, engagementId: string, body: { jurisdiction?: string; statutory_rate?: number; taxable_income: number; adjustments?: { description: string; amount: number }[] }) =>
      request<AFSTaxComputation>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/tax/compute`, { tenantId, method: "POST", body }),
    listTaxComputations: (tenantId: string, engagementId: string) =>
      request<{ items: AFSTaxComputation[] }>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/tax`, { tenantId }),
    addTemporaryDifference: (tenantId: string, engagementId: string, computationId: string, body: { description: string; carrying_amount: number; tax_base: number; diff_type?: string }) =>
      request<AFSTemporaryDifference>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/tax/${encodeURIComponent(computationId)}/differences`, { tenantId, method: "POST", body }),
    generateTaxNote: (tenantId: string, engagementId: string, computationId: string, body?: { nl_instruction?: string }) =>
      request<AFSTaxComputation>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/tax/${encodeURIComponent(computationId)}/generate-note`, { tenantId, method: "POST", body }),

    // Consolidation
    linkOrg: (tenantId: string, engagementId: string, body: { org_id: string; reporting_currency?: string; fx_avg_rates?: Record<string, number>; fx_closing_rates?: Record<string, number> }) =>
      request<AFSConsolidation>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/consolidation/link`, { tenantId, method: "POST", body }),
    getConsolidation: (tenantId: string, engagementId: string) =>
      request<AFSConsolidation>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/consolidation`, { tenantId }),
    runConsolidation: (tenantId: string, engagementId: string, body?: { fx_avg_rates?: Record<string, number>; fx_closing_rates?: Record<string, number> }) =>
      request<AFSConsolidation>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/consolidation/run`, { tenantId, method: "POST", body: body ?? {} }),
    listConsolidationEntities: (tenantId: string, engagementId: string) =>
      request<{ items: AFSConsolidationEntity[] }>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/consolidation/entities`, { tenantId }),

    // Outputs
    generateOutput: (tenantId: string, engagementId: string, body: { format: string }) =>
      request<AFSOutput>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/outputs/generate`, { tenantId, method: "POST", body }),
    listOutputs: (tenantId: string, engagementId: string) =>
      request<{ items: AFSOutput[] }>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/outputs`, { tenantId }),
    downloadOutput: (tenantId: string, engagementId: string, outputId: string) =>
      request<Blob>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/outputs/${encodeURIComponent(outputId)}/download`, { tenantId }),

    // Analytics
    computeAnalytics: (tenantId: string, engagementId: string, body: { industry_segment?: string }) =>
      request<AFSAnalytics>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/analytics/compute`, { tenantId, method: "POST", body }),
    getAnalytics: (tenantId: string, engagementId: string) =>
      request<AFSAnalytics>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/analytics`, { tenantId }),
    getAnalyticsRatios: (tenantId: string, engagementId: string) =>
      request<Record<string, number | null>>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/analytics/ratios`, { tenantId }),
    getAnalyticsAnomalies: (tenantId: string, engagementId: string) =>
      request<{ anomalies: { ratio_key: string; severity: string; description: string; disclosure_impact: string }[] }>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/analytics/anomalies`, { tenantId }),
    getGoingConcern: (tenantId: string, engagementId: string) =>
      request<{ risk_level: string; factors: { factor: string; indicator: string; detail: string }[]; recommendation: string; disclosure_required: boolean }>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/analytics/going-concern`, { tenantId }),

    // Phase 6: Custom frameworks + roll-forward
    inferFramework: (tenantId: string, body: { description: string; jurisdiction?: string; entity_type?: string }) =>
      request<AFSFramework & { items_count: number }>("/api/v1/afs/frameworks/infer", { tenantId, method: "POST", body }),
    addDisclosureItem: (tenantId: string, frameworkId: string, body: { section: string; reference?: string; description: string; required?: boolean }) =>
      request<AFSDisclosureItem>(`/api/v1/afs/frameworks/${encodeURIComponent(frameworkId)}/items`, { tenantId, method: "POST", body }),
    rollforward: (tenantId: string, engagementId: string) =>
      request<{ sections_copied: number; comparatives_copied: boolean }>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/rollforward`, { tenantId, method: "POST" }),
  },

  // --- PIM (Portfolio Intelligence Module) ---
  pim: {
    universe: {
      list: (tenantId: string, opts?: { limit?: number; offset?: number; sector?: string; active_only?: boolean }) =>
        request<PimUniverseListResponse>(
          `/api/v1/pim/universe?${new URLSearchParams({
            ...(opts?.limit != null && { limit: String(opts.limit) }),
            ...(opts?.offset != null && { offset: String(opts.offset) }),
            ...(opts?.sector && { sector: opts.sector }),
            ...(opts?.active_only != null && { active_only: String(opts.active_only) }),
          }).toString()}`,
          { tenantId }
        ),
      add: (tenantId: string, body: { ticker: string; company_name: string; sector?: string; sub_sector?: string; country_iso?: string; exchange?: string; currency?: string; tags?: string[]; notes?: string }) =>
        request<PimUniverseCompany>("/api/v1/pim/universe", { tenantId, method: "POST", body }),
      get: (tenantId: string, companyId: string) =>
        request<PimUniverseCompany>(`/api/v1/pim/universe/${encodeURIComponent(companyId)}`, { tenantId }),
      update: (tenantId: string, companyId: string, body: { is_active?: boolean; sector?: string; sub_sector?: string; country_iso?: string; exchange?: string; currency?: string; tags?: string[]; notes?: string }) =>
        request<PimUniverseCompany>(`/api/v1/pim/universe/${encodeURIComponent(companyId)}`, { tenantId, method: "PATCH", body }),
      remove: (tenantId: string, companyId: string) =>
        request<{ deleted: boolean }>(`/api/v1/pim/universe/${encodeURIComponent(companyId)}`, { tenantId, method: "DELETE" }),
      sectors: (tenantId: string) =>
        request<{ sectors: string[] }>("/api/v1/pim/universe/sectors/list", { tenantId }),
      bulkAdd: (tenantId: string, body: { companies: { ticker: string; company_name: string; sector?: string; country_iso?: string; exchange?: string }[] }) =>
        request<{ added: number; skipped: number; errors: string[] }>("/api/v1/pim/universe/bulk", { tenantId, method: "POST", body }),
    },
    sentiment: {
      scores: (tenantId: string, opts?: { company_id?: string; limit?: number; offset?: number }) =>
        request<PimSentimentScoresResponse>(
          `/api/v1/pim/sentiment/scores?${new URLSearchParams({
            ...(opts?.company_id && { company_id: opts.company_id }),
            ...(opts?.limit != null && { limit: String(opts.limit) }),
            ...(opts?.offset != null && { offset: String(opts.offset) }),
          }).toString()}`,
          { tenantId }
        ),
      aggregates: (tenantId: string, opts?: { company_id?: string; period_type?: string; months_back?: number; limit?: number; offset?: number }) =>
        request<PimSentimentAggregatesResponse>(
          `/api/v1/pim/sentiment/aggregates?${new URLSearchParams({
            ...(opts?.company_id && { company_id: opts.company_id }),
            ...(opts?.period_type && { period_type: opts.period_type }),
            ...(opts?.months_back != null && { months_back: String(opts.months_back) }),
            ...(opts?.limit != null && { limit: String(opts.limit) }),
            ...(opts?.offset != null && { offset: String(opts.offset) }),
          }).toString()}`,
          { tenantId }
        ),
      dashboard: (tenantId: string) =>
        request<PimSentimentDashboardResponse>("/api/v1/pim/sentiment/dashboard", { tenantId }),
      companyDetail: (tenantId: string, companyId: string, opts?: { period_type?: string; months_back?: number; signals_limit?: number }) =>
        request<PimSentimentCompanyDetail>(
          `/api/v1/pim/sentiment/company/${encodeURIComponent(companyId)}?${new URLSearchParams({
            ...(opts?.period_type && { period_type: opts.period_type }),
            ...(opts?.months_back != null && { months_back: String(opts.months_back) }),
            ...(opts?.signals_limit != null && { signals_limit: String(opts.signals_limit) }),
          }).toString()}`,
          { tenantId }
        ),
    },
    economic: {
      current: (tenantId: string) =>
        request<PimEconomicSnapshot>("/api/v1/pim/economic/current", { tenantId }),
      snapshots: (tenantId: string, opts?: { limit?: number; offset?: number }) =>
        request<PimEconomicSnapshotsResponse>(
          `/api/v1/pim/economic/snapshots?${new URLSearchParams({
            ...(opts?.limit != null && { limit: String(opts.limit) }),
            ...(opts?.offset != null && { offset: String(opts.offset) }),
          }).toString()}`,
          { tenantId }
        ),
    },
    cis: {
      compute: (tenantId: string, body: PimCISComputeBody) =>
        request<PimCISComputeResponse>("/api/v1/pim/cis/compute", { tenantId, method: "POST", body }),
      factorAttribution: (tenantId: string, body: PimFactorAttributionBody) =>
        request<PimFactorAttributionResponse>("/api/v1/pim/cis/factor-attribution", { tenantId, method: "POST", body }),
    },
    portfolio: {
      build: (tenantId: string, body: PimBuildPortfolioBody) =>
        request<PimPortfolioRun>("/api/v1/pim/portfolio/build", { tenantId, method: "POST", body }),
      runs: (tenantId: string, params?: { limit?: number; offset?: number }) =>
        request<PimPortfolioRunsResponse>(
          `/api/v1/pim/portfolio/runs?${new URLSearchParams({
            ...(params?.limit !== undefined && { limit: String(params.limit) }),
            ...(params?.offset !== undefined && { offset: String(params.offset) }),
          })}`,
          { tenantId },
        ),
      get: (tenantId: string, runId: string) =>
        request<PimPortfolioRun>(`/api/v1/pim/portfolio/${encodeURIComponent(runId)}`, { tenantId }),
      delete: (tenantId: string, runId: string) =>
        request<{ deleted: boolean }>(`/api/v1/pim/portfolio/${encodeURIComponent(runId)}`, { tenantId, method: "DELETE" }),
    },
    backtest: {
      run: (tenantId: string, body: PimRunBacktestBody) =>
        request<PimBacktestResult>("/api/v1/pim/backtest/run", { tenantId, method: "POST", body }),
      results: (tenantId: string, params?: { limit?: number; offset?: number }) =>
        request<PimBacktestResultsResponse>(
          `/api/v1/pim/backtest/results?${new URLSearchParams({
            ...(params?.limit !== undefined && { limit: String(params.limit) }),
            ...(params?.offset !== undefined && { offset: String(params.offset) }),
          })}`,
          { tenantId },
        ),
      get: (tenantId: string, backtestId: string) =>
        request<PimBacktestResult>(`/api/v1/pim/backtest/${encodeURIComponent(backtestId)}`, { tenantId }),
      commentary: (tenantId: string, backtestId: string) =>
        request<PimBacktestCommentary>(`/api/v1/pim/backtest/${encodeURIComponent(backtestId)}/commentary`, { tenantId }),
      addCost: (tenantId: string, backtestId: string, body: PimTransactionCostInput) =>
        request<PimTransactionCost>(`/api/v1/pim/backtest/${encodeURIComponent(backtestId)}/costs`, { tenantId, method: "POST", body }),
      listCosts: (tenantId: string, backtestId: string) =>
        request<PimTransactionCostsResponse>(`/api/v1/pim/backtest/${encodeURIComponent(backtestId)}/costs`, { tenantId }),
      summary: (tenantId: string) =>
        request<PimBacktestSummaryResponse>("/api/v1/pim/backtest/summary", { tenantId }),
    },
    markov: {
      states: (tenantId: string) =>
        request<PimMarkovStateLabelsResponse>("/api/v1/pim/markov/states", { tenantId }),
      steadyState: (tenantId: string) =>
        request<PimMarkovSteadyStateResponse>("/api/v1/pim/markov/steady-state", { tenantId }),
      topTransitions: (tenantId: string, topN?: number) =>
        request<PimMarkovTopTransitionsResponse>(
          `/api/v1/pim/markov/top-transitions${topN !== undefined ? `?top_n=${topN}` : ""}`,
          { tenantId },
        ),
    },
    pe: {
      create: (tenantId: string, body: CreatePeAssessmentBody) =>
        request<PeAssessment>("/api/v1/pim/pe/assessments", { tenantId, method: "POST", body }),
      list: (tenantId: string, params?: { limit?: number; offset?: number; vintage_year?: number }) =>
        request<PeAssessmentsResponse>(
          `/api/v1/pim/pe/assessments?${new URLSearchParams({
            ...(params?.limit !== undefined && { limit: String(params.limit) }),
            ...(params?.offset !== undefined && { offset: String(params.offset) }),
            ...(params?.vintage_year !== undefined && { vintage_year: String(params.vintage_year) }),
          })}`,
          { tenantId },
        ),
      get: (tenantId: string, assessmentId: string) =>
        request<PeAssessment>(`/api/v1/pim/pe/assessments/${encodeURIComponent(assessmentId)}`, { tenantId }),
      update: (tenantId: string, assessmentId: string, body: UpdatePeAssessmentBody) =>
        request<PeAssessment>(`/api/v1/pim/pe/assessments/${encodeURIComponent(assessmentId)}`, { tenantId, method: "PUT", body }),
      delete: (tenantId: string, assessmentId: string) =>
        request<{ deleted: boolean }>(`/api/v1/pim/pe/assessments/${encodeURIComponent(assessmentId)}`, { tenantId, method: "DELETE" }),
      compute: (tenantId: string, assessmentId: string) =>
        request<PeComputeResult>(`/api/v1/pim/pe/assessments/${encodeURIComponent(assessmentId)}/compute`, { tenantId, method: "POST", body: {} }),
      memo: (tenantId: string, assessmentId: string) =>
        request<PeMemoResult>(`/api/v1/pim/pe/assessments/${encodeURIComponent(assessmentId)}/memo`, { tenantId, method: "POST", body: {} }),
      summary: (tenantId: string) =>
        request<PePortfolioSummary>("/api/v1/pim/pe/summary", { tenantId }),
    },
    peer: {
      createBenchmark: (tenantId: string, body: CreatePeerBenchmarkBody) =>
        request<PeerBenchmark>("/api/v1/pim/peer/benchmarks", { tenantId, method: "POST", body }),
      listBenchmarks: (tenantId: string, params?: { vintage_year?: number; strategy?: string }) =>
        request<PeerBenchmarksResponse>(
          `/api/v1/pim/peer/benchmarks?${new URLSearchParams({
            ...(params?.vintage_year !== undefined && { vintage_year: String(params.vintage_year) }),
            ...(params?.strategy !== undefined && { strategy: params.strategy }),
          })}`,
          { tenantId },
        ),
      deleteBenchmark: (tenantId: string, benchmarkId: string) =>
        request<{ deleted: boolean }>(`/api/v1/pim/peer/benchmarks/${encodeURIComponent(benchmarkId)}`, { tenantId, method: "DELETE" }),
      rankAssessment: (tenantId: string, assessmentId: string, params?: { strategy?: string; geography?: string }) =>
        request<PeerRankResponse>(
          `/api/v1/pim/peer/assessments/${encodeURIComponent(assessmentId)}/rank?${new URLSearchParams({
            ...(params?.strategy !== undefined && { strategy: params.strategy }),
            ...(params?.geography !== undefined && { geography: params.geography }),
          })}`,
          { tenantId },
        ),
    },
  },
  admin: {
    llm: {
      getPolicy: (tenantId: string) =>
        request<LlmPolicyResponse>("/api/v1/admin/llm-policy", { tenantId }),
      updatePolicy: (tenantId: string, body: UpdateLlmPolicyBody) =>
        request<LlmPolicyResponse>("/api/v1/admin/llm-policy", { tenantId, method: "PUT", body }),
      resetPolicy: (tenantId: string) =>
        request<LlmPolicyResponse>("/api/v1/admin/llm-policy/reset", { tenantId, method: "POST", body: {} }),
    },
  },
};

export interface ScenarioItem {
  scenario_id: string;
  baseline_id: string;
  baseline_version: string;
  label: string;
  description?: string | null;
  overrides: { ref: string; field: string; value: number }[];
  created_at: string | null;
}

export interface TeamSummary {
  team_id: string;
  name: string;
  description: string | null;
  created_at: string | null;
  created_by: string | null;
}

export interface TeamsListResponse {
  teams: TeamSummary[];
}

export interface TeamMember {
  user_id: string;
  job_function_id: string;
  reports_to: string | null;
  created_at: string | null;
}

export interface TeamDetail {
  team_id: string;
  name: string;
  description: string | null;
  created_at: string | null;
  created_by: string | null;
  members: TeamMember[];
}

export interface JobFunction {
  job_function_id: string;
  name: string;
  created_at: string | null;
}

export interface JobFunctionsResponse {
  job_functions: JobFunction[];
}

export interface MembersResponse {
  members: TeamMember[];
}

export interface WorkflowTemplateStage {
  stage_id: string;
  name: string;
  assignee_rule: string;
  assignee_config?: Record<string, unknown>;
}

export interface WorkflowTemplate {
  template_id: string;
  name: string;
  description: string | null;
  stages: WorkflowTemplateStage[];
  created_at: string | null;
}

export interface WorkflowTemplatesResponse {
  templates: WorkflowTemplate[];
  limit: number;
  offset: number;
}

export interface WorkflowInstance {
  instance_id: string;
  template_id: string;
  entity_type: string;
  entity_id: string;
  current_stage_index: number;
  status: string;
  created_at: string | null;
  created_by: string | null;
  updated_at: string | null;
}

export interface WorkflowInstancesResponse {
  instances: WorkflowInstance[];
  limit: number;
  offset: number;
}

export interface AssignmentItem {
  assignment_id: string;
  workflow_instance_id: string | null;
  entity_type: string;
  entity_id: string;
  assignee_user_id: string | null;
  assigned_by_user_id: string | null;
  status: string;
  deadline: string | null;
  instructions: string | null;
  created_at: string | null;
  submitted_at: string | null;
}

export interface ReviewItem {
  review_id: string;
  assignment_id: string;
  reviewer_user_id: string;
  decision: string;
  notes: string | null;
  corrections: { path: string; old_value?: string | null; new_value?: string | null; reason?: string | null }[];
  created_at: string | null;
}

export interface AssignmentsResponse {
  assignments: AssignmentItem[];
  limit: number;
  offset: number;
}

export interface FeedbackLearningPoint {
  point: string;
  category?: string | null;
}

export interface FeedbackItem {
  summary_id: string;
  review_id: string;
  assignment_id: string;
  summary_text: string;
  learning_points: FeedbackLearningPoint[];
  acknowledged_at: string | null;
  created_at: string | null;
  decision: string;
  corrections: { path: string; old_value?: string | null; new_value?: string | null; reason?: string | null }[];
}

export interface FeedbackListResponse {
  items: FeedbackItem[];
  limit: number;
  offset: number;
}

// --- Covenants ---
export interface CovenantDefinition {
  covenant_id: string;
  label: string;
  metric_ref: string;
  operator: string;
  threshold_value: number;
  created_at?: string | null;
}

export interface CovenantMetricRefs {
  metric_refs: string[];
  operators: string[];
}

// --- Billing ---
export interface BillingPlan {
  plan_id: string;
  name: string;
  label?: string;
  tier?: string | number;
  price_monthly?: number;
  llm_tokens_monthly?: number;
  features?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface BillingSubscription {
  subscription_id: string;
  plan_id: string;
  status: string;
  created_at?: string | null;
  [key: string]: unknown;
}

export interface BillingUsageResponse {
  usage: {
    usage?: {
      llm_tokens_total?: number;
      mc_runs?: number;
      sync_events?: number;
      [key: string]: unknown;
    };
    [key: string]: unknown;
  };
  limits: { llm_tokens_monthly: number | null };
}

// --- Integrations ---
export interface IntegrationConnection {
  connection_id: string;
  provider: string;
  status: string;
  org_name: string | null;
  last_sync_at: string | null;
  created_at: string | null;
}

export interface IntegrationSnapshot {
  snapshot_id: string;
  connection_id: string;
  as_of: string | null;
  period_start: string | null;
  period_end: string | null;
  storage_path: string | null;
  created_at?: string | null;
}

// --- Audit ---
export interface AuditEvent {
  audit_event_id: string;
  tenant_id?: string;
  user_id: string | null;
  event_type: string;
  event_category: string;
  resource_type: string | null;
  resource_id: string | null;
  timestamp: string | null;
  event_data?: Record<string, unknown>;
}

export interface AuditCatalogResponse {
  events: Record<string, unknown>[];
}

// --- Memos ---
export interface MemoSummary {
  memo_id: string;
  memo_type: string;
  title: string;
  source_json: Record<string, unknown>;
  status: string;
  created_at: string | null;
}

// --- Documents ---
export interface DocumentItem {
  document_id: string;
  entity_type: string;
  entity_id: string;
  filename: string;
  content_type: string;
  file_size: number | null;
  created_at: string | null;
  created_by: string | null;
}

// --- Comments ---
export interface CommentItem {
  comment_id: string;
  entity_type: string;
  entity_id: string;
  parent_comment_id: string | null;
  body: string;
  created_at: string | null;
  created_by: string | null;
}

// --- Activity ---
export interface ActivityItem {
  type: "audit" | "comment";
  id: string;
  timestamp: string | null;
  user_id: string | null;
  resource_type: string | null;
  resource_id: string | null;
  summary: string;
  event_type?: string;
  event_category?: string;
  event_data?: Record<string, unknown>;
  body?: string;
}

// --- Board Pack Schedules ---
export interface BoardPackSchedule {
  schedule_id: string;
  label: string;
  run_id: string;
  budget_id: string | null;
  section_order: string[];
  cron_expr: string;
  next_run_at: string | null;
  distribution_emails: string[];
  enabled: boolean;
  created_at: string | null;
}

export interface BoardPackHistoryItem {
  history_id: string;
  schedule_id: string;
  pack_id: string;
  label: string;
  run_id: string;
  generated_at: string | null;
  distributed_at: string | null;
  status: string;
  error_message: string | null;
}

// --- Currency ---
export interface CurrencySettings {
  base_currency: string;
  reporting_currency: string;
  fx_source: string;
  updated_at: string | null;
}

export interface FxRate {
  from_currency: string;
  to_currency: string;
  effective_date: string;
  rate: number;
  created_at: string | null;
  created_by: string | null;
}

// --- Benchmark ---
export interface BenchmarkOptIn {
  opted_in: boolean;
  industry_segment?: string;
  size_segment?: string;
  opted_in_at?: string | null;
}

export interface BenchmarkSummary {
  segment_key: string;
  metrics: {
    metric_name: string;
    median: number;
    p25: number | null;
    p75: number | null;
    sample_count: number;
    computed_at: string | null;
  }[];
}

// --- Marketplace ---
export interface MarketplaceTemplate {
  template_id: string;
  name: string;
  industry: string;
  template_type: string;
  description: string;
  created_at: string | null;
}

// --- SSO ---
export interface SamlConfigResponse {
  entity_id?: string | null;
  acs_url?: string | null;
  idp_sso_url?: string | null;
  idp_certificate?: string | null;
  idp_metadata_url?: string | null;
  attribute_mapping?: Record<string, string>;
  [key: string]: unknown;
}

// --- Compliance ---
export interface ComplianceExport {
  tenant_id: string;
  user_id: string;
  audit_events: Record<string, unknown>[];
  drafts: Record<string, unknown>[];
  notifications: Record<string, unknown>[];
  scenarios: Record<string, unknown>[];
  integration_connections: Record<string, unknown>[];
  excel_connections: Record<string, unknown>[];
  excel_sync_events: Record<string, unknown>[];
  memo_packs: Record<string, unknown>[];
}

// --- Excel Connections ---
export interface ExcelConnection {
  excel_connection_id: string;
  label: string | null;
  mode: string;
  status: string;
  target_json: Record<string, unknown>;
  bindings_json: Record<string, unknown>[];
  created_at: string | null;
  created_by: string | null;
}

export interface ExcelPullValue {
  binding_id: string;
  path: string;
  value: unknown;
}

// --- CSV Import ---
export interface CsvImportResponse {
  draft_session_id: string;
  scenario_id: string;
  overrides_count: number;
  status: string;
}

export interface MetricsSummary {
  request_count: number;
  latency_p50_ms: number;
  latency_p95_ms: number;
  by_endpoint: Record<string, number>;
}

// --- AFS (Annual Financial Statements) ---
export interface AFSFramework {
  framework_id: string;
  name: string;
  standard: string;
  version: string;
  jurisdiction: string | null;
  is_builtin: boolean;
  disclosure_schema_json: Record<string, unknown> | null;
  statement_templates_json: Record<string, unknown> | null;
  created_by: string | null;
  created_at: string;
}

export interface AFSDisclosureItem {
  item_id: string;
  framework_id: string;
  section: string;
  reference: string | null;
  description: string;
  required: boolean;
  applicable_entity_types: string[] | null;
}

export interface AFSEngagement {
  engagement_id: string;
  entity_name: string;
  framework_id: string;
  period_start: string;
  period_end: string;
  prior_engagement_id: string | null;
  status: string;
  base_source: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface AFSTrialBalance {
  trial_balance_id: string;
  engagement_id: string;
  entity_id: string | null;
  source: string;
  data_json: unknown[];
  mapped_accounts_json: Record<string, unknown> | null;
  period_months: string[] | null;
  is_partial: boolean;
  uploaded_at: string;
}

export interface AFSPriorAFS {
  prior_afs_id: string;
  engagement_id: string;
  source_type: string;
  filename: string;
  file_size: number | null;
  extracted_json: Record<string, unknown> | null;
  upload_path: string | null;
  uploaded_at: string;
}

export interface AFSDiscrepancy {
  discrepancy_id: string;
  engagement_id: string;
  line_item: string;
  pdf_value: number | null;
  excel_value: number | null;
  difference: number | null;
  resolution: string | null;
  resolution_note: string | null;
  resolved_by: string | null;
  resolved_at: string | null;
}

export interface AFSProjection {
  projection_id: string;
  engagement_id: string;
  month: string;
  basis_description: string;
  projected_data_json: Record<string, unknown>;
  is_estimate: boolean;
  created_by: string | null;
  created_at: string;
}

export interface AFSSection {
  section_id: string;
  engagement_id: string;
  section_type: string;
  section_number: number;
  title: string;
  content_json: {
    title: string;
    paragraphs: { type: "text" | "table" | "heading"; content: string }[];
    references: string[];
    warnings: string[];
  } | null;
  status: string;
  version: number;
  rolled_forward_from: string | null;
  needs_review: boolean;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  llm_cost_usd?: number;
  llm_tokens?: number;
}

export interface AFSSectionHistory {
  history_id: string;
  section_id: string;
  version: number;
  content_json: Record<string, unknown>;
  nl_instruction: string | null;
  changed_by: string | null;
  changed_at: string;
}

export interface AFSValidationResult {
  compliant: boolean;
  missing_disclosures: { reference: string; description: string; severity: string }[];
  suggestions: string[];
  llm_cost_usd?: number;
  llm_tokens?: number;
  sections_validated?: number;
  checklist_items_checked?: number;
}

export interface AFSReview {
  review_id: string;
  engagement_id: string;
  stage: string;
  status: string;
  submitted_by: string | null;
  submitted_at: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  comments: string | null;
}

export interface AFSReviewComment {
  comment_id: string;
  review_id: string;
  section_id: string | null;
  parent_comment_id: string | null;
  body: string;
  resolved: boolean;
  created_by: string | null;
  created_at: string;
}

export interface AFSTaxComputation {
  computation_id: string;
  engagement_id: string;
  entity_id: string | null;
  jurisdiction: string;
  statutory_rate: number;
  taxable_income: number;
  current_tax: number;
  deferred_tax_json: Record<string, unknown>;
  reconciliation_json: { description: string; amount: number; tax_effect: number }[];
  tax_note_json: {
    title: string;
    paragraphs: { type: "text" | "table" | "heading"; content: string }[];
    references: string[];
    warnings: string[];
  } | null;
  temporary_differences?: AFSTemporaryDifference[];
  created_by: string | null;
  created_at: string;
  updated_at: string;
  llm_cost_usd?: number;
  llm_tokens?: number;
}

export interface AFSTemporaryDifference {
  difference_id: string;
  computation_id: string;
  description: string;
  carrying_amount: number;
  tax_base: number;
  difference: number;
  deferred_tax_effect: number;
  diff_type: string;
}

export interface AFSConsolidation {
  consolidation_id: string;
  engagement_id: string;
  org_id: string;
  reporting_currency: string;
  fx_avg_rates: Record<string, number>;
  fx_closing_rates: Record<string, number>;
  elimination_entries_json: unknown[];
  consolidated_tb_json: unknown[] | null;
  entity_tb_map: Record<string, string>;
  status: string;
  error_message: string | null;
  consolidated_at: string | null;
  created_by: string | null;
  created_at: string;
}

export interface AFSConsolidationEntity {
  entity_id: string;
  name: string;
  entity_type: string;
  currency: string;
  has_trial_balance: boolean;
}

export interface AFSOutput {
  output_id: string;
  engagement_id: string;
  format: string;
  filename: string;
  file_size_bytes: number | null;
  status: string;
  error_message: string | null;
  generated_by: string | null;
  generated_at: string;
}

export interface AFSAnalytics {
  analytics_id: string;
  engagement_id: string;
  computed_at: string;
  ratios_json: Record<string, number | null>;
  benchmark_comparison_json: Record<string, {
    value: number;
    p25: number;
    median: number;
    p75: number;
    position: string;
  }>;
  anomalies_json: {
    anomalies: {
      ratio_key: string;
      severity: string;
      description: string;
      disclosure_impact: string;
    }[];
  };
  commentary_json: {
    key_highlights: string[];
    risk_factors: string[];
    outlook_points: string[];
  } | null;
  going_concern_json: {
    risk_level: string;
    factors: {
      factor: string;
      indicator: string;
      detail: string;
    }[];
    recommendation: string;
    disclosure_required: boolean;
  } | null;
  industry_segment: string | null;
  status: string;
  error_message: string | null;
  computed_by: string | null;
}

// --- PIM Types ---

export interface PimUniverseCompany {
  company_id: string;
  ticker: string;
  company_name: string;
  sector: string | null;
  sub_sector: string | null;
  country_iso: string | null;
  market_cap_usd: number | null;
  currency: string | null;
  exchange: string | null;
  is_active: boolean;
  tags: string[];
  notes: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface PimUniverseListResponse {
  items: PimUniverseCompany[];
  total: number;
  limit: number;
  offset: number;
}

export interface PimSentimentSignal {
  signal_id: string;
  company_id: string;
  source_type: string;
  source_ref: string | null;
  headline: string | null;
  published_at: string | null;
  sentiment_score: number;
  confidence: number;
  llm_model: string | null;
  created_at: string | null;
}

export interface PimSentimentAggregate {
  company_id: string;
  period_type: string;
  period_start: string | null;
  period_end: string | null;
  avg_sentiment: number;
  median_sentiment: number | null;
  min_sentiment: number | null;
  max_sentiment: number | null;
  std_sentiment: number | null;
  signal_count: number;
  avg_confidence: number | null;
  source_breakdown: Record<string, number>;
  trend_direction: string | null;
  updated_at: string | null;
}

export interface PimSentimentScoresResponse {
  items: PimSentimentSignal[];
  total: number;
  limit: number;
  offset: number;
}

export interface PimSentimentAggregatesResponse {
  items: PimSentimentAggregate[];
  total: number;
  limit: number;
  offset: number;
}

export interface PimSentimentDashboardItem {
  company_id: string;
  ticker: string;
  company_name: string;
  sector: string | null;
  total_signals: number;
  latest_avg_sentiment: number | null;
  latest_signal_count: number;
  latest_avg_confidence: number | null;
  source_breakdown: Record<string, number>;
  trend_direction: string | null;
  latest_period_start: string | null;
  latest_period_end: string | null;
  latest_signal: {
    sentiment_score: number;
    confidence: number;
    headline: string | null;
    published_at: string | null;
    source_type: string;
  } | null;
}

export interface PimSentimentDashboardResponse {
  items: PimSentimentDashboardItem[];
  total: number;
}

export interface PimSentimentCompanyDetail {
  company: {
    company_id: string;
    ticker: string;
    company_name: string;
    sector: string | null;
    sub_sector: string | null;
  };
  aggregates: PimSentimentAggregate[];
  recent_signals: PimSentimentSignal[];
}

// --- PIM Economic Context Types ---

export interface PimEconomicSnapshot {
  snapshot_id: string;
  fetched_at: string;
  gdp_growth_pct: number | null;
  cpi_yoy_pct: number | null;
  unemployment_rate: number | null;
  yield_spread_10y2y: number | null;
  ism_pmi: number | null;
  regime: "expansion" | "contraction" | "transition";
  regime_confidence: number;
  indicators_agreeing: number;
  indicators_total: number;
  created_at: string | null;
}

export interface PimEconomicSnapshotsResponse {
  snapshots: PimEconomicSnapshot[];
  limit: number;
  offset: number;
}

// --- PIM CIS Types ---

export interface PimCISFactorInput {
  company_id: string;
  sector?: string | null;
  dcf_upside_pct?: number | null;
  roe?: number | null;
  debt_to_equity?: number | null;
  revenue_growth_qoq?: number | null;
  ebitda_margin_change?: number | null;
  avg_sentiment_score?: number | null;
  trend_direction?: "improving" | "stable" | "declining" | null;
}

export interface PimCISComputeBody {
  companies: PimCISFactorInput[];
  weights?: Record<string, number> | null;
}

export interface PimCISScores {
  fundamental_quality: number | null;
  fundamental_momentum: number | null;
  idiosyncratic_sentiment: number | null;
  sentiment_momentum: number | null;
  sector_positioning: number | null;
}

export interface PimCISResult {
  company_id: string;
  cis_score: number;
  factors_available: number;
  factors_total: number;
  factor_scores: PimCISScores;
  weights_used: Record<string, number>;
  ci_lower: number | null;
  ci_upper: number | null;
  ci_method: string;
  ci_warning?: string;
  limitations: string;
}

export interface PimCISComputeResponse {
  companies: PimCISResult[];
  current_regime: "expansion" | "contraction" | "transition" | null;
  count: number;
}

export interface PimFactorAttributionBody {
  company_id: string;
  cis_score: number;
  fundamental_quality?: number | null;
  fundamental_momentum?: number | null;
  idiosyncratic_sentiment?: number | null;
  sentiment_momentum?: number | null;
  sector_positioning?: number | null;
  current_regime?: "expansion" | "contraction" | "transition" | null;
}

export interface PimFactorAttributionResponse {
  company_id: string;
  cis_score: number;
  narrative: string;
  top_driver: string;
  risk_note: string;
  limitations: string;
}

// Markov chain types (PIM-3.x / PIM-5.4)
export interface PimMarkovStateLabel {
  state_index: number;
  gdp_state: number;         // 0=contraction, 1=neutral, 2=expansion
  sentiment_state: number;   // 0=negative, 1=neutral, 2=positive
  quality_state: number;     // 0=weak, 1=average, 2=strong
  momentum_state: number;    // 0=declining, 1=stable, 2=improving
  label: string;             // e.g. "expansion/positive/strong/improving"
}

export interface PimMarkovStateLabelsResponse {
  items: PimMarkovStateLabel[];
  total: number;
}

export interface PimMarkovTopState {
  state_index: number;
  label: string;
  probability: number;
}

export interface PimMarkovSteadyStateResponse {
  top_states: PimMarkovTopState[];
  is_ergodic: boolean;
  quantecon_available: boolean;
  n_observations: number;
  matrix_id: string;
  limitations: string;
  ci_lower: number[] | null;
  ci_upper: number[] | null;
  ci_warning?: string;
}

export interface PimMarkovTransitionEdge {
  from_state: number;
  from_label: string;
  to_state: number;
  to_label: string;
  probability: number;
}

export interface PimMarkovTopTransitionsResponse {
  edges: PimMarkovTransitionEdge[];
  top_state_indices: number[];
  limitations: string;
}

export interface PimMarkovSteadyStateResult {
  top_states: { state_index: number; label: string; probability: number }[];
  is_ergodic: boolean;
  quantecon_available: boolean;
  limitations: string;
}

export interface PimMarkovCurrentState {
  state_index: number;
  label: string;
  gdp_state: number;
  sentiment_state: number;
  quality_state: number;
  momentum_state: number;
}

export interface PimFundamentalsSnapshot {
  company_id: string;
  ticker: string;
  period_end: string;
  period_type: string;
  revenue: number | null;
  gross_profit: number | null;
  ebitda: number | null;
  net_income: number | null;
  eps_diluted: number | null;
  total_assets: number | null;
  total_liabilities: number | null;
  total_equity: number | null;
  cash_and_equivalents: number | null;
  total_debt: number | null;
  roe: number | null;
  debt_to_equity: number | null;
  gross_margin_pct: number | null;
  net_margin_pct: number | null;
  market_cap: number | null;
  price: number | null;
  pe_ratio: number | null;
  ev_ebitda: number | null;
  revenue_growth_qoq: number | null;
  ebitda_margin_change: number | null;
  source: string;
  limitations: string;
}

// --- PIM Portfolio Types (PIM-4.x) ---

export interface PimPositionConstraints {
  top_n?: number;
  max_weight_pct?: number;
  max_sector_pct?: number;
  min_cis_score?: number;
  min_liquidity_usd?: number | null;
}

export interface PimPortfolioCandidate {
  company_id: string;
  cis_score: number;
  ticker?: string | null;
  name?: string | null;
  sector?: string | null;
  market_cap_usd?: number | null;
  fundamental_quality?: number | null;
  fundamental_momentum?: number | null;
  idiosyncratic_sentiment?: number | null;
  sentiment_momentum?: number | null;
  sector_positioning?: number | null;
}

export interface PimPortfolioHolding {
  rank: number;
  company_id: string;
  cis_score: number;
  weight: number;
  ticker: string | null;
  name: string | null;
  sector: string | null;
  fundamental_quality: number | null;
  fundamental_momentum: number | null;
  idiosyncratic_sentiment: number | null;
  sentiment_momentum: number | null;
  sector_positioning: number | null;
}

export interface PimPortfolioRun {
  run_id: string;
  tenant_id: string;
  run_at?: string;
  holdings: PimPortfolioHolding[];
  constraints: PimPositionConstraints;
  regime_at_run: string | null;
  n_candidates: number;
  n_holdings: number;
  avg_cis_score: number;
  total_cis_score: number;
  narrative: string | null;
  narrative_top_picks: string | null;
  narrative_risk_note: string | null;
  narrative_regime_context: string | null;
  limitations: string;
}

export interface PimBuildPortfolioBody {
  candidates: PimPortfolioCandidate[];
  constraints?: PimPositionConstraints | null;
  current_regime?: string | null;
  generate_narrative?: boolean;
}

export interface PimPortfolioRunsResponse {
  items: PimPortfolioRun[];
  total: number;
  limit: number;
  offset: number;
}

// --- PIM Backtest Types (PIM-4.7/4.8) ---

export interface PimBacktestConfig {
  lookback_days?: number;
  rebalance_freq_days?: number;
  top_n?: number;
  max_weight_pct?: number;
  max_sector_pct?: number;
  benchmark_label?: string;
  strategy_label?: string;
}

export interface PimHistoricalCISRecord {
  date: string;
  company_id: string;
  cis_score: number;
  sector?: string | null;
  ticker?: string | null;
  name?: string | null;
  realised_return?: number | null;
}

export interface PimBacktestPeriod {
  period_start: string;
  period_end: string;
  n_holdings: number;
  period_return: number;
  cumulative_return: number;
  ic: number | null;
}

export interface PimBacktestResult {
  backtest_id: string;
  tenant_id: string;
  config: PimBacktestConfig;
  n_periods: number;
  cumulative_return: number;
  annualised_return: number;
  volatility: number;
  sharpe_ratio: number | null;
  max_drawdown: number;
  ic_mean: number | null;
  ic_std: number | null;
  icir: number | null;
  periods: PimBacktestPeriod[];
  limitations: string;
}

export interface PimRunBacktestBody {
  historical_records: PimHistoricalCISRecord[];
  config?: PimBacktestConfig | null;
}

export interface PimBacktestResultsResponse {
  items: PimBacktestResult[];
  total: number;
  limit: number;
  offset: number;
}

export interface PimBacktestCommentary {
  backtest_id: string;
  commentary: string | null;
  commentary_risks: string | null;
  limitations: string;
}

export type PimCostType = "commission" | "spread" | "slippage";

export interface PimTransactionCostInput {
  cost_type: PimCostType;
  estimated_bps: number;
  n_rebalances: number;
  actual_bps?: number | null;
  description?: string | null;
}

export interface PimTransactionCost {
  cost_id: string;
  backtest_id: string;
  cost_type: PimCostType;
  estimated_bps: number;
  actual_bps: number | null;
  n_rebalances: number;
  description: string | null;
  created_at: string | null;
}

export interface PimTransactionCostsResponse {
  backtest_id: string;
  items: PimTransactionCost[];
  total: number;
}

export interface PimBacktestSummaryItem {
  strategy_label: string;
  run_count: number;
  latest_run_at: string | null;
  avg_cumulative_return: number | null;
  avg_annualised_return: number | null;
  avg_sharpe_ratio: number | null;
  avg_max_drawdown: number | null;
  avg_ic_mean: number | null;
  avg_ic_std: number | null;
  avg_icir: number | null;
  best_cumulative_return: number | null;
  worst_cumulative_return: number | null;
}

export interface PimBacktestSummaryResponse {
  items: PimBacktestSummaryItem[];
  total: number;
  note: string;
}

// --- PE Assessment Types (PIM-6.x) ---

export type PeCashFlowType = "drawdown" | "distribution" | "recallable_distribution";

export interface PeCashFlowItem {
  date: string;
  amount_usd: number;
  cf_type: PeCashFlowType;
}

export interface PeJCurvePoint {
  period_months: number;
  cumulative_return: number;
}

export interface PeAssessment {
  assessment_id: string;
  tenant_id: string;
  fund_name: string;
  vintage_year: number;
  currency: string;
  commitment_usd: number;
  cash_flows: PeCashFlowItem[];
  nav_usd: number | null;
  nav_date: string | null;
  paid_in_capital: number | null;
  distributed: number | null;
  dpi: number | null;
  tvpi: number | null;
  moic: number | null;
  irr: number | null;
  irr_computed_at: string | null;
  j_curve_json: PeJCurvePoint[] | null;
  notes: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface PeAssessmentsResponse {
  items: PeAssessment[];
  total: number;
  limit: number;
  offset: number;
}

export interface CreatePeAssessmentBody {
  fund_name: string;
  vintage_year: number;
  currency?: string;
  commitment_usd: number;
  cash_flows?: PeCashFlowItem[];
  nav_usd?: number | null;
  nav_date?: string | null;
  notes?: string | null;
}

export interface UpdatePeAssessmentBody {
  fund_name?: string;
  vintage_year?: number;
  currency?: string;
  commitment_usd?: number;
  cash_flows?: PeCashFlowItem[];
  nav_usd?: number | null;
  nav_date?: string | null;
  notes?: string | null;
}

export interface PeComputeResult {
  assessment_id: string;
  paid_in_capital: number;
  distributed: number;
  dpi: number | null;
  tvpi: number | null;
  moic: number | null;
  irr: number | null;
  irr_converged: boolean;
  j_curve: PeJCurvePoint[];
  limitations: string;
}

// --- PE Memo Types (PIM-7.2) ---

export interface PeMemoResult {
  assessment_id: string;
  fund_name: string;
  title: string;
  executive_summary: string;
  performance_analysis: string;
  risk_factors: string;
  recommendation: string;
  disclaimer: string;
  model_used: string;
}

// --- PE Portfolio Summary Types (PIM-7.9) ---

export interface PePortfolioSummary {
  total_assessments: number;
  assessments_with_irr: number;
  avg_dpi: number | null;
  avg_tvpi: number | null;
  avg_irr: number | null;
}

// --- Peer Benchmark Types (PIM-7.1) ---

export interface PeerBenchmark {
  benchmark_id: string;
  tenant_id: string;
  vintage_year: number;
  strategy: string;
  geography: string;
  dpi_p25: number | null;
  dpi_p50: number | null;
  dpi_p75: number | null;
  tvpi_p25: number | null;
  tvpi_p50: number | null;
  tvpi_p75: number | null;
  irr_p25: number | null;
  irr_p50: number | null;
  irr_p75: number | null;
  fund_count: number | null;
  data_source: string | null;
  as_of_date: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface PeerBenchmarksResponse {
  items: PeerBenchmark[];
  total: number;
  limit: number;
  offset: number;
}

export interface CreatePeerBenchmarkBody {
  vintage_year: number;
  strategy?: string;
  geography?: string;
  dpi_p25?: number | null;
  dpi_p50?: number | null;
  dpi_p75?: number | null;
  tvpi_p25?: number | null;
  tvpi_p50?: number | null;
  tvpi_p75?: number | null;
  irr_p25?: number | null;
  irr_p50?: number | null;
  irr_p75?: number | null;
  fund_count?: number | null;
  data_source?: string | null;
  as_of_date?: string | null;
}

export interface MetricRank {
  metric: string;
  value: number | null;
  p25: number | null;
  p50: number | null;
  p75: number | null;
  percentile_rank: number | null;
  quartile: number | null;
  quartile_label: string | null;
}

export interface PeerRankResponse {
  assessment_id: string;
  vintage_year: number;
  strategy: string;
  geography: string;
  benchmark_id: string | null;
  fund_count: number | null;
  data_source: string | null;
  rankings: MetricRank[];
  warning: string | null;
}

// --- Admin LLM Policy Types (REM-19) ---

export interface LlmPolicyRule {
  task_label: string;
  priority: number;
  provider: string;
  model: string;
  max_tokens?: number;
  temperature?: number;
}

export interface LlmPolicyFallback {
  provider: string;
  model: string;
  max_tokens?: number;
  temperature?: number;
}

export interface LlmPolicy {
  rules: LlmPolicyRule[];
  fallback?: LlmPolicyFallback;
}

export interface LlmPolicyResponse {
  source: "default" | "override";
  policy: LlmPolicy;
  hint: string;
}

export interface UpdateLlmPolicyBody {
  rules: LlmPolicyRule[];
  fallback?: LlmPolicyFallback | null;
}


// --- Venture Types (PIM-7.3) ---

export interface VentureSummary {
  venture_id: string;
  entity_name: string;
  template_id: string;
}

export interface VentureDetail {
  venture_id: string;
  entity_name: string;
  template_id: string;
  answers: Record<string, string>;
}
