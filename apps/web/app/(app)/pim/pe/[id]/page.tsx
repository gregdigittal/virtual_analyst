"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer,
} from "recharts";
import { api, PeAssessment, PeComputeResult, MetricRank, PeerRankResponse } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { VAButton } from "@/components/ui/VAButton";
import { VACard } from "@/components/ui/VACard";
import { VASpinner } from "@/components/ui/VASpinner";
import { VABadge } from "@/components/ui/VABadge";

function fmt(v: number | null | undefined, decimals = 2): string {
  if (v == null) return "—";
  return v.toFixed(decimals);
}

function fmtPct(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

function fmtCurrency(v: number | null | undefined, currency = "USD"): string {
  if (v == null) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency, maximumFractionDigits: 0 }).format(v);
}

function MetricsTable({ a }: { a: PeAssessment }) {
  const rows: [string, string][] = [
    ["Vintage Year", String(a.vintage_year)],
    ["Currency", a.currency],
    ["Commitment", fmtCurrency(a.commitment_usd, a.currency)],
    ["Paid-In Capital", fmtCurrency(a.paid_in_capital, a.currency)],
    ["Distributed", fmtCurrency(a.distributed, a.currency)],
    ["DPI", a.dpi != null ? `${fmt(a.dpi)}x` : "—"],
    ["TVPI", a.tvpi != null ? `${fmt(a.tvpi)}x` : "—"],
    ["MOIC", a.moic != null ? `${fmt(a.moic)}x` : "—"],
    ["IRR (annualised)", fmtPct(a.irr)],
    ["Current NAV", fmtCurrency(a.nav_usd, a.currency)],
  ];
  return (
    <div className="divide-y divide-va-border">
      {rows.map(([label, value]) => (
        <div key={label} className="flex justify-between items-center py-2">
          <span className="text-sm text-va-text/60">{label}</span>
          <span className="text-sm font-mono text-va-text">{value}</span>
        </div>
      ))}
    </div>
  );
}

function JCurveChart({ data }: { data: { period_months: number; cumulative_return: number }[] }) {
  if (data.length === 0) return <p className="text-va-text/50 text-sm">No cash flow data for J-curve.</p>;
  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
        <XAxis
          dataKey="period_months"
          tickFormatter={(v: number) => `${v.toFixed(0)}m`}
          tick={{ fontSize: 11, fill: "rgba(255,255,255,0.5)" }}
          label={{ value: "Months", position: "insideBottom", offset: -4, fontSize: 11, fill: "rgba(255,255,255,0.4)" }}
        />
        <YAxis
          tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
          tick={{ fontSize: 11, fill: "rgba(255,255,255,0.5)" }}
        />
        <ReferenceLine y={0} stroke="rgba(255,255,255,0.25)" strokeDasharray="4 4" />
        <Tooltip
          contentStyle={{ background: "#1a1f2e", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 6 }}
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          formatter={(value: any) => [`${(value * 100).toFixed(1)}%`, "Cumulative Return"]}
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          labelFormatter={(label: any) => `Month ${Number(label).toFixed(0)}`}
        />
        <Line type="monotone" dataKey="cumulative_return" stroke="#3b82f6" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

function PeerRankings({ rankings, dataSource }: { rankings: MetricRank[]; dataSource: string | null }) {
  return (
    <div className="space-y-3">
      {dataSource && <p className="text-xs text-va-text/50">Source: {dataSource}</p>}
      {rankings.map((r) => (
        <div key={r.metric} className="bg-va-midnight/60 rounded-lg p-3">
          <div className="flex justify-between items-center mb-1">
            <span className="text-xs font-semibold text-va-text/70 uppercase tracking-wider">{r.metric.toUpperCase()}</span>
            {r.quartile_label && (
              <VABadge variant={r.quartile === 1 ? "success" : r.quartile === 2 ? "default" : r.quartile === 3 ? "warning" : "danger"}>
                {r.quartile_label}
              </VABadge>
            )}
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className="font-mono text-va-text">
              {r.metric === "irr" ? fmtPct(r.value) : r.value != null ? `${fmt(r.value)}x` : "—"}
            </span>
            {r.percentile_rank != null && (
              <span className="text-va-text/50 text-xs">
                {r.percentile_rank.toFixed(0)}th percentile
              </span>
            )}
          </div>
          {r.p25 != null && r.p50 != null && r.p75 != null && (
            <div className="text-xs text-va-text/40 mt-1 font-mono">
              P25: {r.metric === "irr" ? fmtPct(r.p25) : `${fmt(r.p25)}x`} ·
              P50: {r.metric === "irr" ? fmtPct(r.p50) : `${fmt(r.p50)}x`} ·
              P75: {r.metric === "irr" ? fmtPct(r.p75) : `${fmt(r.p75)}x`}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export default function PimPeDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [assessment, setAssessment] = useState<PeAssessment | null>(null);
  const [peerRank, setPeerRank] = useState<PeerRankResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [computing, setComputing] = useState(false);
  const [computeError, setComputeError] = useState<string | null>(null);
  const [generatingMemo, setGeneratingMemo] = useState(false);
  const [memo, setMemo] = useState<{ title: string; recommendation: string } | null>(null);

  useEffect(() => {
    getAuthContext().then((ctx) => {
      if (!ctx) { router.push("/login"); return; }
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);
    });
  }, [router]);

  useEffect(() => {
    if (!tenantId) return;
    setLoading(true);
    Promise.all([
      api.pim.pe.get(tenantId, id),
      api.pim.peer.rankAssessment(tenantId, id).catch(() => null),
    ])
      .then(([a, rank]) => {
        setAssessment(a);
        setPeerRank(rank);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [tenantId, id]);

  async function handleCompute() {
    if (!tenantId || !assessment) return;
    setComputing(true);
    setComputeError(null);
    try {
      const result: PeComputeResult = await api.pim.pe.compute(tenantId, assessment.assessment_id);
      // Refresh assessment to get updated metrics
      const updated = await api.pim.pe.get(tenantId, assessment.assessment_id);
      setAssessment({ ...updated, j_curve_json: result.j_curve });
    } catch (e) {
      setComputeError(String(e));
    } finally {
      setComputing(false);
    }
  }

  async function handleMemo() {
    if (!tenantId || !assessment) return;
    setGeneratingMemo(true);
    try {
      const result = await api.pim.pe.memo(tenantId, assessment.assessment_id);
      setMemo({ title: result.title, recommendation: result.recommendation });
    } catch (e) {
      setComputeError(String(e));
    } finally {
      setGeneratingMemo(false);
    }
  }

  const jCurveData = assessment?.j_curve_json ?? [];

  if (loading) {
    return <div className="flex justify-center py-12"><VASpinner /></div>;
  }

  if (error) return <p className="p-6 text-red-400">{error}</p>;
  if (!assessment) return <p className="p-6 text-va-text/50">Assessment not found.</p>;

  const hasMetrics = assessment.dpi != null || assessment.tvpi != null;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-sora font-semibold text-va-text">{assessment.fund_name}</h1>
          <p className="text-sm text-va-text/60 mt-1">
            {assessment.vintage_year} · {assessment.currency} · {fmtCurrency(assessment.commitment_usd, assessment.currency)} commitment
          </p>
        </div>
        <div className="flex gap-2">
          <VAButton onClick={handleCompute} disabled={computing} variant="secondary">
            {computing ? "Computing…" : "Run Compute"}
          </VAButton>
          {hasMetrics && (
            <VAButton onClick={handleMemo} disabled={generatingMemo}>
              {generatingMemo ? "Generating…" : "Generate Memo"}
            </VAButton>
          )}
        </div>
      </div>

      {computeError && <p className="text-red-400 text-sm">{computeError}</p>}

      {memo && (
        <VACard className="p-4 border border-va-blue/30 bg-va-panel">
          <h3 className="font-semibold text-va-text mb-1">{memo.title}</h3>
          <p className="text-sm text-va-text/80">{memo.recommendation}</p>
        </VACard>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <VACard className="p-5">
          <h2 className="text-sm font-semibold text-va-text/70 mb-3 uppercase tracking-wider">Fund Metrics</h2>
          <MetricsTable a={assessment} />
          {!hasMetrics && (
            <p className="text-xs text-va-text/40 mt-3">Metrics not yet computed. Click Run Compute to calculate DPI/TVPI/IRR.</p>
          )}
        </VACard>

        <VACard className="p-5 lg:col-span-2">
          <h2 className="text-sm font-semibold text-va-text/70 mb-3 uppercase tracking-wider">J-Curve</h2>
          <JCurveChart data={jCurveData} />
          {hasMetrics && (
            <p className="text-xs text-va-text/40 mt-2">
              Cumulative net return from LP perspective. Negative early periods reflect capital drawdowns before distributions.
            </p>
          )}
        </VACard>
      </div>

      {peerRank && (
        <VACard className="p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-va-text/70 uppercase tracking-wider">Peer Comparison</h2>
            {peerRank.fund_count && (
              <span className="text-xs text-va-text/50">{peerRank.fund_count} funds · {peerRank.strategy}</span>
            )}
          </div>
          {peerRank.warning ? (
            <p className="text-xs text-amber-400">{peerRank.warning}</p>
          ) : (
            <PeerRankings rankings={peerRank.rankings} dataSource={peerRank.data_source} />
          )}
        </VACard>
      )}

      {assessment.notes && (
        <VACard className="p-5">
          <h2 className="text-sm font-semibold text-va-text/70 mb-2 uppercase tracking-wider">Notes</h2>
          <p className="text-sm text-va-text/80">{assessment.notes}</p>
        </VACard>
      )}
    </div>
  );
}
