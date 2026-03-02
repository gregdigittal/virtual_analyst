"use client";

import { VAButton, VACard, VAInput, VASpinner } from "@/components/ui";
import { api, type SamlConfigResponse } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { useCallback, useEffect, useState } from "react";

export default function SsoSettingsPage() {
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [config, setConfig] = useState<SamlConfigResponse | null>(null);
  const [form, setForm] = useState({
    idp_metadata_url: "",
    idp_metadata_xml: "",
    entity_id: "",
    acs_url: "",
    idp_sso_url: "",
    idp_certificate: "",
    attribute_mapping: "{}",
  });
  const [saving, setSaving] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!tenantId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.sso.getConfig(tenantId);
      setConfig(res);
      setEnabled(res.enabled ?? res.configured ?? false);
      if (res.configured) {
        setForm((prev) => ({
          ...prev,
          entity_id: res.entity_id ?? "",
          acs_url: res.acs_url ?? "",
          idp_sso_url: res.idp_sso_url ?? "",
          attribute_mapping: JSON.stringify(res.attribute_mapping ?? {}, null, 2),
        }));
      }
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

  async function handleSave() {
    if (!tenantId) return;
    setSaving(true);
    setError(null);
    try {
      const mapping = JSON.parse(form.attribute_mapping || "{}");
      await api.sso.updateConfig(tenantId, {
        enabled,
        idp_metadata_url: form.idp_metadata_url || null,
        idp_metadata_xml: form.idp_metadata_xml || null,
        entity_id: form.entity_id,
        acs_url: form.acs_url,
        idp_sso_url: form.idp_sso_url || null,
        idp_certificate: form.idp_certificate || null,
        attribute_mapping: mapping,
      });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-6">
        <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
          SSO / SAML
        </h1>
        <p className="mt-1 text-sm text-va-text2">
          Configure identity provider settings and attribute mappings.
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
        <VASpinner label="Loading SSO configuration…" />
      ) : (
        <VACard className="p-5">
          <div className="mb-3 text-sm text-va-text2">
            Status:{" "}
            <span className={config?.configured ? "text-va-success" : "text-va-warning"}>
              {config?.configured ? "Configured" : "Not configured"}
            </span>
          </div>
          <div className="mb-4 flex items-center gap-3">
            <label htmlFor="sso-toggle" className="text-sm font-medium text-va-text">
              Enable SSO
            </label>
            <button
              id="sso-toggle"
              role="switch"
              aria-checked={enabled}
              aria-label="Enable SSO"
              onClick={() => setEnabled((prev) => !prev)}
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight ${
                enabled ? "bg-va-blue" : "bg-va-border"
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition ${
                  enabled ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          </div>
          <div className="grid gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-va-text">
                IdP metadata URL
              </label>
              <VAInput
                value={form.idp_metadata_url}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, idp_metadata_url: e.target.value }))
                }
                placeholder="https://idp.example.com/metadata"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-va-text">
                IdP metadata XML
              </label>
              <textarea
                className="min-h-[120px] w-full rounded-va-xs border border-va-border bg-va-surface px-3 py-2 text-sm text-va-text"
                value={form.idp_metadata_xml}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, idp_metadata_xml: e.target.value }))
                }
                placeholder="<EntityDescriptor>…</EntityDescriptor>"
              />
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium text-va-text">
                  Entity ID
                </label>
                <VAInput
                  value={form.entity_id}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, entity_id: e.target.value }))
                  }
                  placeholder="urn:example:va"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-va-text">
                  ACS URL
                </label>
                <VAInput
                  value={form.acs_url}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, acs_url: e.target.value }))
                  }
                  placeholder="https://api.example.com/api/v1/auth/saml/acs"
                />
              </div>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-va-text">
                IdP SSO URL
              </label>
              <VAInput
                value={form.idp_sso_url}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, idp_sso_url: e.target.value }))
                }
                placeholder="https://idp.example.com/sso"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-va-text">
                IdP certificate (PEM)
              </label>
              <textarea
                className="min-h-[120px] w-full rounded-va-xs border border-va-border bg-va-surface px-3 py-2 text-sm text-va-text"
                value={form.idp_certificate}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, idp_certificate: e.target.value }))
                }
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-va-text">
                Attribute mapping (JSON)
              </label>
              <textarea
                className="min-h-[120px] w-full rounded-va-xs border border-va-border bg-va-surface px-3 py-2 text-sm text-va-text"
                value={form.attribute_mapping}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, attribute_mapping: e.target.value }))
                }
              />
            </div>
          </div>
          <VAButton className="mt-4" onClick={handleSave} disabled={saving}>
            {saving ? "Saving…" : "Save configuration"}
          </VAButton>
        </VACard>
      )}
    </main>
  );
}
