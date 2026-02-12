"use client";

import { api } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import { Nav } from "@/components/nav";
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
    <div className="min-h-screen bg-background">
      <Nav />
      <main className="mx-auto max-w-4xl px-4 py-8">
        <div className="mb-6 flex items-center gap-4">
          <Link
            href="/baselines"
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            ← Baselines
          </Link>
        </div>
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-semibold tracking-tight">
            Baseline {id}
          </h1>
          <button
            type="button"
            onClick={createRun}
            disabled={runCreating || !config}
            className="rounded-md bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {runCreating ? "Creating run…" : "Run model"}
          </button>
        </div>
        {error && (
          <div
            className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800"
            role="alert"
          >
            {error}
          </div>
        )}
        {loading ? (
          <p className="text-muted-foreground">Loading…</p>
        ) : config ? (
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="text-sm text-muted-foreground">
              Model config loaded. Use &quot;Run model&quot; to execute and view
              statements and KPIs.
            </p>
            <pre className="mt-3 max-h-96 overflow-auto rounded bg-muted/50 p-3 text-xs">
              {JSON.stringify(config, null, 2)}
            </pre>
          </div>
        ) : (
          <p className="text-muted-foreground">Baseline not found.</p>
        )}
      </main>
    </div>
  );
}
