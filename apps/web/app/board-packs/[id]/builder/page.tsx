"use client";

import { api, type BoardPackSummary } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { VAButton, VACard, VASpinner, useToast } from "@/components/ui";
import { Nav } from "@/components/nav";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

const ALL_SECTIONS = [
  "executive_summary",
  "income_statement",
  "balance_sheet",
  "cash_flow",
  "budget_variance",
  "kpi_dashboard",
  "scenario_comparison",
  "strategic_commentary",
  "benchmark",
] as const;

type SectionSlug = (typeof ALL_SECTIONS)[number];

const SECTION_LABELS: Record<SectionSlug, string> = {
  executive_summary: "Executive Summary",
  income_statement: "Income Statement",
  balance_sheet: "Balance Sheet",
  cash_flow: "Cash Flow Statement",
  budget_variance: "Budget Variance",
  kpi_dashboard: "KPI Dashboard",
  scenario_comparison: "Scenario Comparison",
  strategic_commentary: "Strategic Commentary",
  benchmark: "Benchmark Analysis",
};

const btnCls =
  "rounded px-1.5 py-0.5 text-xs text-va-text2 hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-1 focus-visible:ring-va-blue";

export default function BoardPackBuilderPage() {
  const params = useParams();
  const router = useRouter();
  const packId = params?.id as string;
  const { toast } = useToast();

  const [pack, setPack] = useState<BoardPackSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tenantId, setTenantId] = useState<string | null>(null);

  const [active, setActive] = useState<SectionSlug[]>([]);
  const [available, setAvailable] = useState<SectionSlug[]>([]);

  const load = useCallback(async () => {
    const ctx = await getAuthContext();
    if (!ctx) { router.replace("/login"); return; }
    api.setAccessToken(ctx.accessToken);
    setTenantId(ctx.tenantId);
    try {
      const p = await api.boardPacks.get(ctx.tenantId, packId);
      setPack(p);
      const current = (p.section_order ?? []).filter((s): s is SectionSlug =>
        (ALL_SECTIONS as readonly string[]).includes(s)
      );
      setActive(current);
      setAvailable(
        ALL_SECTIONS.filter((s) => !current.includes(s)) as SectionSlug[]
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [packId, router]);

  useEffect(() => {
    if (!packId) return;
    load();
  }, [packId, load]);

  function addSection(slug: SectionSlug) {
    setActive((prev) => [...prev, slug]);
    setAvailable((prev) => prev.filter((s) => s !== slug));
  }

  function removeSection(idx: number) {
    const slug = active[idx];
    setActive((prev) => prev.filter((_, i) => i !== idx));
    setAvailable((prev) =>
      [...prev, slug].sort(
        (a, b) =>
          ALL_SECTIONS.indexOf(a) - ALL_SECTIONS.indexOf(b)
      )
    );
  }

  function moveUp(idx: number) {
    if (idx === 0) return;
    setActive((prev) => {
      const next = [...prev];
      [next[idx - 1], next[idx]] = [next[idx], next[idx - 1]];
      return next;
    });
  }

  function moveDown(idx: number) {
    setActive((prev) => {
      if (idx >= prev.length - 1) return prev;
      const next = [...prev];
      [next[idx], next[idx + 1]] = [next[idx + 1], next[idx]];
      return next;
    });
  }

  async function handleSave() {
    if (!tenantId) return;
    setSaving(true);
    try {
      await api.boardPacks.update(tenantId, packId, { section_order: active });
      toast.success("Section order saved");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  if (!tenantId && !loading) return null;

  return (
    <div className="min-h-screen bg-va-midnight">
      <Nav />
      <main className="mx-auto max-w-5xl px-4 py-8">
        <div className="mb-6 flex items-center gap-4">
          <Link
            href={`/board-packs/${packId}`}
            className="text-sm text-va-blue hover:underline"
          >
            ← Back to board pack
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
        ) : (
          <>
            <div className="mb-6 flex items-center justify-between">
              <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
                Report Builder{pack ? ` — ${pack.label}` : ""}
              </h1>
              <VAButton
                type="button"
                variant="primary"
                onClick={handleSave}
                disabled={saving || active.length === 0}
              >
                {saving ? "Saving…" : "Save order"}
              </VAButton>
            </div>

            <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
              {/* Available sections */}
              <div>
                <h2 className="mb-3 text-sm font-medium text-va-text2 uppercase tracking-wide">
                  Available sections
                </h2>
                {available.length === 0 ? (
                  <p className="text-sm text-va-text2">
                    All sections are in the report.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {available.map((slug) => (
                      <VACard
                        key={slug}
                        className="flex items-center justify-between p-3"
                      >
                        <span className="text-sm text-va-text">
                          {SECTION_LABELS[slug]}
                        </span>
                        <button
                          type="button"
                          onClick={() => addSection(slug)}
                          className="rounded border border-va-border px-2 py-1 text-xs text-va-text2 hover:bg-white/10 focus:outline-none focus-visible:ring-1 focus-visible:ring-va-blue"
                        >
                          Add →
                        </button>
                      </VACard>
                    ))}
                  </div>
                )}
              </div>

              {/* Report order */}
              <div>
                <h2 className="mb-3 text-sm font-medium text-va-text2 uppercase tracking-wide">
                  Report order
                </h2>
                {active.length === 0 ? (
                  <p className="text-sm text-va-text2">
                    Add sections from the left panel to build your report.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {active.map((slug, idx) => (
                      <VACard
                        key={slug}
                        className="flex items-center gap-2 p-3"
                      >
                        <span className="w-5 text-xs text-va-muted">
                          {idx + 1}.
                        </span>
                        <span className="flex-1 text-sm text-va-text">
                          {SECTION_LABELS[slug]}
                        </span>
                        <button
                          type="button"
                          onClick={() => moveUp(idx)}
                          disabled={idx === 0}
                          className={btnCls}
                          aria-label="Move up"
                        >
                          ↑
                        </button>
                        <button
                          type="button"
                          onClick={() => moveDown(idx)}
                          disabled={idx === active.length - 1}
                          className={btnCls}
                          aria-label="Move down"
                        >
                          ↓
                        </button>
                        <button
                          type="button"
                          onClick={() => removeSection(idx)}
                          className={`${btnCls} text-va-danger hover:text-va-danger`}
                          aria-label="Remove section"
                        >
                          ✕
                        </button>
                      </VACard>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
