"use client";

import { api, type StatementsData, type KpiItem } from "@/lib/api";
import { VAButton, VACard } from "@/components/ui";
import { createClient } from "@/lib/supabase/client";
import { Nav } from "@/components/nav";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

type Tab = "statements" | "kpis";

function formatNum(n: number): string {
  if (Number.isNaN(n)) return "—";
  return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function StatementTable({
  title,
  rows,
  periods,
}: {
  title: string;
  rows: { label: string; values: number[] }[];
  periods: string[];
}) {
  return (
    <div className="mb-8">
      <h3 className="font-brand mb-2 text-lg font-medium text-va-text">
        {title}
      </h3>
      <div className="overflow-x-auto rounded-va-lg border border-va-border">
        <table className="w-full min-w-[600px] text-sm text-va-text">
          <thead>
            <tr className="border-b border-va-border bg-va-surface">
              <th className="px-3 py-2 text-left font-medium">Line item</th>
              {periods.map((p) => (
                <th
                  key={p}
                  className="px-3 py-2 text-right font-medium font-mono"
                >
                  {p}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr
                key={row.label}
                className={
                  i % 2 === 0
                    ? "border-b border-va-border/50"
                    : "border-b border-va-border/50 bg-va-surface/50"
                }
              >
                <td className="px-3 py-2 font-medium">{row.label}</td>
                {row.values.map((v, j) => (
                  <td
                    key={j}
                    className={`px-3 py-2 text-right font-mono ${
                      v < 0 ? "text-va-danger" : ""
                    }`}
                  >
                    {formatNum(v)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function statementsToRows(
  data: Record<string, number[] | undefined>,
  periodCount: number
): { label: string; values: number[] }[] {
  const rows: { label: string; values: number[] }[] = [];
  const skip = new Set(["period_index"]);
  const labelMap: Record<string, string> = {
    revenue: "Revenue",
    cogs: "COGS",
    gross_profit: "Gross profit",
    operating_expenses: "Operating expenses",
    ebitda: "EBITDA",
    depreciation_amortization: "D&A",
    ebit: "EBIT",
    interest_expense: "Interest",
    ebt: "EBT",
    tax: "Tax",
    net_income: "Net income",
    cash: "Cash",
    accounts_receivable: "AR",
    inventory: "Inventory",
    total_current_assets: "Current assets",
    ppe_gross: "PP&E (gross)",
    accumulated_depreciation: "Acc. depreciation",
    ppe_net: "PP&E (net)",
    total_assets: "Total assets",
    accounts_payable: "AP",
    total_liabilities: "Total liabilities",
    total_equity: "Total equity",
    total_liabilities_equity: "Total L&E",
    operating: "Operating",
    investing: "Investing",
    financing: "Financing",
    net_cf: "Net CF",
    opening_cash: "Opening cash",
    closing_cash: "Closing cash",
  };
  for (const [key, arr] of Object.entries(data)) {
    if (skip.has(key) || !Array.isArray(arr)) continue;
    const values = arr.slice(0, periodCount);
    const label =
      labelMap[key] ??
      key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
    rows.push({ label, values });
  }
  return rows;
}

function buildStatementRows(
  list: Record<string, unknown>[] | undefined,
  periodCount: number
): { label: string; values: number[] }[] {
  if (!list?.length) return [];
  const byKey: Record<string, number[]> = {};
  for (let t = 0; t < list.length && t < periodCount; t++) {
    const row = list[t] as Record<string, unknown>;
    for (const [k, v] of Object.entries(row)) {
      if (k === "period_index") continue;
      const num = typeof v === "number" ? v : Number(v);
      if (!byKey[k]) byKey[k] = [];
      byKey[k][t] = num;
    }
  }
  return statementsToRows(byKey, periodCount);
}

export default function RunDetailPage() {
  const params = useParams();
  const runId = params.id as string;
  const [run, setRun] = useState<{ run_id: string; status: string } | null>(
    null
  );
  const [statements, setStatements] = useState<StatementsData | null>(null);
  const [kpis, setKpis] = useState<KpiItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("statements");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const supabase = createClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session?.user?.id) return;
      const tid = session.user.id;
      setTenantId(tid);
      try {
        const [runRes, stRes, kpiRes] = await Promise.all([
          api.runs.get(tid, runId),
          api.runs.getStatements(tid, runId),
          api.runs.getKpis(tid, runId),
        ]);
        if (!cancelled) {
          setRun(runRes);
          setStatements(stRes);
          setKpis(Array.isArray(kpiRes) ? kpiRes : []);
        }
      } catch (e) {
        if (!cancelled)
          setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [runId]);

  if (!tenantId && !loading) return null;

  const periodLabels =
    Array.isArray(statements?.periods) && statements.periods.length > 0
      ? statements.periods
      : Array.from({ length: 12 }, (_, i) => `P${i}`);
  const periodCount = periodLabels.length;
  const periods = periodLabels;
  const isList = Array.isArray(statements?.income_statement)
    ? (statements!.income_statement as Record<string, unknown>[])
    : [];
  const bsList = Array.isArray(statements?.balance_sheet)
    ? (statements!.balance_sheet as Record<string, unknown>[])
    : [];
  const cfList = Array.isArray(statements?.cash_flow)
    ? (statements!.cash_flow as Record<string, unknown>[])
    : [];
  const isRows = buildStatementRows(isList, periodCount);
  const bsRows = buildStatementRows(bsList, periodCount);
  const cfRows = buildStatementRows(cfList, periodCount);

  return (
    <div className="min-h-screen bg-va-midnight">
      <Nav />
      <main className="mx-auto max-w-6xl px-4 py-8">
        <div className="mb-6 flex items-center gap-4">
          <Link
            href="/runs"
            className="text-sm text-va-text2 hover:text-va-text focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded"
          >
            ← Runs
          </Link>
        </div>
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
              Run {runId}
            </h1>
            {run && (
              <p className="mt-1 text-sm text-va-text2">Status: {run.status}</p>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <VAButton
              type="button"
              variant={tab === "statements" ? "primary" : "ghost"}
              onClick={() => setTab("statements")}
              className="!py-1.5"
            >
              Statements
            </VAButton>
            <VAButton
              type="button"
              variant={tab === "kpis" ? "primary" : "ghost"}
              onClick={() => setTab("kpis")}
              className="!py-1.5"
            >
              KPIs
            </VAButton>
            <Link
              href={`/runs/${runId}/mc`}
              className="rounded-va-sm border border-va-border bg-transparent px-3 py-1.5 text-sm font-medium text-va-text2 hover:bg-white/5 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight"
            >
              MC
            </Link>
            <Link
              href={`/runs/${runId}/valuation`}
              className="rounded-va-sm border border-va-border bg-transparent px-3 py-1.5 text-sm font-medium text-va-text2 hover:bg-white/5 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight"
            >
              Valuation
            </Link>
          </div>
        </div>
        {error && (
          <div
            className="mb-4 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger"
            role="alert"
          >
            {error}
          </div>
        )}
        {loading ? (
          <p className="text-va-text2">Loading run…</p>
        ) : tab === "statements" ? (
          <div>
            {isRows.length > 0 && (
              <StatementTable
                title="Income Statement"
                rows={isRows}
                periods={periods}
              />
            )}
            {bsRows.length > 0 && (
              <StatementTable
                title="Balance Sheet"
                rows={bsRows}
                periods={periods}
              />
            )}
            {cfRows.length > 0 && (
              <StatementTable
                title="Cash Flow"
                rows={cfRows}
                periods={periods}
              />
            )}
            {isRows.length === 0 &&
              bsRows.length === 0 &&
              cfRows.length === 0 && (
                <p className="text-va-text2">
                  No statement data for this run.
                </p>
              )}
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {kpis.length === 0 ? (
              <p className="text-va-text2">No KPI data for this run.</p>
            ) : (
              kpis.map((kpi, i) => (
                <VACard key={i} className="p-4">
                  <pre className="font-mono text-xs text-va-text2">
                    {JSON.stringify(kpi, null, 2)}
                  </pre>
                </VACard>
              ))
            )}
          </div>
        )}
      </main>
    </div>
  );
}
