"use client";

import { VABadge, VAButton, VACard, VAInput, VASpinner, useToast } from "@/components/ui";
import { api, type PimUniverseCompany } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { useCallback, useEffect, useState } from "react";

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

const LIMIT = 50;

export default function UniverseManagerPage() {
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [companies, setCompanies] = useState<PimUniverseCompany[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<CompanyForm>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const { toast } = useToast();

  const loadCompanies = useCallback(
    async (currentTenantId: string, currentOffset: number) => {
      setLoading(true);
      setError(null);
      try {
        const res = await api.pim.universe.list(currentTenantId, {
          limit: LIMIT,
          offset: currentOffset,
        });
        if (currentOffset === 0) {
          setCompanies(res.items);
        } else {
          setCompanies((prev) => [...prev, ...res.items]);
        }
        setTotal(res.total);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    },
    [],
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
    if (tenantId) loadCompanies(tenantId, 0);
  }, [tenantId, loadCompanies]);

  function handleFormChange(field: keyof CompanyForm, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
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
      setOffset(0);
      await loadCompanies(tenantId, 0);
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
      toast.success(
        `${company.ticker} ${company.is_active ? "deactivated" : "activated"}.`,
      );
      setCompanies((prev) =>
        prev.map((c) =>
          c.company_id === company.company_id
            ? { ...c, is_active: !c.is_active }
            : c,
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
      setCompanies((prev) =>
        prev.filter((c) => c.company_id !== company.company_id),
      );
      setTotal((prev) => prev - 1);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e));
    } finally {
      setActionLoading(null);
    }
  }

  async function handleLoadMore() {
    if (!tenantId) return;
    const nextOffset = offset + LIMIT;
    setOffset(nextOffset);
    await loadCompanies(tenantId, nextOffset);
  }

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      {/* Page header */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
            Universe Manager
          </h1>
          <p className="mt-1 text-sm text-va-text2">
            Manage the companies in your investable universe.
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

      {/* Add company form */}
      {showForm && (
        <VACard className="mb-6 p-5">
          <h2 className="mb-4 text-sm font-medium text-va-text">
            Add Company
          </h2>
          <form onSubmit={handleAddCompany} className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-va-text2">
                  Ticker <span className="text-va-danger">*</span>
                </label>
                <VAInput
                  value={form.ticker}
                  onChange={(e) =>
                    handleFormChange("ticker", e.target.value.toUpperCase())
                  }
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
                  onChange={(e) =>
                    handleFormChange("company_name", e.target.value)
                  }
                  placeholder="e.g. Apple Inc."
                  maxLength={255}
                  required
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-va-text2">
                  Sector
                </label>
                <VAInput
                  value={form.sector}
                  onChange={(e) => handleFormChange("sector", e.target.value)}
                  placeholder="e.g. Technology"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-va-text2">
                  Country ISO
                </label>
                <VAInput
                  value={form.country_iso}
                  onChange={(e) =>
                    handleFormChange(
                      "country_iso",
                      e.target.value.toUpperCase().slice(0, 2),
                    )
                  }
                  placeholder="e.g. US"
                  maxLength={2}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-va-text2">
                  Exchange
                </label>
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

      {/* Error state */}
      {error && (
        <div
          className="mb-4 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger"
          role="alert"
        >
          {error}
        </div>
      )}

      {/* Loading state */}
      {loading && companies.length === 0 ? (
        <VASpinner label="Loading universe…" />
      ) : !loading && companies.length === 0 ? (
        /* Empty state */
        <VACard className="p-6 text-center">
          <p className="text-sm text-va-text2">
            No companies in your universe yet. Use the &ldquo;Add Company&rdquo; button above to
            add your first ticker.
          </p>
        </VACard>
      ) : (
        /* Company table */
        <div className="overflow-x-auto rounded-va-lg border border-va-border">
          <table className="w-full text-sm text-va-text">
            <thead>
              <tr className="border-b border-va-border bg-va-surface">
                <th className="px-3 py-2 text-left font-medium">Ticker</th>
                <th className="px-3 py-2 text-left font-medium">Company</th>
                <th className="px-3 py-2 text-left font-medium">Sector</th>
                <th className="px-3 py-2 text-left font-medium">Country</th>
                <th className="px-3 py-2 text-left font-medium">Exchange</th>
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
                  <td className="px-3 py-2 font-mono text-xs font-medium">
                    {company.ticker}
                  </td>
                  <td className="px-3 py-2 font-medium">{company.company_name}</td>
                  <td className="px-3 py-2 text-va-text2">
                    {company.sector ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-va-text2">
                    {company.country_iso ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-va-text2">
                    {company.exchange ?? "—"}
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
                        onClick={() => handleToggleActive(company)}
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
                        onClick={() => handleRemove(company)}
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
      )}

      {/* Load more */}
      {!loading && companies.length < total && (
        <div className="mt-4 flex justify-center">
          <VAButton variant="ghost" onClick={handleLoadMore}>
            Load more ({companies.length} of {total})
          </VAButton>
        </div>
      )}

      {/* Loading indicator for load-more */}
      {loading && companies.length > 0 && (
        <div className="mt-4 flex justify-center">
          <VASpinner label="Loading more…" />
        </div>
      )}
    </main>
  );
}
