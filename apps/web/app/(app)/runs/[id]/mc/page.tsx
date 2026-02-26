"use client";

import { api } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { VACard, VASpinner, VATabs } from "@/components/ui";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState, useCallback } from "react";

type McData = {
  num_simulations: number;
  seed: number;
  percentiles: Record<string, Record<string, number[]>>;
  summary: Record<string, unknown>;
};

const METRICS = ["revenue", "ebitda", "net_income", "fcf"] as const;
type Metric = (typeof METRICS)[number];

const METRIC_LABELS: Record<Metric, string> = {
  revenue: "Revenue",
  ebitda: "EBITDA",
  net_income: "Net Income",
  fcf: "FCF",
};

function fmtNum(n: number): string {
  if (Number.isNaN(n)) return "\u2014";
  return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

const SVG_W = 800;
const SVG_H = 380;
const PAD = { top: 20, right: 20, bottom: 40, left: 80 };
const CHART_W = SVG_W - PAD.left - PAD.right;
const CHART_H = SVG_H - PAD.top - PAD.bottom;

function buildAreaPath(
  upper: number[],
  lower: number[],
  xScale: (i: number) => number,
  yScale: (v: number) => number
): string {
  const n = upper.length;
  if (n === 0) return "";
  const pts: string[] = [];
  for (let i = 0; i < n; i++) pts.push(`${xScale(i)},${yScale(upper[i])}`);
  for (let i = n - 1; i >= 0; i--) pts.push(`${xScale(i)},${yScale(lower[i])}`);
  return `M${pts.join("L")}Z`;
}

function buildLinePath(
  vals: number[],
  xScale: (i: number) => number,
  yScale: (v: number) => number
): string {
  if (vals.length === 0) return "";
  return vals.map((v, i) => `${i === 0 ? "M" : "L"}${xScale(i)},${yScale(v)}`).join("");
}

function FanChart({ data, metric }: { data: McData; metric: Metric }) {
  const p = data.percentiles[metric];
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  const series = useMemo(() => {
    if (!p) return null;
    return {
      p5: p.p5 ?? [],
      p10: p.p10 ?? [],
      p25: p.p25 ?? [],
      p50: p.p50 ?? [],
      p75: p.p75 ?? [],
      p90: p.p90 ?? [],
      p95: p.p95 ?? [],
    };
  }, [p]);

  const periods = series?.p50?.length ?? 0;

  const { yMin, yMax } = useMemo(() => {
    if (!series || periods === 0) return { yMin: 0, yMax: 1 };
    const allVals = [
      ...series.p5,
      ...series.p95,
      ...series.p10,
      ...series.p90,
    ];
    const min = Math.min(...allVals);
    const max = Math.max(...allVals);
    const pad = (max - min) * 0.05 || 1;
    return { yMin: min - pad, yMax: max + pad };
  }, [series, periods]);

  const xScale = useCallback(
    (i: number) => PAD.left + (periods > 1 ? (i / (periods - 1)) * CHART_W : CHART_W / 2),
    [periods]
  );
  const yScale = useCallback(
    (v: number) => PAD.top + CHART_H - ((v - yMin) / (yMax - yMin)) * CHART_H,
    [yMin, yMax]
  );

  const yTicks = useMemo(() => {
    const count = 5;
    const step = (yMax - yMin) / count;
    return Array.from({ length: count + 1 }, (_, i) => yMin + step * i);
  }, [yMin, yMax]);

  if (!series || periods === 0) {
    return <p className="text-sm text-va-text2">No series data for {METRIC_LABELS[metric]}.</p>;
  }

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const svg = e.currentTarget;
    const rect = svg.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * SVG_W;
    const idx = Math.round(((x - PAD.left) / CHART_W) * (periods - 1));
    setHoverIdx(idx >= 0 && idx < periods ? idx : null);
  };

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${SVG_W} ${SVG_H}`}
        className="w-full"
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHoverIdx(null)}
      >
        {/* Y-axis labels */}
        {yTicks.map((v) => (
          <g key={v}>
            <line
              x1={PAD.left}
              y1={yScale(v)}
              x2={SVG_W - PAD.right}
              y2={yScale(v)}
              stroke="currentColor"
              className="text-va-border"
              strokeWidth={0.5}
              strokeDasharray="4 4"
            />
            <text
              x={PAD.left - 8}
              y={yScale(v) + 4}
              textAnchor="end"
              className="fill-va-text2 text-[10px]"
            >
              {fmtNum(v)}
            </text>
          </g>
        ))}

        {/* Fan areas */}
        <path d={buildAreaPath(series.p95, series.p5, xScale, yScale)} className="fill-va-blue" opacity={0.1} />
        <path d={buildAreaPath(series.p90, series.p10, xScale, yScale)} className="fill-va-blue" opacity={0.2} />
        <path d={buildAreaPath(series.p75, series.p25, xScale, yScale)} className="fill-va-blue" opacity={0.4} />

        {/* P50 line */}
        <path
          d={buildLinePath(series.p50, xScale, yScale)}
          fill="none"
          className="stroke-va-blue"
          strokeWidth={2}
        />

        {/* X-axis labels */}
        {Array.from({ length: periods }, (_, i) => i).map((i) => {
          const show = periods <= 12 || i % Math.ceil(periods / 12) === 0 || i === periods - 1;
          if (!show) return null;
          return (
            <text
              key={i}
              x={xScale(i)}
              y={SVG_H - 8}
              textAnchor="middle"
              className="fill-va-text2 text-[10px]"
            >
              P{i}
            </text>
          );
        })}

        {/* Hover line + tooltip */}
        {hoverIdx != null && (
          <>
            <line
              x1={xScale(hoverIdx)}
              y1={PAD.top}
              x2={xScale(hoverIdx)}
              y2={PAD.top + CHART_H}
              stroke="currentColor"
              className="text-va-text2"
              strokeWidth={1}
              strokeDasharray="3 3"
            />
            <circle cx={xScale(hoverIdx)} cy={yScale(series.p50[hoverIdx])} r={3} className="fill-va-blue" />
          </>
        )}
      </svg>

      {/* Tooltip overlay */}
      {hoverIdx != null && (
        <div
          className="pointer-events-none absolute rounded-va-sm border border-va-border bg-va-panel px-3 py-2 text-xs shadow-va-md"
          style={{
            left: `${(xScale(hoverIdx) / SVG_W) * 100}%`,
            top: 0,
            transform: "translateX(-50%)",
          }}
        >
          <p className="mb-1 font-medium text-va-text">Period {hoverIdx}</p>
          <div className="space-y-0.5 font-mono text-va-text2">
            <p>P95: {fmtNum(series.p95[hoverIdx])}</p>
            <p>P90: {fmtNum(series.p90[hoverIdx])}</p>
            <p>P75: {fmtNum(series.p75[hoverIdx])}</p>
            <p className="text-va-text">P50: {fmtNum(series.p50[hoverIdx])}</p>
            <p>P25: {fmtNum(series.p25[hoverIdx])}</p>
            <p>P10: {fmtNum(series.p10[hoverIdx])}</p>
            <p>P5: {fmtNum(series.p5[hoverIdx])}</p>
          </div>
        </div>
      )}

      <div className="mt-2 flex justify-center gap-4 text-xs text-va-text2">
        <span className="flex items-center gap-1">
          <span className="inline-block h-3 w-6 rounded-sm bg-va-blue/10" /> P5–P95
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-3 w-6 rounded-sm bg-va-blue/20" /> P10–P90
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-3 w-6 rounded-sm bg-va-blue/40" /> P25–P75
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-1 w-6 rounded-sm bg-va-blue" /> P50
        </span>
      </div>
    </div>
  );
}

export default function RunMcPage() {
  const params = useParams();
  const router = useRouter();
  const runId = params.id as string;
  const [data, setData] = useState<McData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [activeMetric, setActiveMetric] = useState<string>("revenue");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) { router.replace("/login"); return; }
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);
      try {
        const res = await api.runs.getMc(ctx.tenantId, runId);
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
  }, [router, runId]);

  if (!tenantId && !loading) return null;

  const periods = data?.percentiles?.revenue?.p50?.length ?? 0;

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
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
      <h1 className="font-brand mb-4 text-2xl font-semibold tracking-tight text-va-text">
        Monte Carlo Results
      </h1>

      {error && (
        <div
          className="mb-4 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger"
          role="alert"
        >
          {error}
        </div>
      )}

      {loading ? (
        <VASpinner label="Loading MC results\u2026" />
      ) : data ? (
        <div className="space-y-6">
          <VACard className="p-4">
            <p className="text-sm text-va-text2">
              {data.num_simulations} simulations, seed {data.seed}
            </p>
          </VACard>

          {/* Percentile table */}
          <VACard className="p-4">
            <h2 className="mb-3 font-brand text-lg font-medium text-va-text">
              Percentile table (terminal)
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-va-text">
                <thead>
                  <tr className="border-b border-va-border">
                    <th className="px-3 py-2 text-left font-medium">Metric</th>
                    <th className="px-3 py-2 text-right font-medium text-va-blue">P5</th>
                    <th className="px-3 py-2 text-right font-medium text-va-violet">P50</th>
                    <th className="px-3 py-2 text-right font-medium text-va-magenta">P95</th>
                  </tr>
                </thead>
                <tbody>
                  {METRICS.map((metric) => {
                    const p = data.percentiles[metric];
                    const last = periods - 1;
                    const p5 = p?.p5?.[last];
                    const p50 = p?.p50?.[last];
                    const p95 = p?.p95?.[last];
                    return (
                      <tr key={metric} className="border-b border-va-border/50">
                        <td className="px-3 py-2 font-medium capitalize">
                          {metric.replaceAll("_", " ")}
                        </td>
                        <td className="px-3 py-2 text-right font-mono">
                          {p5 != null ? fmtNum(p5) : "\u2014"}
                        </td>
                        <td className="px-3 py-2 text-right font-mono">
                          {p50 != null ? fmtNum(p50) : "\u2014"}
                        </td>
                        <td className="px-3 py-2 text-right font-mono">
                          {p95 != null ? fmtNum(p95) : "\u2014"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </VACard>

          {/* Fan chart with metric tabs */}
          <VATabs
            activeId={activeMetric}
            onSelect={setActiveMetric}
            tabs={METRICS.map((m) => ({
              id: m,
              label: METRIC_LABELS[m],
              content: <FanChart data={data} metric={m} />,
            }))}
          />
        </div>
      ) : (
        <p className="text-va-text2">No MC data for this run.</p>
      )}
    </main>
  );
}
