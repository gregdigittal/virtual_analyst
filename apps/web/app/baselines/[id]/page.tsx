"use client";

import { api } from "@/lib/api";
import { VAButton, VACard, VASpinner } from "@/components/ui";
import { createClient } from "@/lib/supabase/client";
import { Nav } from "@/components/nav";
import { EntityTimeline } from "@/components/EntityTimeline";
import { CommentThread } from "@/components/CommentThread";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export default function BaselineDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const [config, setConfig] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [runCreating, setRunCreating] = useState(false);

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
      setUserId(session.user.id);
      try {
        const res = await api.baselines.get(tid, id);
        if (!cancelled) setConfig(res.model_config);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  async function createRun() {
    if (!tenantId) return;
    setRunCreating(true);
    try {
      const res = await api.runs.create(tenantId, id);
      router.push(`/runs/${res.run_id}`);
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunCreating(false);
    }
  }

  if (!tenantId && !loading) return null;

  return (
    <div className="min-h-screen bg-va-midnight">
      <Nav />
      <main className="mx-auto max-w-4xl px-4 py-8">
        <div className="mb-6 flex items-center gap-4">
          <Link
            href="/baselines"
            className="text-sm text-va-text2 hover:text-va-text focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded"
          >
            ← Baselines
          </Link>
        </div>
        <div className="mb-6 flex items-center justify-between">
          <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
            Baseline {id}
          </h1>
          <VAButton
            type="button"
            variant="primary"
            onClick={createRun}
            disabled={runCreating || !config}
          >
            {runCreating ? "Creating run…" : "Run model"}
          </VAButton>
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
          <VASpinner label="Loading…" />
        ) : config ? (
          <VACard className="p-4">
            <p className="text-sm text-va-text2">
              Model config loaded. Use &quot;Run model&quot; to execute and view
              statements and KPIs.
            </p>
            <pre className="mt-3 max-h-96 overflow-auto rounded-va-xs bg-va-surface p-3 font-mono text-xs text-va-text2">
              {JSON.stringify(config, null, 2)}
            </pre>
          </VACard>
        ) : (
          <p className="text-va-text2">Baseline not found.</p>
        )}

        {tenantId && !loading && (
          <div className="mt-8 grid gap-6 lg:grid-cols-2">
            <VACard className="p-4">
              <h2 className="mb-3 font-brand text-lg font-medium text-va-text">
                History
              </h2>
              <EntityTimeline
                tenantId={tenantId}
                resourceType="baseline"
                resourceId={id}
              />
            </VACard>
            <VACard className="p-4">
              <h2 className="mb-3 font-brand text-lg font-medium text-va-text">
                Comments
              </h2>
              {userId && (
                <CommentThread
                  tenantId={tenantId}
                  userId={userId}
                  entityType="baseline"
                  entityId={id}
                />
              )}
            </VACard>
          </div>
        )}
      </main>
    </div>
  );
}
