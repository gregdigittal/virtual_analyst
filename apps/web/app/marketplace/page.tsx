"use client";

import { Nav } from "@/components/nav";
import { VAButton, VACard, VAInput, VASpinner } from "@/components/ui";
import { api, type MarketplaceTemplate } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { useCallback, useEffect, useState } from "react";

export default function MarketplacePage() {
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | undefined>(undefined);
  const [templates, setTemplates] = useState<MarketplaceTemplate[]>([]);
  const [filters, setFilters] = useState({
    industry: "",
    template_type: "",
  });
  const [forms, setForms] = useState<Record<string, { label: string; fiscal_year: string }>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!tenantId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.marketplace.list(tenantId, {
        industry: filters.industry || undefined,
        template_type: filters.template_type || undefined,
        limit: 50,
        offset: 0,
      });
      setTemplates(res.items ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [tenantId, filters]);

  useEffect(() => {
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) return;
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);
      setUserId(ctx.userId);
    })();
  }, []);

  useEffect(() => {
    if (tenantId) load();
  }, [tenantId, load]);

  async function handleUse(templateId: string) {
    if (!tenantId) return;
    const form = forms[templateId] || { label: "", fiscal_year: "" };
    if (!form.label || !form.fiscal_year) {
      setError("Provide a label and fiscal year to use the template.");
      return;
    }
    setError(null);
    try {
      await api.marketplace.useTemplate(tenantId, userId, templateId, {
        label: form.label,
        fiscal_year: form.fiscal_year,
        answers: {},
        num_periods: 12,
      });
      setForms((prev) => ({ ...prev, [templateId]: { label: "", fiscal_year: "" } }));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="min-h-screen bg-va-midnight">
      <Nav />
      <main className="mx-auto max-w-6xl px-4 py-8">
        <div className="mb-6">
          <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
            Marketplace
          </h1>
          <p className="mt-1 text-sm text-va-text2">
            Browse templates and create new baselines or budgets.
          </p>
        </div>

        {error && (
          <div
            className="mb-4 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger"
            role="alert"
          >
            {error}
          </div>
        )}

        <VACard className="mb-4 p-4">
          <div className="grid gap-3 md:grid-cols-3">
            <VAInput
              placeholder="Industry"
              value={filters.industry}
              onChange={(e) =>
                setFilters((prev) => ({ ...prev, industry: e.target.value }))
              }
            />
            <VAInput
              placeholder="Template type (budget/model)"
              value={filters.template_type}
              onChange={(e) =>
                setFilters((prev) => ({
                  ...prev,
                  template_type: e.target.value,
                }))
              }
            />
            <VAButton variant="secondary" onClick={load}>
              Apply filters
            </VAButton>
          </div>
        </VACard>

        {loading ? (
          <VASpinner label="Loading marketplace…" />
        ) : templates.length === 0 ? (
          <VACard className="p-6 text-center text-va-text2">
            No templates available. Check back soon for community-contributed models.
          </VACard>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {templates.map((tpl) => {
              const form = forms[tpl.template_id] || { label: "", fiscal_year: "" };
              return (
                <VACard key={tpl.template_id} className="p-5">
                  <div className="flex items-center justify-between">
                    <h2 className="text-lg font-medium text-va-text">
                      {tpl.name}
                    </h2>
                    <span className="rounded-full bg-va-border px-2 py-0.5 text-xs text-va-text2">
                      {tpl.template_type}
                    </span>
                  </div>
                  <p className="mt-2 text-sm text-va-text2">
                    {tpl.description}
                  </p>
                  <p className="mt-1 text-xs text-va-text2">
                    Industry: {tpl.industry}
                  </p>
                  <div className="mt-4 grid gap-2 md:grid-cols-2">
                    <VAInput
                      placeholder="Label"
                      value={form.label}
                      onChange={(e) =>
                        setForms((prev) => ({
                          ...prev,
                          [tpl.template_id]: {
                            ...form,
                            label: e.target.value,
                          },
                        }))
                      }
                    />
                    <VAInput
                      placeholder="Fiscal year"
                      value={form.fiscal_year}
                      onChange={(e) =>
                        setForms((prev) => ({
                          ...prev,
                          [tpl.template_id]: {
                            ...form,
                            fiscal_year: e.target.value,
                          },
                        }))
                      }
                    />
                  </div>
                  <VAButton className="mt-3" onClick={() => handleUse(tpl.template_id)}>
                    Use template
                  </VAButton>
                </VACard>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
