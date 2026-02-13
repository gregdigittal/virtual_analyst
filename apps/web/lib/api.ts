/**
 * API client for Virtual Analyst backend.
 * Uses NEXT_PUBLIC_API_URL and X-Tenant-ID from caller.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface ApiOptions {
  tenantId: string;
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
  { tenantId, method = "GET", body }: ApiOptions
): Promise<T> {
  const headers: Record<string, string> = {
    "X-Tenant-ID": tenantId,
    "Content-Type": "application/json",
  };
  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers,
    ...(body !== undefined && { body: JSON.stringify(body) }),
  });
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

export const api = {
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
    create: (tenantId: string, baselineId: string, scenarioId?: string) =>
      request<{ run_id: string; status: string }>("/api/v1/runs", {
        tenantId,
        method: "POST",
        body: { baseline_id: baselineId, ...(scenarioId && { scenario_id: scenarioId }) },
      }),
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
};
