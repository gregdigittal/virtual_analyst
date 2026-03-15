"use client";

import { VABadge, VAButton, VACard, VAInput, VASpinner, useToast } from "@/components/ui";
import { api, type PimUniverseCompany } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { useCallback, useEffect, useMemo, useState } from "react";

type CompanyForm = {
  ticker: string;
  company_name: string;
  sector: string;
  country_iso: string;
  exchange: string;
};

const EMPTY_FORM: CompanyForm = {
  ticker: "",
  company_name: "",
  sector: "",
  country_iso: "",
  exchange: "",
};

const LIMIT = 200; // load all for sector grouping

/** Data quality score [0–3]: count of non-null optional fields (sector, country, exchange, market_cap). */
function dataQualityScore(c: PimUniverseCompany): number {
  return [c.sector, c.country_iso, c.exchange, c.market_cap_usd].filter(Boolean).length;
}

function DataQualityBadge({ company }: { company: PimUniverseCompany }) {
  const score = dataQualityScore(company);
  if (score >= 3) return <VABadge variant="success">Complete</VABadge>;
  if (score >= 1) return <VABadge variant="warning">Partial</VABadge>;
  return <VABadge variant="default">Minimal</VABadge>;
}

export default function UniverseManagerPage() {
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [companies, setCompanies] = useState<PimUniverseCompany[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<CompanyForm>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [sectorFilter, setSectorFilter] = useState<string>("all");
  const [groupBySector, setGroupBySector] = useState(false);
  const { toast } = useToast();

  const loadCompanies = useCallback(async (tid: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.pim.universe.list(tid, { limit: LIMIT, offset: 0 });
      setCompanies(res.items);
      setTotal(res.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) return;
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);
    })();
  }, []);

  useEffect(() => {
    if (tenantId) loadCompanies(tenantId);
  }, [tenantId, loadCompanies]);

  function handleFormChange(f: keyof CompanyForm, value: string) {
    setForm((prev) => ({ ...prev, [f]: value }));
  }

  async function handleAddCompany(e: React.FormEvent) {
    e.preventDefault();
    if (!tenantId) return;
    setSubmitting(true);
    try {
      await api.pim.universe.add(tenantId, {
        ticker: form.ticker.toUpperCase(),
        company_name: form.company_name,
        ...(form.sector && { sector: form.sector }),
        ...(form.country_iso && { country_iso: form.country_iso.toUpperCase() }),
        ...(form.exchange && { exchange: form.exchange }),
      });
      toast.success(`${form.ticker.toUpperCase()} added to universe.`);
      setForm(EMPTY_FORM);
      setShowForm(false);
      if (tenantId) await loadCompanies(tenantId);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleToggleActive(company: PimUniverseCompany) {
    if (!tenantId) return;
    setActionLoading(company.company_id);
    try {
      await api.pim.universe.update(tenantId, company.company_id, {
        is_active: !company.is_active,
      });
      toast.success(`${company.ticker} ${company.is_active ? "deactivated" : "activated"}.`);
      setCompanies((prev) =>
        prev.map((c) =>
          c.company_id === company.company_id ? { ...c, is_active: !c.is_active } : c,
        ),
      );
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e));
    } finally {
      setActionLoading(null);
    }
  }

  async function handleRemove(company: PimUniverseCompany) {
    if (!tenantId) return;
    if (
      !window.confirm(
        `Remove ${company.ticker} (${company.company_name}) from the universe? This cannot be undone.`,
      )
    )
      return;
    setActionLoading(company.company_id);
    try {
      await api.pim.universe.remove(tenantId, company.company_id);
      toast.success(`${company.ticker} removed from universe.`);
      setCompanies((prev) => prev.filter((c) => c.company_id !== company.company_id));
      setTotal((prev) => prev - 1);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e));
    } finally {
      setActionLoading(null);
    }
  }

  // Derived data for sector grouping / filtering
  const sectors = useMemo(() => {
    const s = new Set(companies.map((c) => c.sector ?? "Unclassified"));
    return ["all", ...Array.from(s).sort()];
  }, [companies]);

  const filtered = useMemo(() => {
    if (sectorFilter === "all") return companies;
    const target = sectorFilter === "Unclassified" ? null : sectorFilter;
    return companies.filter((c) => (c.sector ?? null) === target);
  }, [companies, sectorFilter]);

  const bySector = useMemo((): Record<string, PimUniverseCompany[]> => {
    const map: Record<string, PimUniverseCompany[]> = {};
    for (const c of filtered) {
      const key = c.sector ?? "Unclassified";
      (map[key] ??= []).push(c);
    }
    return map;
  }, [filtered]);

  // Rows to render — flat list or grouped
  const rows = groupBySector ? null : filtered;
  const groups = groupBySector ? Object.entries(bySector).sort(([a], [b]) => a.localeCompare(b)) : null;

  const qualitySummary = useMemo(() => {
    const complete = companies.filter((c) => dataQualityScore(c) >= 3).length;
    const partial = companies.filter((c) => dataQualityScore(c) >= 1 && dataQualityScore(c) < 3).length;
    return { complete, partial, minimal: companies.length - complete - partial };
  }, [companies]);

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      {/* Header */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
            Universe Manager
          </h1>
          <p className="mt-1 text-sm text-va-text2">
            {total} companies across {sectors.length - 1} sectors.
          </p>
        </div>
        <VAButton
          variant={showForm ? "ghost" : "primary"}
          onClick={() => {
            setShowForm((v) => !v);
            setForm(EMPTY_FORM);
          }}
        >
          {showForm ? "Cancel" : "+ Add Company"}
        </VAButton>
      </div>

      {/* Quality summary strip */}
      {companies.length > 0 && (
        <div className="mb-4 flex flex-wrap gap-3">
          <span className="text-xs text-va-text2">Data quality:</span>
          <span className="text-xs text-green-400">{qualitySummary.complete} complete</span>
          <span className="text-xs text-yellow-400">{qualitySummary.partial} partial</span>
          <span className="text-xs text-va-text2">{qualitySummary.minimal} minimal</span>
        </div>
      )}

      {/* Add company form */}
      {showForm && (
        <VACard className="mb-6 p-5">
          <h2 className="mb-4 text-sm font-medium text-va-text">Add Company</h2>
          <form onSubmit={handleAddCompany} className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-va-text2">
                  Ticker <span className="text-va-danger">*</span>
                </label>
                <VAInput
                  value={form.ticker}
                  onChange={(e) => handleFormChange("ticker", e.target.value.toUpperCase())}
                  placeholder="e.g. AAPL"
                  maxLength={20}
                  required
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-va-text2">
                  Company Name <span className="text-va-danger">*</span>
                </label>
                <VAInput
                  value={form.company_name}
                  onChange={(e) => handleFormChange("company_name", e.target.value)}
                  placeholder="e.g. Apple Inc."
                  maxLength={255}
                  required
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-va-text2">Sector</label>
                <VAInput
                  value={form.sector}
                  onChange={(e) => handleFormChange("sector", e.target.value)}
                  placeholder="e.g. Technology"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-va-text2">Country ISO</label>
                <VAInput
                  value={form.country_iso}
                  onChange={(e) =>
                    handleFormChange("country_iso", e.target.value.toUpperCase().slice(0, 2))
                  }
                  placeholder="e.g. US"
                  maxLength={2}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-va-text2">Exchange</label>
                <VAInput
                  value={form.exchange}
                  onChange={(e) => handleFormChange("exchange", e.target.value)}
                  placeholder="e.g. NASDAQ"
                />
              </div>
            </div>
            <div className="flex gap-2 pt-2">
              <VAButton type="submit" variant="primary" disabled={submitting}>
                {submitting ? "Adding…" : "Add"}
              </VAButton>
              <VAButton
                type="button"
                variant="ghost"
                onClick={() => {
                  setShowForm(false);
                  setForm(EMPTY_FORM);
                }}
              >
                Cancel
              </VAButton>
            </div>
          </form>
        </VACard>
      )}

      {/* Error */}
      {error && (
        <div
          className="mb-4 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger"
          role="alert"
        >
          {error}
        </div>
      )}

      {/* Loading */}
      {loading && companies.length === 0 ? (
        <VASpinner label="Loading universe…" />
      ) : !loading && companies.length === 0 ? (
        <VACard className="p-6 text-center">
          <p className="text-sm text-va-text2">
            No companies in your universe yet. Use the &ldquo;Add Company&rdquo; button to add
            your first ticker.
          </p>
        </VACard>
      ) : (
        <>
          {/* Sector filter + view controls */}
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <span className="text-xs text-va-text2">Sector:</span>
            {sectors.map((s) => (
              <button
                key={s}
                onClick={() => setSectorFilter(s)}
                className={`rounded-full px-2 py-0.5 text-xs transition-colors ${
                  sectorFilter === s
                    ? "bg-va-blue text-white"
                    : "bg-va-surface text-va-text2 hover:text-va-text"
                }`}
              >
                {s === "all" ? `All (${companies.length})` : s}
              </button>
            ))}
            <span className="ml-auto">
              <button
                onClick={() => setGroupBySector((v) => !v)}
                className="text-xs text-va-text2 hover:text-va-text transition-colors"
              >
                {groupBySector ? "Flat view" : "Group by sector"}
              </button>
            </span>
          </div>

          {/* Company table — flat or grouped */}
          {groups ? (
            <div className="space-y-6">
              {groups.map(([sector, sectorCompanies]) => (
                <div key={sector}>
                  <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-va-text2">
                    {sector} ({sectorCompanies.length})
                  </h3>
                  <CompanyTable
                    companies={sectorCompanies}
                    actionLoading={actionLoading}
                    onToggleActive={handleToggleActive}
                    onRemove={handleRemove}
                  />
                </div>
              ))}
            </div>
          ) : (
            <CompanyTable
              companies={rows ?? []}
              actionLoading={actionLoading}
              onToggleActive={handleToggleActive}
              onRemove={handleRemove}
            />
          )}
        </>
      )}

      {/* Loading indicator while refreshing */}
      {loading && companies.length > 0 && (
        <div className="mt-4 flex justify-center">
          <VASpinner label="Refreshing…" />
        </div>
      )}
    </main>
  );
}

// ---------------------------------------------------------------------------
// Sub-component: reusable table (used in flat + grouped views)
// ---------------------------------------------------------------------------

function CompanyTable({
  companies,
  actionLoading,
  onToggleActive,
  onRemove,
}: {
  companies: PimUniverseCompany[];
  actionLoading: string | null;
  onToggleActive: (c: PimUniverseCompany) => void;
  onRemove: (c: PimUniverseCompany) => void;
}) {
  return (
    <div className="overflow-x-auto rounded-va-lg border border-va-border">
      <table className="w-full text-sm text-va-text">
        <thead>
          <tr className="border-b border-va-border bg-va-surface">
            <th className="px-3 py-2 text-left font-medium">Ticker</th>
            <th className="px-3 py-2 text-left font-medium">Company</th>
            <th className="px-3 py-2 text-left font-medium">Sector</th>
            <th className="px-3 py-2 text-left font-medium">Country</th>
            <th className="px-3 py-2 text-left font-medium">Exchange</th>
            <th className="px-3 py-2 text-left font-medium">Data Quality</th>
            <th className="px-3 py-2 text-left font-medium">Status</th>
            <th className="px-3 py-2 text-right font-medium">Actions</th>
          </tr>
        </thead>
        <tbody>
          {companies.map((company) => (
            <tr
              key={company.company_id}
              className="border-b border-va-border/50 transition-colors hover:bg-va-surface/50"
            >
              <td className="px-3 py-2 font-mono text-xs font-medium">{company.ticker}</td>
              <td className="px-3 py-2 font-medium">{company.company_name}</td>
              <td className="px-3 py-2 text-va-text2">{company.sector ?? "—"}</td>
              <td className="px-3 py-2 text-va-text2">{company.country_iso ?? "—"}</td>
              <td className="px-3 py-2 text-va-text2">{company.exchange ?? "—"}</td>
              <td className="px-3 py-2">
                <DataQualityBadge company={company} />
              </td>
              <td className="px-3 py-2">
                {company.is_active ? (
                  <VABadge variant="success">Active</VABadge>
                ) : (
                  <VABadge variant="default">Inactive</VABadge>
                )}
              </td>
              <td className="px-3 py-2">
                <div className="flex justify-end gap-2">
                  <VAButton
                    variant="ghost"
                    disabled={actionLoading === company.company_id}
                    onClick={() => onToggleActive(company)}
                  >
                    {actionLoading === company.company_id
                      ? "…"
                      : company.is_active
                        ? "Deactivate"
                        : "Activate"}
                  </VAButton>
                  <VAButton
                    variant="ghost"
                    disabled={actionLoading === company.company_id}
                    onClick={() => onRemove(company)}
                  >
                    Remove
                  </VAButton>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
