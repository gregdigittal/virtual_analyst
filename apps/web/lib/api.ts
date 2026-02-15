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
  method?: "GET" | "POST" | "PATCH" | "DELETE";
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
  created_at: string | null;
}

export interface RunsResponse {
  items: RunSummary[];
  limit: number;
  offset: number;
}

export interface RunDetail {
  run_id: string;
  baseline_id: string;
  baseline_version: string;
  scenario_id: string | null;
  status: string;
  created_at: string | null;
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
    list: (tenantId: string) =>
      request<BaselinesResponse>("/api/v1/baselines", { tenantId }),
    get: (tenantId: string, baselineId: string) =>
      request<{ model_config: unknown }>(
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
    list: (tenantId: string) =>
      request<RunsResponse>("/api/v1/runs", { tenantId }),
    get: (tenantId: string, runId: string) =>
      request<RunDetail>(`/api/v1/runs/${encodeURIComponent(runId)}`, {
        tenantId,
      }),
    create: (
      tenantId: string,
      baselineId: string,
      opts?: { scenarioId?: string; mcEnabled?: boolean; numSimulations?: number; seed?: number }
    ) =>
      request<{ run_id: string; status: string; task_id?: string }>("/api/v1/runs", {
        tenantId,
        method: "POST",
        body: {
          baseline_id: baselineId,
          ...(opts?.scenarioId && { scenario_id: opts.scenarioId }),
          ...(opts?.mcEnabled && { mc_enabled: true, num_simulations: opts.numSimulations ?? 1000, seed: opts.seed ?? 42 }),
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
      request<{ base_fcf: number; pct: number; drivers: { ref: string; impact_low: number; impact_high: number }[] }>(
        `/api/v1/runs/${encodeURIComponent(runId)}/sensitivity?pct=${pct ?? 0.1}`,
        { tenantId }
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
    list: (tenantId: string, status?: string) =>
      request<DraftsResponse>(
        `/api/v1/drafts${status ? `?status=${encodeURIComponent(status)}` : ""}`,
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
    list: (tenantId: string, unreadOnly?: boolean, limit?: number, offset?: number) =>
      request<NotificationsResponse>(
        `/api/v1/notifications?${new URLSearchParams({
          ...(unreadOnly && { unread_only: "true" }),
          ...(limit != null && { limit: String(limit) }),
          ...(offset != null && { offset: String(offset) }),
        }).toString()}`,
        { tenantId }
      ),
    markRead: (tenantId: string, notificationId: string) =>
      request<{ id: string; read_at: string | null }>(
        `/api/v1/notifications/${encodeURIComponent(notificationId)}`,
        { tenantId, method: "PATCH" }
      ),
  },
  scenarios: {
    list: (tenantId: string, baselineId?: string) =>
      request<{ items: ScenarioItem[]; limit: number; offset: number }>(
        `/api/v1/scenarios${baselineId ? `?baseline_id=${encodeURIComponent(baselineId)}` : ""}`,
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
    list: (tenantId: string, status?: string) =>
      request<{ budgets: BudgetSummary[]; limit: number; offset: number }>(
        `/api/v1/budgets${status ? `?status=${encodeURIComponent(status)}` : ""}`,
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
    list: (tenantId: string, status?: string) =>
      request<{ items: BoardPackSummary[] }>(
        `/api/v1/board-packs${status ? `?status=${encodeURIComponent(status)}` : ""}`,
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
