"use client";

import { api, type BoardPackDetail } from "@/lib/api";
import { VACard } from "@/components/ui";
import { createClient } from "@/lib/supabase/client";
import { Nav } from "@/components/nav";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function BoardPackDetailPage() {
  const params = useParams();
  const router = useRouter();
  const packId = params?.id as string;
  const [pack, setPack] = useState<BoardPackDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);

  const load = useCallback(async () => {
    const supabase = createClient();
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (!session?.user?.id) {
      router.replace("/login");
      return;
    }
    const tid = session.user.user_metadata?.tenant_id ?? session.user.id;
    setTenantId(tid);
    setAccessToken(session.access_token ?? null);
    try {
      const p = await api.boardPacks.get(tid, packId);
      setPack(p);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setPack(null);
    } finally {
      setLoading(false);
    }
  }, [packId, router]);

  useEffect(() => {
    if (!packId) return;
    load();
  }, [packId, load]);

  async function handleGenerate() {
    if (!tenantId || !packId) return;
    setGenerating(true);
    setError(null);
    try {
      await api.boardPacks.generate(tenantId, packId);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setGenerating(false);
    }
  }

  async function handleDownload(format: "html" | "pdf" | "pptx") {
    if (!tenantId || !accessToken) return;
    const url = `${API_URL}/api/v1/board-packs/${encodeURIComponent(packId)}/export?format=${format}`;
    const res = await fetch(url, {
      headers: {
        "X-Tenant-ID": tenantId,
        Authorization: `Bearer ${accessToken}`,
      },
    });
    if (!res.ok) {
      setError(`Download failed: ${res.status}`);
      return;
    }
    const blob = await res.blob();
    const ext = format === "pptx" ? "pptx" : format;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${packId}.${ext}`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  if (!tenantId && !loading) return null;

  return (
    <div className="min-h-screen bg-va-midnight">
      <Nav />
      <main className="mx-auto max-w-4xl px-4 py-8">
        <div className="mb-6 flex items-center gap-4">
          <Link
            href="/board-packs"
            className="text-sm text-va-blue hover:underline"
          >
            ← Board packs
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
          <p className="text-va-text2">Loading…</p>
        ) : pack ? (
          <>
            <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
              {pack.label}
            </h1>
            <p className="mt-1 text-sm text-va-text2">
              {pack.run_id ?? "—"} · {pack.status}
            </p>
            {pack.status === "draft" || pack.status === "error" ? (
              <button
                type="button"
                onClick={handleGenerate}
                disabled={generating}
                className="mt-4 rounded-va-lg bg-va-blue px-4 py-2 text-sm font-medium text-white hover:bg-va-blue/90 disabled:opacity-50"
              >
                {generating ? "Generating…" : "Generate narrative"}
              </button>
            ) : null}
            {pack.status === "ready" && (
              <VACard className="mt-6 p-4">
                <h2 className="text-lg font-medium text-va-text">Export</h2>
                <div className="mt-2 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => handleDownload("html")}
                    className="rounded-va-lg border border-va-border bg-va-panel px-3 py-2 text-sm text-va-text hover:bg-white/5"
                  >
                    Download HTML
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDownload("pdf")}
                    className="rounded-va-lg border border-va-border bg-va-panel px-3 py-2 text-sm text-va-text hover:bg-white/5"
                  >
                    Download PDF
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDownload("pptx")}
                    className="rounded-va-lg border border-va-border bg-va-panel px-3 py-2 text-sm text-va-text hover:bg-white/5"
                  >
                    Download PPTX
                  </button>
                </div>
              </VACard>
            )}
            {pack.narrative_json?.executive_summary && (
              <VACard className="mt-6 p-4">
                <h2 className="text-lg font-medium text-va-text">Executive summary</h2>
                <p className="mt-2 whitespace-pre-wrap text-sm text-va-text2">
                  {String(pack.narrative_json.executive_summary)}
                </p>
              </VACard>
            )}
            {pack.narrative_json?.strategic_commentary && (
              <VACard className="mt-4 p-4">
                <h2 className="text-lg font-medium text-va-text">Strategic commentary</h2>
                <p className="mt-2 whitespace-pre-wrap text-sm text-va-text2">
                  {String(pack.narrative_json.strategic_commentary)}
                </p>
              </VACard>
            )}
            {pack.error_message && (
              <p className="mt-2 text-sm text-va-danger">{pack.error_message}</p>
            )}
          </>
        ) : (
          <p className="text-va-text2">Board pack not found.</p>
        )}
      </main>
    </div>
  );
}
