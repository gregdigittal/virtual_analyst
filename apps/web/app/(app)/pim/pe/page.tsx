"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, PeAssessment, PeAssessmentsResponse, CreatePeAssessmentBody } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { VAButton } from "@/components/ui/VAButton";
import { VACard } from "@/components/ui/VACard";
import { VASpinner } from "@/components/ui/VASpinner";
import { VAPagination } from "@/components/ui/VAPagination";
import { VAInput } from "@/components/ui/VAInput";

const PAGE_SIZE = 20;

function formatPct(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

function formatMultiple(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${v.toFixed(2)}x`;
}

function formatCurrency(v: number | null | undefined, currency = "USD"): string {
  if (v == null) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency, maximumFractionDigits: 0 }).format(v);
}

interface CreateFormState {
  fund_name: string;
  vintage_year: string;
  commitment_usd: string;
  currency: string;
  notes: string;
}

const EMPTY_FORM: CreateFormState = {
  fund_name: "",
  vintage_year: String(new Date().getFullYear()),
  commitment_usd: "",
  currency: "USD",
  notes: "",
};

export default function PimPeListPage() {
  const router = useRouter();
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [data, setData] = useState<PeAssessmentsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<CreateFormState>(EMPTY_FORM);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

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
    api.pim.pe.list(tenantId, { limit: PAGE_SIZE, offset })
      .then(setData)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [tenantId, offset]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!tenantId) return;
    setCreating(true);
    setCreateError(null);
    try {
      const body: CreatePeAssessmentBody = {
        fund_name: form.fund_name,
        vintage_year: parseInt(form.vintage_year, 10),
        commitment_usd: parseFloat(form.commitment_usd),
        currency: form.currency,
        notes: form.notes || undefined,
      };
      const created = await api.pim.pe.create(tenantId, body);
      setShowCreate(false);
      setForm(EMPTY_FORM);
      router.push(`/pim/pe/${created.assessment_id}`);
    } catch (e) {
      setCreateError(String(e));
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-sora font-semibold text-va-text">PE Fund Assessments</h1>
          <p className="text-sm text-va-text/60 mt-1">DPI · TVPI · IRR · J-curve analysis per fund</p>
        </div>
        <VAButton onClick={() => setShowCreate(true)}>+ New Assessment</VAButton>
      </div>

      {showCreate && (
        <VACard className="p-6 border border-va-blue/30 bg-va-panel">
          <h2 className="text-lg font-sora font-semibold text-va-text mb-4">New PE Fund Assessment</h2>
          <form onSubmit={handleCreate} className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="block text-xs text-va-text/60 mb-1">Fund Name *</label>
              <VAInput
                value={form.fund_name}
                onChange={(e) => setForm((f) => ({ ...f, fund_name: e.target.value }))}
                placeholder="Acme Ventures III"
                required
              />
            </div>
            <div>
              <label className="block text-xs text-va-text/60 mb-1">Vintage Year *</label>
              <VAInput
                type="number"
                value={form.vintage_year}
                onChange={(e) => setForm((f) => ({ ...f, vintage_year: e.target.value }))}
                placeholder="2020"
                required
              />
            </div>
            <div>
              <label className="block text-xs text-va-text/60 mb-1">Commitment (USD) *</label>
              <VAInput
                type="number"
                value={form.commitment_usd}
                onChange={(e) => setForm((f) => ({ ...f, commitment_usd: e.target.value }))}
                placeholder="5000000"
                required
              />
            </div>
            <div>
              <label className="block text-xs text-va-text/60 mb-1">Currency</label>
              <VAInput
                value={form.currency}
                onChange={(e) => setForm((f) => ({ ...f, currency: e.target.value.toUpperCase() }))}
                placeholder="USD"
                maxLength={3}
              />
            </div>
            <div>
              <label className="block text-xs text-va-text/60 mb-1">Notes</label>
              <VAInput
                value={form.notes}
                onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
                placeholder="Optional notes"
              />
            </div>
            {createError && (
              <div className="col-span-2 text-red-400 text-sm">{createError}</div>
            )}
            <div className="col-span-2 flex gap-3">
              <VAButton type="submit" disabled={creating}>
                {creating ? "Creating…" : "Create Assessment"}
              </VAButton>
              <VAButton variant="secondary" type="button" onClick={() => { setShowCreate(false); setForm(EMPTY_FORM); }}>
                Cancel
              </VAButton>
            </div>
          </form>
        </VACard>
      )}

      {loading && (
        <div className="flex justify-center py-12">
          <VASpinner />
        </div>
      )}
      {error && <p className="text-red-400 text-sm">{error}</p>}

      {!loading && data && data.items.length === 0 && (
        <VACard className="p-8 text-center">
          <p className="text-va-text/50">No PE fund assessments yet. Create your first assessment to get started.</p>
        </VACard>
      )}

      {!loading && data && data.items.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-va-border">
          <table className="w-full text-sm">
            <thead className="bg-va-panel border-b border-va-border">
              <tr>
                <th className="px-4 py-3 text-left text-va-text/70 font-medium">Fund</th>
                <th className="px-4 py-3 text-right text-va-text/70 font-medium">Vintage</th>
                <th className="px-4 py-3 text-right text-va-text/70 font-medium">Commitment</th>
                <th className="px-4 py-3 text-right text-va-text/70 font-medium">DPI</th>
                <th className="px-4 py-3 text-right text-va-text/70 font-medium">TVPI</th>
                <th className="px-4 py-3 text-right text-va-text/70 font-medium">IRR</th>
                <th className="px-4 py-3 text-right text-va-text/70 font-medium"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-va-border">
              {data.items.map((a: PeAssessment) => (
                <tr key={a.assessment_id} className="hover:bg-va-panel/50 transition-colors">
                  <td className="px-4 py-3 font-medium text-va-text">{a.fund_name}</td>
                  <td className="px-4 py-3 text-right text-va-text/80 font-mono">{a.vintage_year}</td>
                  <td className="px-4 py-3 text-right text-va-text/80 font-mono">{formatCurrency(a.commitment_usd, a.currency)}</td>
                  <td className="px-4 py-3 text-right font-mono">
                    <span className={a.dpi != null && a.dpi >= 1 ? "text-green-400" : "text-va-text/80"}>
                      {formatMultiple(a.dpi)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right font-mono">
                    <span className={a.tvpi != null && a.tvpi >= 1 ? "text-green-400" : "text-va-text/80"}>
                      {formatMultiple(a.tvpi)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-va-text/80">{formatPct(a.irr)}</td>
                  <td className="px-4 py-3 text-right">
                    <Link href={`/pim/pe/${a.assessment_id}`} className="text-va-blue hover:underline text-xs">
                      View →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && data.total > PAGE_SIZE && (
        <VAPagination
          page={Math.floor(offset / PAGE_SIZE) + 1}
          pageSize={PAGE_SIZE}
          total={data.total}
          onPageChange={(p) => setOffset((p - 1) * PAGE_SIZE)}
        />
      )}
    </div>
  );
}
