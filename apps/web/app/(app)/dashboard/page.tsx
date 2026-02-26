"use client";

import { api, type MetricsSummary, type RunSummary, type AssignmentItem, type NotificationItem, type ActivityItem } from "@/lib/api";
import { VACard, VASpinner } from "@/components/ui";
import { getAuthContext } from "@/lib/auth";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export default function DashboardPage() {
  const router = useRouter();
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [summary, setSummary] = useState<MetricsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [recentRuns, setRecentRuns] = useState<RunSummary[]>([]);
  const [pendingAssignments, setPendingAssignments] = useState<AssignmentItem[]>([]);
  const [unreadNotifications, setUnreadNotifications] = useState<NotificationItem[]>([]);
  const [recentActivity, setRecentActivity] = useState<ActivityItem[]>([]);

  useEffect(() => {
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) { router.replace("/login"); return; }
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);

      const [metricsRes, runsRes, assignmentsRes, notifRes, activityRes] = await Promise.allSettled([
        api.metrics.getSummary(ctx.tenantId),
        api.runs.list(ctx.tenantId, { limit: 5 }),
        api.assignments.list(ctx.tenantId, { assignee_user_id: ctx.userId, status: "open", limit: 5 }, ctx.userId),
        api.notifications.list(ctx.tenantId, ctx.userId, true, 5, 0),
        api.activity.list(ctx.tenantId, { limit: 10 }),
      ]);

      if (metricsRes.status === "fulfilled") setSummary(metricsRes.value);
      if (runsRes.status === "fulfilled") setRecentRuns(runsRes.value.items ?? []);
      if (assignmentsRes.status === "fulfilled") setPendingAssignments(assignmentsRes.value.assignments ?? []);
      if (notifRes.status === "fulfilled") setUnreadNotifications(notifRes.value.items ?? []);
      if (activityRes.status === "fulfilled") setRecentActivity(activityRes.value.items ?? []);
      setLoading(false);
    })();
  }, [router]);

  if (!tenantId && !loading) return null;

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="font-brand mb-6 text-2xl font-semibold tracking-tight text-va-text">
        Dashboard
      </h1>

      {loading ? (
        <VASpinner label="Loading dashboard…" />
      ) : (
        <div className="space-y-6">
          {/* Summary cards */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <VACard className="p-4">
              <p className="text-sm text-va-text2">Recent runs</p>
              <p className="font-mono text-2xl font-semibold text-va-text">{recentRuns.length}</p>
              <Link href="/runs" className="text-xs text-va-blue hover:underline">View all →</Link>
            </VACard>
            <VACard className="p-4">
              <p className="text-sm text-va-text2">Pending tasks</p>
              <p className="font-mono text-2xl font-semibold text-va-text">{pendingAssignments.length}</p>
              <Link href="/inbox" className="text-xs text-va-blue hover:underline">View inbox →</Link>
            </VACard>
            <VACard className="p-4">
              <p className="text-sm text-va-text2">Unread notifications</p>
              <p className="font-mono text-2xl font-semibold text-va-text">{unreadNotifications.length}</p>
              <Link href="/notifications" className="text-xs text-va-blue hover:underline">View all →</Link>
            </VACard>
            {summary && (
              <VACard className="p-4">
                <p className="text-sm text-va-text2">API latency (P50)</p>
                <p className="font-mono text-2xl font-semibold text-va-text">{summary.latency_p50_ms.toFixed(0)} ms</p>
                <p className="text-xs text-va-text2">P95: {summary.latency_p95_ms.toFixed(0)} ms</p>
              </VACard>
            )}
          </div>

          {/* Recent runs + Pending assignments */}
          <div className="grid gap-6 lg:grid-cols-2">
            <VACard className="p-4">
              <h2 className="mb-3 text-sm font-medium text-va-text">Recent runs</h2>
              {recentRuns.length === 0 ? (
                <p className="text-sm text-va-text2">No runs yet.</p>
              ) : (
                <ul className="space-y-2">
                  {recentRuns.map((r) => (
                    <li key={r.run_id} className="flex items-center justify-between text-sm">
                      <Link href={`/runs/${r.run_id}`} className="truncate text-va-blue hover:underline">
                        {r.run_id}
                      </Link>
                      <span className={`rounded-full px-2 py-0.5 text-xs ${
                        r.status === "completed" ? "bg-green-900/40 text-green-300" :
                        r.status === "failed" ? "bg-red-900/40 text-red-300" :
                        "bg-yellow-900/40 text-yellow-300"
                      }`}>
                        {r.status}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </VACard>

            <VACard className="p-4">
              <h2 className="mb-3 text-sm font-medium text-va-text">My pending tasks</h2>
              {pendingAssignments.length === 0 ? (
                <p className="text-sm text-va-text2">No pending tasks.</p>
              ) : (
                <ul className="space-y-2">
                  {pendingAssignments.map((a) => (
                    <li key={a.assignment_id} className="flex items-center justify-between text-sm">
                      <span className="truncate text-va-text">
                        {a.entity_type}: {a.entity_id}
                      </span>
                      <span className="text-xs text-va-text2">{a.status}</span>
                    </li>
                  ))}
                </ul>
              )}
            </VACard>
          </div>

          {/* Recent activity */}
          <VACard className="p-4">
            <h2 className="mb-3 text-sm font-medium text-va-text">Recent activity</h2>
            {recentActivity.length === 0 ? (
              <p className="text-sm text-va-text2">No recent activity.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {recentActivity.map((a) => (
                  <li key={a.id} className="flex items-baseline gap-3 border-b border-va-border/30 pb-2">
                    <span className="shrink-0 text-xs text-va-text2">
                      {a.timestamp ? new Date(a.timestamp).toLocaleDateString() : "—"}
                    </span>
                    <span className="text-va-text">
                      {a.event_type?.replace(/_/g, " ") ?? a.summary}
                      {a.resource_type ? ` on ${a.resource_type} ${a.resource_id ?? ""}` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </VACard>

          {/* Performance metrics (collapsed) */}
          {summary && (
            <details>
              <summary className="cursor-pointer text-sm font-medium text-va-text2 hover:text-va-text">
                API performance metrics
              </summary>
              <div className="mt-3 space-y-4">
                <div className="grid gap-4 sm:grid-cols-3">
                  <VACard className="p-4">
                    <p className="text-sm text-va-text2">Request count</p>
                    <p className="font-mono text-2xl font-semibold text-va-text">{summary.request_count}</p>
                    <p className="text-xs text-va-text2">Last 1,000 requests</p>
                  </VACard>
                  <VACard className="p-4">
                    <p className="text-sm text-va-text2">Latency P50</p>
                    <p className="font-mono text-2xl font-semibold text-va-text">{summary.latency_p50_ms.toFixed(1)} ms</p>
                  </VACard>
                  <VACard className="p-4">
                    <p className="text-sm text-va-text2">Latency P95</p>
                    <p className="font-mono text-2xl font-semibold text-va-text">{summary.latency_p95_ms.toFixed(1)} ms</p>
                  </VACard>
                </div>
                {Object.keys(summary.by_endpoint).length > 0 && (
                  <VACard className="p-4">
                    <h2 className="mb-3 text-sm font-medium text-va-text">Latency by endpoint (avg ms)</h2>
                    <ul className="space-y-1 text-sm">
                      {Object.entries(summary.by_endpoint)
                        .sort(([, a], [, b]) => b - a)
                        .map(([path, avg]) => (
                          <li key={path} className="flex justify-between gap-4 text-va-text">
                            <span className="truncate font-mono text-va-text2">{path}</span>
                            <span className="font-mono">{avg.toFixed(1)}</span>
                          </li>
                        ))}
                    </ul>
                  </VACard>
                )}
              </div>
            </details>
          )}
        </div>
      )}
    </main>
  );
}
