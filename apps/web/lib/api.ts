/**
 * API client for Virtual Analyst backend.
 * Uses NEXT_PUBLIC_API_URL and X-Tenant-ID from caller.
 * When setAccessToken() is set, requests include Authorization: Bearer for API auth (C1).
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers,
    ...(body !== undefined && { body: JSON.stringify(body) }),
  });
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
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers,
    body,
  });
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

export interface StatementsData {
  income_statement?: Record<string, unknown>[] | unknown;
  balance_sheet?: Record<string, unknown>[] | unknown;
  cash_flow?: Record<string, unknown>[] | unknown;
  periods?: string[];
}

export interface KpiItem {
  period?: number;
  [key: string]: unknown;
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
  value: unknown;
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

export interface CommitResult {
  baseline_id: string;
  baseline_version: string;
  integrity?: { status: string; checks: unknown[] };
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
      request<{ model_config: unknown } & Record<string, unknown>>(
        `/api/v1/baselines/${encodeURIComponent(baselineId)}`,
        { tenantId }
      ),
    create: (tenantId: string, modelConfig: object) =>
      request<{ baseline_id: string; baseline_version: string; status: string }>(
        "/api/v1/baselines",
        { tenantId, method: "POST", body: { model_config: modelConfig } }
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
      opts?: { scenarioId?: string; mcEnabled?: boolean; numSimulations?: number; seed?: number }
    ) =>
      request<{ run_id: string; status: string; task_id?: string } & Record<string, unknown>>("/api/v1/runs", {
        tenantId,
        method: "POST",
        body: {
          baseline_id: baselineId,
          ...(opts?.scenarioId && { scenario_id: opts.scenarioId }),
          ...(opts?.mcEnabled && { mode: "monte_carlo", num_simulations: opts.numSimulations ?? 1000, seed: opts.seed ?? 42 }),
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
    list: (tenantId: string, opts?: { status?: string; limit?: number; offset?: number }) =>
      request<DraftsResponse>(
        `/api/v1/drafts?${new URLSearchParams({
          ...(opts?.status && { status: opts.status }),
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
  },
  changesets: {
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
