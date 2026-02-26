"use client";

import { api } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { VAButton, VACard, VAInput, VASpinner } from "@/components/ui";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

interface SensitivityDriver {
  ref: string;
  impact_low: number;
  impact_high: number;
}

interface SensitivityData {
  base_fcf: number;
  pct: number;
  drivers: SensitivityDriver[];
}

interface HeatMapData {
  param_a: string;
  param_b: string;
  values_a: number[];
  values_b: number[];
  matrix: number[][];
  metric: string;
}

const PCT_OPTIONS = [0.05, 0.1, 0.2] as const;
const METRIC_OPTIONS = ["net_income", "ebitda", "revenue", "fcf"] as const;

function fmtNum(n: number): string {
  if (Number.isNaN(n)) return "\u2014";
  return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function fmtShort(n: number): string {
  if (Number.isNaN(n)) return "\u2014";
  const abs = Math.abs(n);
  if (abs >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return n.toFixed(0);
}

export default function SensitivityPage() {
  const params = useParams();
  const router = useRouter();
  const runId = params.id as string;
  const [data, setData] = useState<SensitivityData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pct, setPct] = useState(0.1);
  const [tenantId, setTenantId] = useState<string | null>(null);

  // Heat map state
  const [hmData, setHmData] = useState<HeatMapData | null>(null);
  const [hmLoading, setHmLoading] = useState(false);
  const [hmError, setHmError] = useState<string | null>(null);
  const [hmParamA, setHmParamA] = useState("metadata.tax_rate");
  const [hmParamB, setHmParamB] = useState("metadata.initial_cash");
  const [hmRangeA, setHmRangeA] = useState({ low: 0.1, high: 0.35, steps: 5 });
  const [hmRangeB, setHmRangeB] = useState({ low: 50000, high: 200000, steps: 5 });
  const [hmMetric, setHmMetric] = useState<string>("net_income");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) { router.replace("/login"); return; }
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);
      setLoading(true);
      setError(null);
      try {
        const res = await api.runs.getSensitivity(ctx.tenantId, runId, pct);
        if (!cancelled) setData(res);
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
  }, [router, runId, pct]);

  async function handleRunHeatmap() {
    if (!tenantId) return;
    setHmLoading(true);
    setHmError(null);
    try {
      const res = await api.runs.postSensitivityHeatmap(tenantId, runId, {
        param_a_path: hmParamA,
        param_a_range: [hmRangeA.low, hmRangeA.high, hmRangeA.steps],
        param_b_path: hmParamB,
        param_b_range: [hmRangeB.low, hmRangeB.high, hmRangeB.steps],
        metric: hmMetric,
      });
      setHmData(res);
    } catch (e) {
      setHmError(e instanceof Error ? e.message : String(e));
    } finally {
      setHmLoading(false);
    }
  }

  const sorted = [...(data?.drivers ?? [])].sort(
    (a, b) =>
      Math.abs(b.impact_low) +
      Math.abs(b.impact_high) -
      (Math.abs(a.impact_low) + Math.abs(a.impact_high))
  );

  const maxImpact = sorted.reduce(
    (m, d) => Math.max(m, Math.abs(d.impact_low), Math.abs(d.impact_high)),
    1
  );

  // Heat map color: scale from danger (low) to blue (high)
  function hmCellClass(val: number, min: number, max: number): string {
    if (max === min) return "bg-va-blue/30";
    const ratio = (val - min) / (max - min);
    if (ratio < 0.25) return "bg-va-danger/60";
    if (ratio < 0.5) return "bg-va-danger/25";
    if (ratio < 0.75) return "bg-va-blue/25";
    return "bg-va-blue/60";
  }

  if (!tenantId && !loading) return null;

  const hmMin = hmData ? Math.min(...hmData.matrix.flat()) : 0;
  const hmMax = hmData ? Math.max(...hmData.matrix.flat()) : 0;

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-6 flex items-center gap-4">
        <Link
          href="/runs"
          className="rounded text-sm text-va-text2 hover:text-va-text focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight"
        >
          &larr; Runs
        </Link>
        <Link
          href={`/runs/${runId}`}
          className="rounded text-sm text-va-text2 hover:text-va-text focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight"
        >
          Run {runId}
        </Link>
      </div>

      {/* --- Tornado Chart Section --- */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
          Sensitivity Analysis
        </h1>
        <div className="flex gap-2">
          {PCT_OPTIONS.map((p) => (
            <VAButton
              key={p}
              type="button"
              variant={pct === p ? "primary" : "ghost"}
              onClick={() => setPct(p)}
              className="!py-1.5"
            >
              &plusmn;{(p * 100).toFixed(0)}%
            </VAButton>
          ))}
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
        <VASpinner label="Loading sensitivity&hellip;" />
      ) : data && sorted.length > 0 ? (
        <VACard className="mb-8 p-4">
          {data.base_fcf != null && (
            <p className="mb-4 text-sm text-va-text2">
              Base FCF:{" "}
              <span className="font-mono text-va-text">
                {fmtNum(data.base_fcf)}
              </span>
            </p>
          )}

          <div className="space-y-2">
            {sorted.map((d) => {
              const lowPct =
                (Math.abs(d.impact_low) / maxImpact) * 100;
              const highPct =
                (Math.abs(d.impact_high) / maxImpact) * 100;
              return (
                <div key={d.ref} className="flex items-center gap-2">
                  <div
                    className="w-40 shrink-0 truncate text-right text-sm text-va-text"
                    title={d.ref}
                  >
                    {d.ref}
                  </div>
                  <div className="flex flex-1 items-center">
                    <div className="flex w-1/2 justify-end">
                      <div
                        className={`h-6 rounded-l ${d.impact_low < 0 ? "bg-va-danger/70" : "bg-va-blue/70"}`}
                        style={{
                          width: `${lowPct}%`,
                          minWidth: lowPct > 0 ? "2px" : "0",
                        }}
                      />
                    </div>
                    <div className="h-8 w-px bg-va-text2/40" />
                    <div className="flex w-1/2">
                      <div
                        className={`h-6 rounded-r ${d.impact_high < 0 ? "bg-va-danger/70" : "bg-va-blue/70"}`}
                        style={{
                          width: `${highPct}%`,
                          minWidth: highPct > 0 ? "2px" : "0",
                        }}
                      />
                    </div>
                  </div>
                  <div className="w-28 shrink-0 font-mono text-xs text-va-text2">
                    {fmtNum(d.impact_low)} / {fmtNum(d.impact_high)}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-4 flex justify-center gap-6 text-xs text-va-text2">
            <span className="flex items-center gap-1">
              <span className="inline-block h-3 w-3 rounded-sm bg-va-danger/70" />{" "}
              Negative impact
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block h-3 w-3 rounded-sm bg-va-blue/70" />{" "}
              Positive impact
            </span>
          </div>
        </VACard>
      ) : (
        <VACard className="mb-8 p-6 text-center text-va-text2">
          No tornado data for this run.
        </VACard>
      )}

      {/* --- Heat Map Section --- */}
      <h2 className="mb-4 font-brand text-xl font-semibold tracking-tight text-va-text">
        Two-Variable Heat Map
      </h2>

      <VACard className="mb-6 p-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs font-medium text-va-text2">Parameter A (rows)</label>
            <VAInput
              value={hmParamA}
              onChange={(e) => setHmParamA(e.target.value)}
              placeholder="e.g. metadata.tax_rate"
            />
            <div className="mt-1 flex gap-2">
              <VAInput
                type="number"
                value={hmRangeA.low}
                onChange={(e) => setHmRangeA({ ...hmRangeA, low: Number(e.target.value) })}
                placeholder="Low"
                className="w-24"
              />
              <VAInput
                type="number"
                value={hmRangeA.high}
                onChange={(e) => setHmRangeA({ ...hmRangeA, high: Number(e.target.value) })}
                placeholder="High"
                className="w-24"
              />
              <VAInput
                type="number"
                value={hmRangeA.steps}
                onChange={(e) => setHmRangeA({ ...hmRangeA, steps: Number(e.target.value) })}
                placeholder="Steps"
                className="w-16"
                min={2}
                max={20}
              />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-va-text2">Parameter B (columns)</label>
            <VAInput
              value={hmParamB}
              onChange={(e) => setHmParamB(e.target.value)}
              placeholder="e.g. metadata.initial_cash"
            />
            <div className="mt-1 flex gap-2">
              <VAInput
                type="number"
                value={hmRangeB.low}
                onChange={(e) => setHmRangeB({ ...hmRangeB, low: Number(e.target.value) })}
                placeholder="Low"
                className="w-24"
              />
              <VAInput
                type="number"
                value={hmRangeB.high}
                onChange={(e) => setHmRangeB({ ...hmRangeB, high: Number(e.target.value) })}
                placeholder="High"
                className="w-24"
              />
              <VAInput
                type="number"
                value={hmRangeB.steps}
                onChange={(e) => setHmRangeB({ ...hmRangeB, steps: Number(e.target.value) })}
                placeholder="Steps"
                className="w-16"
                min={2}
                max={20}
              />
            </div>
          </div>
        </div>
        <div className="mt-3 flex items-end gap-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-va-text2">Metric</label>
            <select
              value={hmMetric}
              onChange={(e) => setHmMetric(e.target.value)}
              className="rounded-va-xs border border-va-stroke bg-va-card px-2 py-1.5 text-sm text-va-text"
            >
              {METRIC_OPTIONS.map((m) => (
                <option key={m} value={m}>{m.replace("_", " ")}</option>
              ))}
            </select>
          </div>
          <VAButton onClick={handleRunHeatmap} disabled={hmLoading}>
            {hmLoading ? "Running\u2026" : "Generate Heat Map"}
          </VAButton>
        </div>
      </VACard>

      {hmError && (
        <div
          className="mb-4 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger"
          role="alert"
        >
          {hmError}
        </div>
      )}

      {hmLoading && <VASpinner label="Generating heat map&hellip;" />}

      {hmData && !hmLoading && (
        <VACard className="overflow-x-auto p-4">
          <p className="mb-3 text-sm text-va-text2">
            {hmData.param_a} (rows) &times; {hmData.param_b} (columns) &rarr; {hmData.metric}
          </p>
          <table className="w-full border-collapse text-xs">
            <thead>
              <tr>
                <th className="border border-va-stroke bg-va-card px-2 py-1 text-right text-va-text2">
                  {hmData.param_a} \ {hmData.param_b}
                </th>
                {hmData.values_b.map((vb, j) => (
                  <th
                    key={j}
                    className="border border-va-stroke bg-va-card px-2 py-1 text-center font-mono text-va-text2"
                  >
                    {fmtShort(vb)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {hmData.matrix.map((row, i) => (
                <tr key={i}>
                  <td className="border border-va-stroke bg-va-card px-2 py-1 text-right font-mono text-va-text2">
                    {hmData.values_a[i].toFixed(
                      hmData.values_a[i] < 1 ? 2 : 0
                    )}
                  </td>
                  {row.map((val, j) => (
                    <td
                      key={j}
                      className={`border border-va-stroke px-2 py-1 text-center font-mono text-va-text ${hmCellClass(val, hmMin, hmMax)}`}
                    >
                      {fmtShort(val)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <div className="mt-3 flex justify-center gap-4 text-xs text-va-text2">
            <span className="flex items-center gap-1">
              <span className="inline-block h-3 w-3 rounded-sm bg-va-danger/60" /> Low
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block h-3 w-3 rounded-sm bg-va-danger/25" />
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block h-3 w-3 rounded-sm bg-va-blue/25" />
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block h-3 w-3 rounded-sm bg-va-blue/60" /> High
            </span>
          </div>
        </VACard>
      )}
    </main>
  );
}
