"use client";

import { api, API_URL, type BoardPackDetail } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { VAButton, VACard, VASpinner } from "@/components/ui";
import { Nav } from "@/components/nav";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

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
    const ctx = await getAuthContext();
    if (!ctx) { router.replace("/login"); return; }
    api.setAccessToken(ctx.accessToken);
    setTenantId(ctx.tenantId);
    setAccessToken(ctx.accessToken);
    try {
      const p = await api.boardPacks.get(ctx.tenantId, packId);
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
    try {
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
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = `${packId}.${ext}`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(objectUrl), 100);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Download failed");
    }
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
          <VASpinner label="Loading…" />
        ) : pack ? (
          <>
            <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
              {pack.label}
            </h1>
            <p className="mt-1 text-sm text-va-text2">
              {pack.run_id ?? "—"} · {pack.status}
            </p>
            <div className="mt-2">
              <Link
                href={`/board-packs/${packId}/builder`}
                className="text-sm text-va-blue hover:underline"
              >
                Edit report sections →
              </Link>
            </div>
            {pack.status === "draft" || pack.status === "error" ? (
              <VAButton
                type="button"
                variant="primary"
                onClick={handleGenerate}
                disabled={generating}
                className="mt-4"
              >
                {generating ? "Generating…" : "Generate narrative"}
              </VAButton>
            ) : null}
            {pack.status === "ready" && (
              <VACard className="mt-6 p-4">
                <h2 className="text-lg font-medium text-va-text">Export</h2>
                <div className="mt-2 flex flex-wrap gap-2">
                  <VAButton
                    type="button"
                    variant="secondary"
                    onClick={() => handleDownload("html")}
                  >
                    Download HTML
                  </VAButton>
                  <VAButton
                    type="button"
                    variant="secondary"
                    onClick={() => handleDownload("pdf")}
                  >
                    Download PDF
                  </VAButton>
                  <VAButton
                    type="button"
                    variant="secondary"
                    onClick={() => handleDownload("pptx")}
                  >
                    Download PPTX
                  </VAButton>
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
