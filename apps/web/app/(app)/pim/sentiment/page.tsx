"use client";

import { VABadge, VACard, VASpinner, VATabs, useToast } from "@/components/ui";
import {
  api,
  type PimSentimentCompanyDetail,
  type PimSentimentDashboardItem,
} from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { useCallback, useEffect, useState } from "react";

function sentimentColor(score: number | null): string {
  if (score === null) return "text-va-text2";
  if (score >= 0.3) return "text-emerald-400";
  if (score >= 0.05) return "text-emerald-300/80";
  if (score >= -0.05) return "text-va-text2";
  if (score >= -0.3) return "text-amber-400";
  return "text-red-400";
}

function sentimentLabel(score: number | null): string {
  if (score === null) return "N/A";
  if (score >= 0.3) return "Positive";
  if (score >= 0.05) return "Slightly +";
  if (score >= -0.05) return "Neutral";
  if (score >= -0.3) return "Slightly −";
  return "Negative";
}

function trendIcon(dir: string | null): string {
  if (dir === "up") return "↑";
  if (dir === "down") return "↓";
  return "→";
}

function trendColor(dir: string | null): string {
  if (dir === "up") return "text-emerald-400";
  if (dir === "down") return "text-red-400";
  return "text-va-text2";
}

export default function PimSentimentPage() {
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [items, setItems] = useState<PimSentimentDashboardItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCompany, setSelectedCompany] = useState<string | null>(null);
  const [detail, setDetail] = useState<PimSentimentCompanyDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [tab, setTab] = useState<"dashboard" | "detail">("dashboard");
  const { toast } = useToast();

  const loadDashboard = useCallback(async () => {
    if (!tenantId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.pim.sentiment.dashboard(tenantId);
      setItems(res.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  const loadDetail = useCallback(
    async (companyId: string) => {
      if (!tenantId) return;
      setDetailLoading(true);
      try {
        const res = await api.pim.sentiment.companyDetail(tenantId, companyId);
        setDetail(res);
        setTab("detail");
      } catch (e) {
        toast.error(e instanceof Error ? e.message : String(e));
      } finally {
        setDetailLoading(false);
      }
    },
    [tenantId, toast],
  );

  useEffect(() => {
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) return;
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);
    })();
  }, []);

  useEffect(() => {
    if (tenantId) loadDashboard();
  }, [tenantId, loadDashboard]);

  function handleCompanyClick(companyId: string) {
    setSelectedCompany(companyId);
    loadDetail(companyId);
  }

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-6">
        <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
          Sentiment Monitor
        </h1>
        <p className="mt-1 text-sm text-va-text2">
          Track news sentiment across your portfolio universe.
        </p>
      </div>

      {error && (
        <div
          className="mb-4 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger"
          role="alert"
        >
          {error}
        </div>
      )}

      <VATabs
        activeId={tab}
        onSelect={(v) => setTab(v as "dashboard" | "detail")}
        tabs={[
          {
            id: "dashboard",
            label: "Dashboard",
            content: loading ? (
              <VASpinner label="Loading sentiment data…" />
            ) : items.length === 0 ? (
              <VACard className="p-6 text-center">
                <p className="text-sm text-va-text2">
                  No companies in your universe yet. Add companies from the
                  Universe Manager to start tracking sentiment.
                </p>
              </VACard>
            ) : (
              <div className="overflow-x-auto rounded-va-lg border border-va-border">
                <table className="w-full text-sm text-va-text">
                  <thead>
                    <tr className="border-b border-va-border bg-va-surface">
                      <th className="px-3 py-2 text-left font-medium">
                        Company
                      </th>
                      <th className="px-3 py-2 text-left font-medium">
                        Ticker
                      </th>
                      <th className="px-3 py-2 text-left font-medium">
                        Sector
                      </th>
                      <th className="px-3 py-2 text-right font-medium">
                        Sentiment
                      </th>
                      <th className="px-3 py-2 text-center font-medium">
                        Trend
                      </th>
                      <th className="px-3 py-2 text-right font-medium">
                        Confidence
                      </th>
                      <th className="px-3 py-2 text-right font-medium">
                        Signals
                      </th>
                      <th className="px-3 py-2 text-left font-medium">
                        Latest Headline
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((item) => (
                      <tr
                        key={item.company_id}
                        className="cursor-pointer border-b border-va-border/50 transition-colors hover:bg-va-surface/50"
                        onClick={() => handleCompanyClick(item.company_id)}
                      >
                        <td className="px-3 py-2 font-medium">
                          {item.company_name}
                        </td>
                        <td className="px-3 py-2 font-mono text-xs text-va-text2">
                          {item.ticker}
                        </td>
                        <td className="px-3 py-2 text-va-text2">
                          {item.sector ?? "—"}
                        </td>
                        <td className="px-3 py-2 text-right">
                          <span
                            className={`font-medium ${sentimentColor(item.latest_avg_sentiment)}`}
                          >
                            {item.latest_avg_sentiment !== null
                              ? item.latest_avg_sentiment.toFixed(2)
                              : "—"}
                          </span>
                          <span className="ml-1 text-xs text-va-text2">
                            {sentimentLabel(item.latest_avg_sentiment)}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-center">
                          <span
                            className={`text-lg ${trendColor(item.trend_direction)}`}
                          >
                            {trendIcon(item.trend_direction)}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-right text-va-text2">
                          {item.latest_avg_confidence !== null
                            ? `${(item.latest_avg_confidence * 100).toFixed(0)}%`
                            : "—"}
                        </td>
                        <td className="px-3 py-2 text-right">
                          {item.total_signals}
                        </td>
                        <td
                          className="max-w-[200px] truncate px-3 py-2 text-va-text2"
                          title={item.latest_signal?.headline ?? ""}
                        >
                          {item.latest_signal?.headline ?? "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ),
          },
          {
            id: "detail",
            label: "Company Detail",
            content: detailLoading ? (
              <VASpinner label="Loading company detail…" />
            ) : detail ? (
              <div className="space-y-6">
                {/* Company header */}
                <VACard className="p-5">
                  <div className="flex items-center gap-3">
                    <h2 className="text-lg font-medium text-va-text">
                      {detail.company.company_name}
                    </h2>
                    <VABadge variant="outline">
                      {detail.company.ticker}
                    </VABadge>
                    {detail.company.sector && (
                      <span className="text-sm text-va-text2">
                        {detail.company.sector}
                        {detail.company.sub_sector
                          ? ` · ${detail.company.sub_sector}`
                          : ""}
                      </span>
                    )}
                  </div>
                </VACard>

                {/* Aggregates time-series */}
                <VACard className="p-5">
                  <h3 className="mb-3 text-sm font-medium text-va-text">
                    Sentiment Trend
                  </h3>
                  {detail.aggregates.length === 0 ? (
                    <p className="text-sm text-va-text2">
                      No aggregate data yet.
                    </p>
                  ) : (
                    <div className="overflow-x-auto rounded-va-lg border border-va-border">
                      <table className="w-full text-sm text-va-text">
                        <thead>
                          <tr className="border-b border-va-border bg-va-surface">
                            <th className="px-3 py-2 text-left font-medium">
                              Period
                            </th>
                            <th className="px-3 py-2 text-right font-medium">
                              Avg
                            </th>
                            <th className="px-3 py-2 text-right font-medium">
                              Median
                            </th>
                            <th className="px-3 py-2 text-right font-medium">
                              Min
                            </th>
                            <th className="px-3 py-2 text-right font-medium">
                              Max
                            </th>
                            <th className="px-3 py-2 text-right font-medium">
                              Signals
                            </th>
                            <th className="px-3 py-2 text-center font-medium">
                              Trend
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {detail.aggregates.map((agg, i) => (
                            <tr
                              key={i}
                              className="border-b border-va-border/50"
                            >
                              <td className="px-3 py-2 text-va-text2">
                                {agg.period_start ?? "—"}
                              </td>
                              <td
                                className={`px-3 py-2 text-right font-medium ${sentimentColor(agg.avg_sentiment)}`}
                              >
                                {agg.avg_sentiment.toFixed(3)}
                              </td>
                              <td className="px-3 py-2 text-right text-va-text2">
                                {agg.median_sentiment?.toFixed(3) ?? "—"}
                              </td>
                              <td className="px-3 py-2 text-right text-va-text2">
                                {agg.min_sentiment?.toFixed(3) ?? "—"}
                              </td>
                              <td className="px-3 py-2 text-right text-va-text2">
                                {agg.max_sentiment?.toFixed(3) ?? "—"}
                              </td>
                              <td className="px-3 py-2 text-right">
                                {agg.signal_count}
                              </td>
                              <td className="px-3 py-2 text-center">
                                <span
                                  className={trendColor(agg.trend_direction)}
                                >
                                  {trendIcon(agg.trend_direction)}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </VACard>

                {/* Recent signals */}
                <VACard className="p-5">
                  <h3 className="mb-3 text-sm font-medium text-va-text">
                    Recent Signals
                  </h3>
                  {detail.recent_signals.length === 0 ? (
                    <p className="text-sm text-va-text2">
                      No signals ingested yet.
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {detail.recent_signals.map((sig) => (
                        <div
                          key={sig.signal_id}
                          className="flex items-start gap-3 rounded-va-sm border border-va-border/50 bg-va-surface/30 px-3 py-2"
                        >
                          <span
                            className={`mt-0.5 text-sm font-medium ${sentimentColor(sig.sentiment_score)}`}
                          >
                            {sig.sentiment_score.toFixed(2)}
                          </span>
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm text-va-text">
                              {sig.headline ?? "No headline"}
                            </p>
                            <p className="text-xs text-va-text2">
                              {sig.source_type}
                              {sig.published_at
                                ? ` · ${new Date(sig.published_at).toLocaleDateString()}`
                                : ""}
                              {` · ${(sig.confidence * 100).toFixed(0)}% confidence`}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </VACard>
              </div>
            ) : (
              <p className="text-sm text-va-text2">
                Select a company from the dashboard to view details.
              </p>
            ),
          },
        ]}
      />
    </main>
  );
}
