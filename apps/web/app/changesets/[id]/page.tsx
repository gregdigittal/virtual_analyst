"use client";

import { api } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { VAButton, VACard, VASpinner, useToast } from "@/components/ui";
import { Nav } from "@/components/nav";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

interface ChangesetDetail {
  changeset_id: string;
  baseline_id: string;
  base_version: string;
  status: string;
  label?: string;
  created_at: string | null;
  overrides: { path: string; value: unknown }[];
}

interface TestResult {
  time_series: Record<string, number[]>;
  applied_overrides: number;
}

export default function ChangesetDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const changesetId = params.id as string;

  const [tenantId, setTenantId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [changeset, setChangeset] = useState<ChangesetDetail | null>(null);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(false);
  const [merging, setMerging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadChangeset = useCallback(async () => {
    if (!tenantId) return;
    try {
      const res = await api.changesets.get(tenantId, changesetId);
      setChangeset(res as unknown as ChangesetDetail);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [tenantId, changesetId]);

  useEffect(() => {
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) {
        router.replace("/login");
        return;
      }
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);
      setUserId(ctx.userId);
    })();
  }, [router]);

  useEffect(() => {
    if (tenantId) loadChangeset();
  }, [tenantId, loadChangeset]);

  async function handleTest() {
    if (!tenantId) return;
    setTesting(true);
    setError(null);
    try {
      const res = await api.changesets.test(tenantId, changesetId);
      setTestResult(res);
      toast.success(
        `Dry-run complete \u2014 ${res.applied_overrides} override(s) applied`
      );
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(msg);
    } finally {
      setTesting(false);
    }
  }

  async function handleMerge() {
    if (!tenantId) return;
    setMerging(true);
    setError(null);
    try {
      const res = await api.changesets.merge(
        tenantId,
        userId ?? undefined,
        changesetId
      );
      toast.success(`Merged! New baseline version: ${res.new_version}`);
      loadChangeset();
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(msg);
    } finally {
      setMerging(false);
    }
  }

  if (!tenantId && !loading) return null;

  const tsEntries = testResult
    ? Object.entries(testResult.time_series)
    : [];
  const periodCount = tsEntries.length > 0 ? tsEntries[0][1].length : 0;

  return (
    <div className="min-h-screen bg-va-midnight">
      <Nav />
      <main className="mx-auto max-w-4xl px-4 py-8">
        <div className="mb-6 flex items-center gap-4">
          <Link
            href="/changesets"
            className="text-sm text-va-text2 hover:text-va-text focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded"
          >
            \u2190 Changesets
          </Link>
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
          <VASpinner label="Loading changeset..." />
        ) : changeset ? (
          <>
            <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
              <div>
                <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
                  Changeset {changeset.changeset_id}
                </h1>
                {changeset.label && (
                  <p className="mt-1 text-sm text-va-text2">
                    {changeset.label}
                  </p>
                )}
                <p className="mt-1 text-sm text-va-text2">
                  Baseline: {changeset.baseline_id} ({changeset.base_version})
                  {" \u00b7 "}
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs ${
                      changeset.status === "merged"
                        ? "bg-green-900/40 text-green-300"
                        : changeset.status === "draft"
                          ? "bg-yellow-900/40 text-yellow-300"
                          : "bg-va-surface text-va-text2"
                    }`}
                  >
                    {changeset.status}
                  </span>
                </p>
              </div>
              {changeset.status !== "merged" && (
                <div className="flex gap-2">
                  <VAButton
                    type="button"
                    variant="secondary"
                    onClick={handleTest}
                    disabled={testing}
                  >
                    {testing ? "Testing..." : "Test (dry-run)"}
                  </VAButton>
                  <VAButton
                    type="button"
                    variant="primary"
                    onClick={handleMerge}
                    disabled={merging}
                  >
                    {merging ? "Merging..." : "Merge to baseline"}
                  </VAButton>
                </div>
              )}
            </div>

            {/* Overrides */}
            <VACard className="mb-6 p-4">
              <h2 className="mb-3 text-sm font-medium text-va-text">
                Overrides ({changeset.overrides.length})
              </h2>
              {changeset.overrides.length === 0 ? (
                <p className="text-sm text-va-text2">No overrides defined.</p>
              ) : (
                <div className="overflow-x-auto rounded-va-lg border border-va-border">
                  <table className="w-full text-sm text-va-text">
                    <thead>
                      <tr className="border-b border-va-border bg-va-surface">
                        <th className="px-3 py-2 text-left font-medium">
                          Path
                        </th>
                        <th className="px-3 py-2 text-left font-medium">
                          Value
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {changeset.overrides.map((o, i) => (
                        <tr
                          key={i}
                          className="border-b border-va-border/50"
                        >
                          <td className="px-3 py-2 font-mono text-va-text2">
                            {o.path}
                          </td>
                          <td className="px-3 py-2 font-mono">
                            {JSON.stringify(o.value)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </VACard>

            {/* Test results */}
            {testResult && (
              <VACard className="p-4">
                <h2 className="mb-3 text-sm font-medium text-va-text">
                  Dry-run results ({testResult.applied_overrides} override(s)
                  applied)
                </h2>
                {tsEntries.length === 0 ? (
                  <p className="text-sm text-va-text2">
                    No time series output.
                  </p>
                ) : (
                  <div className="overflow-x-auto rounded-va-lg border border-va-border">
                    <table className="w-full min-w-[600px] text-sm text-va-text">
                      <thead>
                        <tr className="border-b border-va-border bg-va-surface">
                          <th className="px-3 py-2 text-left font-medium">
                            Metric
                          </th>
                          {Array.from({ length: periodCount }, (_, i) => (
                            <th
                              key={i}
                              className="px-3 py-2 text-right font-medium font-mono"
                            >
                              {`P${i}`}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {tsEntries.map(([metric, values]) => (
                          <tr
                            key={metric}
                            className="border-b border-va-border/50"
                          >
                            <td className="px-3 py-2 capitalize font-medium">
                              {metric.replace(/_/g, " ")}
                            </td>
                            {values.map((v, j) => (
                              <td
                                key={j}
                                className={`px-3 py-2 text-right font-mono ${
                                  v < 0 ? "text-va-danger" : ""
                                }`}
                              >
                                {v.toLocaleString(undefined, {
                                  maximumFractionDigits: 0,
                                })}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </VACard>
            )}
          </>
        ) : (
          <p className="text-va-text2">Changeset not found.</p>
        )}
      </main>
    </div>
  );
}
