/**
 * API client for Virtual Analyst backend.
 * Uses NEXT_PUBLIC_API_URL and X-Tenant-ID from caller.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface ApiOptions {
  tenantId: string;
  method?: "GET" | "POST" | "PATCH";
  body?: unknown;
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
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(
      typeof err.detail === "string" ? err.detail : JSON.stringify(err)
    );
  }
  return res.json() as Promise<T>;
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
};
