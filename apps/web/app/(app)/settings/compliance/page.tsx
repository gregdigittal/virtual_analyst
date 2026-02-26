"use client";

import { VAButton, VACard, VAConfirmDialog, VAInput, useToast } from "@/components/ui";
import { api, type ComplianceExport } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { useCallback, useEffect, useState } from "react";

export default function CompliancePage() {
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | undefined>(undefined);
  const [targetUserId, setTargetUserId] = useState("");
  const [exportData, setExportData] = useState<ComplianceExport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { toast } = useToast();
  const [confirmAction, setConfirmAction] = useState<{ action: () => void; title: string; description: string } | null>(null);

  useEffect(() => {
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) return;
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);
      setUserId(ctx.userId);
      setTargetUserId(ctx.userId);
    })();
  }, []);

  const handleExport = useCallback(async () => {
    if (!tenantId || !targetUserId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.compliance.export(tenantId, userId, targetUserId);
      setExportData(res);
      toast.success("Data exported");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }, [tenantId, userId, targetUserId]);

  const handleAnonymize = useCallback(async () => {
    if (!tenantId || !targetUserId) return;
    setLoading(true);
    setError(null);
    try {
      await api.compliance.anonymize(tenantId, userId, targetUserId);
      setExportData(null);
      toast.success("User anonymized");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }, [tenantId, userId, targetUserId]);

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-6">
        <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
          Compliance & GDPR
        </h1>
        <p className="mt-1 text-sm text-va-text2">
          Export personal data or anonymize user records.
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
        <label className="mb-1 block text-sm font-medium text-va-text">
          User ID
        </label>
        <VAInput
          value={targetUserId}
          onChange={(e) => setTargetUserId(e.target.value)}
          placeholder="User ID to export/anonymize"
        />
        <div className="mt-4 flex flex-wrap gap-2">
          <VAButton onClick={handleExport} disabled={loading}>
            Export data
          </VAButton>
          <VAButton variant="danger" onClick={() => setConfirmAction({
            action: handleAnonymize,
            title: "Anonymize this user?",
            description: "This is irreversible. All personal data for this user will be permanently removed.",
          })} disabled={loading}>
            Anonymize user
          </VAButton>
        </div>
      </VACard>

      {exportData && (
        <VACard className="mt-6 p-5">
          <h2 className="text-lg font-medium text-va-text">Export preview</h2>
          <pre className="mt-3 max-h-[400px] overflow-auto rounded-va-md border border-va-border bg-va-surface p-3 text-xs text-va-text2">
{JSON.stringify(exportData, null, 2)}
          </pre>
        </VACard>
      )}
    <VAConfirmDialog
      open={!!confirmAction}
      title={confirmAction?.title ?? ""}
      description={confirmAction?.description}
      confirmLabel="Anonymize"
      onConfirm={() => { confirmAction?.action(); setConfirmAction(null); }}
      onCancel={() => setConfirmAction(null)}
    />
    </main>
  );
}
