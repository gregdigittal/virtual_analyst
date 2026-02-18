"use client";

import { Nav } from "@/components/nav";
import { VAButton, VACard, VAInput } from "@/components/ui";
import { api, type CsvImportResponse } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { useEffect, useState } from "react";

export default function CsvImportPage() {
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | undefined>(undefined);
  const [file, setFile] = useState<File | null>(null);
  const [baselineId, setBaselineId] = useState("");
  const [baselineVersion, setBaselineVersion] = useState("v1");
  const [label, setLabel] = useState("CSV Import");
  const [mappingJson, setMappingJson] = useState("{}");
  const [result, setResult] = useState<CsvImportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) return;
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);
      setUserId(ctx.userId);
    })();
  }, []);

  async function handleImport() {
    if (!tenantId || !file || !baselineId) return;
    setLoading(true);
    setError(null);
    try {
      const mapping = JSON.parse(mappingJson || "{}");
      const res = await api.csvImport.upload(tenantId, userId, {
        file,
        parent_baseline_id: baselineId,
        parent_baseline_version: baselineVersion,
        label,
        column_mapping: mapping,
      });
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-va-midnight">
      <Nav />
      <main className="mx-auto max-w-4xl px-4 py-8">
        <div className="mb-6">
          <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
            CSV Import
          </h1>
          <p className="mt-1 text-sm text-va-text2">
            Upload a CSV to create a scenario and draft workspace.
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

        <VACard className="p-5">
          <div className="grid gap-3 md:grid-cols-2">
            <VAInput
              placeholder="Baseline ID"
              value={baselineId}
              onChange={(e) => setBaselineId(e.target.value)}
            />
            <VAInput
              placeholder="Baseline version"
              value={baselineVersion}
              onChange={(e) => setBaselineVersion(e.target.value)}
            />
            <VAInput
              placeholder="Label"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
            />
            <input
              type="file"
              accept=".csv"
              className="text-sm text-va-text2"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>
          <div className="mt-4">
            <label className="mb-1 block text-sm font-medium text-va-text">
              Column mapping (JSON)
            </label>
            <textarea
              className="min-h-[120px] w-full rounded-va-xs border border-va-border bg-va-surface px-3 py-2 text-sm text-va-text"
              value={mappingJson}
              onChange={(e) => setMappingJson(e.target.value)}
            />
          </div>
          <VAButton className="mt-3" onClick={handleImport} disabled={loading}>
            {loading ? "Importing…" : "Import CSV"}
          </VAButton>
        </VACard>

        {result && (
          <VACard className="mt-6 p-5">
            <h2 className="text-lg font-medium text-va-text">
              Import complete
            </h2>
            <p className="mt-2 text-sm text-va-text2">
              Draft session: {result.draft_session_id}
            </p>
            <p className="text-sm text-va-text2">
              Scenario: {result.scenario_id}
            </p>
            <p className="text-sm text-va-text2">
              Overrides: {result.overrides_count}
            </p>
          </VACard>
        )}
      </main>
    </div>
  );
}
