"use client";

import { Nav } from "@/components/nav";
import { VAButton, VACard, VAConfirmDialog, VAInput, VASelect, VASpinner, useToast } from "@/components/ui";
import {
  api,
  type CurrencySettings,
  type FxRate,
} from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { useCallback, useEffect, useState } from "react";

export default function CurrencySettingsPage() {
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [settings, setSettings] = useState<CurrencySettings | null>(null);
  const [rates, setRates] = useState<FxRate[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { toast } = useToast();
  const [confirmAction, setConfirmAction] = useState<{ action: () => void; title: string; description: string } | null>(null);
  const [rateForm, setRateForm] = useState({
    from_currency: "USD",
    to_currency: "EUR",
    effective_date: "",
    rate: "",
  });
  const [rateErrors, setRateErrors] = useState<Record<string, string>>({});
  const [conversion, setConversion] = useState({
    from_currency: "USD",
    to_currency: "EUR",
    as_of: "",
    result: "",
  });

  const load = useCallback(async () => {
    if (!tenantId) return;
    setLoading(true);
    setError(null);
    try {
      const [settingsRes, ratesRes] = await Promise.all([
        api.currency.getSettings(tenantId),
        api.currency.listRates(tenantId, { limit: 50, offset: 0 }),
      ]);
      setSettings(settingsRes);
      setRates(ratesRes.rates ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) return;
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);
    })();
  }, []);

  useEffect(() => {
    if (tenantId) load();
  }, [tenantId, load]);

  async function handleSaveSettings() {
    if (!tenantId || !settings) return;
    setSaving(true);
    setError(null);
    try {
      await api.currency.updateSettings(tenantId, {
        base_currency: settings.base_currency,
        reporting_currency: settings.reporting_currency,
        fx_source: settings.fx_source,
      });
      await load();
      toast.success("Currency settings saved");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  }

  async function handleAddRate() {
    if (!tenantId) return;
    const errors: Record<string, string> = {};
    if (rateForm.from_currency.trim().length !== 3) errors.from_currency = "Must be a 3-letter currency code";
    if (rateForm.to_currency.trim().length !== 3) errors.to_currency = "Must be a 3-letter currency code";
    if (!rateForm.effective_date) errors.effective_date = "Effective date is required";
    const rateNum = Number(rateForm.rate);
    if (!rateForm.rate.trim() || !Number.isFinite(rateNum) || rateNum <= 0)
      errors.rate = "Enter a positive number";
    if (Object.keys(errors).length > 0) { setRateErrors(errors); return; }
    setRateErrors({});
    setError(null);
    try {
      await api.currency.addRate(tenantId, {
        from_currency: rateForm.from_currency.toUpperCase(),
        to_currency: rateForm.to_currency.toUpperCase(),
        effective_date: rateForm.effective_date,
        rate: rateNum,
      });
      setRateForm((prev) => ({ ...prev, rate: "" }));
      await load();
      toast.success("FX rate added");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(msg);
    }
  }

  async function handleDeleteRate(rate: FxRate) {
    if (!tenantId) return;
    setError(null);
    try {
      await api.currency.deleteRate(
        tenantId,
        rate.from_currency,
        rate.to_currency,
        rate.effective_date
      );
      await load();
      toast.success("FX rate deleted");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(msg);
    }
  }

  async function handleConvert() {
    if (!tenantId) return;
    setError(null);
    try {
      const res = await api.currency.convert(tenantId, {
        from_currency: conversion.from_currency,
        to_currency: conversion.to_currency,
        as_of: conversion.as_of || undefined,
      });
      setConversion((prev) => ({
        ...prev,
        result: res.rate.toFixed(4),
      }));
      toast.success("Conversion complete");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(msg);
    }
  }

  return (
    <div className="min-h-screen bg-va-midnight">
      <Nav />
      <main className="mx-auto max-w-5xl px-4 py-8">
        <div className="mb-6">
          <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
            Currency Settings
          </h1>
          <p className="mt-1 text-sm text-va-text2">
            Manage base/reporting currency and FX rates.
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

        {loading ? (
          <VASpinner label="Loading currency settings…" />
        ) : settings ? (
          <div className="space-y-8">
            <VACard className="p-5">
              <h2 className="text-lg font-medium text-va-text">
                Tenant settings
              </h2>
              <div className="mt-4 grid gap-3 md:grid-cols-3">
                <div>
                  <label className="mb-1 block text-sm font-medium text-va-text">
                    Base currency
                  </label>
                  <VAInput
                    value={settings.base_currency}
                    onChange={(e) =>
                      setSettings((prev) =>
                        prev
                          ? { ...prev, base_currency: e.target.value.toUpperCase() }
                          : prev
                      )
                    }
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-va-text">
                    Reporting currency
                  </label>
                  <VAInput
                    value={settings.reporting_currency}
                    onChange={(e) =>
                      setSettings((prev) =>
                        prev
                          ? { ...prev, reporting_currency: e.target.value.toUpperCase() }
                          : prev
                      )
                    }
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-va-text">
                    FX source
                  </label>
                  <VASelect
                    value={settings.fx_source}
                    onChange={(e) =>
                      setSettings((prev) =>
                        prev ? { ...prev, fx_source: e.target.value } : prev
                      )
                    }
                  >
                    <option value="manual">Manual</option>
                    <option value="feed">Feed</option>
                  </VASelect>
                </div>
              </div>
              <VAButton
                className="mt-4"
                onClick={handleSaveSettings}
                disabled={saving}
              >
                {saving ? "Saving…" : "Save settings"}
              </VAButton>
            </VACard>

            <VACard className="p-5">
              <h2 className="text-lg font-medium text-va-text">FX rates</h2>
              <div className="mt-4 grid gap-3 md:grid-cols-4">
                <VAInput
                  placeholder="From (USD)"
                  value={rateForm.from_currency}
                  onChange={(e) => {
                    setRateForm((prev) => ({
                      ...prev,
                      from_currency: e.target.value.toUpperCase(),
                    }));
                    setRateErrors((prev) => ({ ...prev, from_currency: "" }));
                  }}
                  error={rateErrors.from_currency}
                />
                <VAInput
                  placeholder="To (EUR)"
                  value={rateForm.to_currency}
                  onChange={(e) => {
                    setRateForm((prev) => ({
                      ...prev,
                      to_currency: e.target.value.toUpperCase(),
                    }));
                    setRateErrors((prev) => ({ ...prev, to_currency: "" }));
                  }}
                  error={rateErrors.to_currency}
                />
                <VAInput
                  type="date"
                  value={rateForm.effective_date}
                  onChange={(e) => {
                    setRateForm((prev) => ({
                      ...prev,
                      effective_date: e.target.value,
                    }));
                    setRateErrors((prev) => ({ ...prev, effective_date: "" }));
                  }}
                  error={rateErrors.effective_date}
                />
                <VAInput
                  placeholder="Rate"
                  value={rateForm.rate}
                  onChange={(e) => {
                    setRateForm((prev) => ({ ...prev, rate: e.target.value }));
                    setRateErrors((prev) => ({ ...prev, rate: "" }));
                  }}
                  error={rateErrors.rate}
                />
              </div>
              <VAButton className="mt-3" onClick={handleAddRate}>
                Add rate
              </VAButton>
              {rates.length > 0 && (
                <div className="mt-4 overflow-x-auto rounded-va-lg border border-va-border">
                  <table className="w-full text-sm text-va-text">
                    <thead>
                      <tr className="border-b border-va-border bg-va-surface">
                        <th className="px-3 py-2 text-left font-medium">
                          Pair
                        </th>
                        <th className="px-3 py-2 text-left font-medium">
                          Effective
                        </th>
                        <th className="px-3 py-2 text-left font-medium">
                          Rate
                        </th>
                        <th className="px-3 py-2" />
                      </tr>
                    </thead>
                    <tbody>
                      {rates.map((rate) => (
                        <tr
                          key={`${rate.from_currency}-${rate.to_currency}-${rate.effective_date}`}
                          className="border-b border-va-border/50"
                        >
                          <td className="px-3 py-2">
                            {rate.from_currency}/{rate.to_currency}
                          </td>
                          <td className="px-3 py-2">{rate.effective_date}</td>
                          <td className="px-3 py-2">{rate.rate}</td>
                          <td className="px-3 py-2 text-right">
                            <VAButton
                              variant="ghost"
                              onClick={() => setConfirmAction({
                              action: () => handleDeleteRate(rate),
                              title: `Delete FX rate ${rate.from_currency}/${rate.to_currency}?`,
                              description: "This action cannot be undone.",
                            })}
                            >
                              Delete
                            </VAButton>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </VACard>

            <VACard className="p-5">
              <h2 className="text-lg font-medium text-va-text">
                Conversion calculator
              </h2>
              <div className="mt-4 grid gap-3 md:grid-cols-4">
                <VAInput
                  placeholder="From"
                  value={conversion.from_currency}
                  onChange={(e) =>
                    setConversion((prev) => ({
                      ...prev,
                      from_currency: e.target.value.toUpperCase(),
                    }))
                  }
                />
                <VAInput
                  placeholder="To"
                  value={conversion.to_currency}
                  onChange={(e) =>
                    setConversion((prev) => ({
                      ...prev,
                      to_currency: e.target.value.toUpperCase(),
                    }))
                  }
                />
                <VAInput
                  type="date"
                  value={conversion.as_of}
                  onChange={(e) =>
                    setConversion((prev) => ({ ...prev, as_of: e.target.value }))
                  }
                />
                <VAInput
                  placeholder="Rate"
                  value={conversion.result}
                  readOnly
                />
              </div>
              <VAButton className="mt-3" onClick={handleConvert}>
                Convert
              </VAButton>
            </VACard>
          </div>
        ) : null}
      <VAConfirmDialog
        open={!!confirmAction}
        title={confirmAction?.title ?? ""}
        description={confirmAction?.description}
        onConfirm={() => { confirmAction?.action(); setConfirmAction(null); }}
        onCancel={() => setConfirmAction(null)}
      />
      </main>
    </div>
  );
}
