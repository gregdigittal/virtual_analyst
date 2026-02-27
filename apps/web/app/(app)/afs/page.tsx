"use client";

import { api, type AFSEngagement, type AFSFramework } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import {
  VABadge,
  VAButton,
  VACard,
  VAEmptyState,
  VAInput,
  VAListToolbar,
  VASelect,
  VAListSkeleton,
  VAErrorAlert,
  useToast,
} from "@/components/ui";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

const STATUS_OPTIONS = [
  { value: "setup", label: "Setup" },
  { value: "ingestion", label: "Ingestion" },
  { value: "drafting", label: "Drafting" },
  { value: "review", label: "Review" },
  { value: "approved", label: "Approved" },
  { value: "published", label: "Published" },
];

function statusBadgeVariant(
  s: string,
): "default" | "success" | "warning" | "danger" | "violet" {
  switch (s) {
    case "setup":
      return "default";
    case "ingestion":
      return "default";
    case "drafting":
      return "violet";
    case "review":
      return "warning";
    case "approved":
    case "published":
      return "success";
    default:
      return "default";
  }
}

export default function AFSPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [engagements, setEngagements] = useState<AFSEngagement[]>([]);
  const [frameworks, setFrameworks] = useState<AFSFramework[]>([]);
  const [total, setTotal] = useState(0);

  // Search & filter
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [retryCount, setRetryCount] = useState(0);

  // Create dialog
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);

  // Create form fields
  const [entityName, setEntityName] = useState("");
  const [frameworkId, setFrameworkId] = useState("");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [priorEngagementId, setPriorEngagementId] = useState("");
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});

  /* ------------------------------------------------------------------ */
  /*  Data loading                                                       */
  /* ------------------------------------------------------------------ */
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) {
        router.replace("/login");
        return;
      }
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);
      try {
        // Auto-seed frameworks if none exist
        let fwRes = await api.afs.listFrameworks(ctx.tenantId);
        if (!cancelled && (fwRes.items ?? []).length === 0) {
          try {
            await api.afs.seedFrameworks(ctx.tenantId);
            fwRes = await api.afs.listFrameworks(ctx.tenantId);
          } catch {
            /* best-effort */
          }
        }
        const engRes = await api.afs.listEngagements(ctx.tenantId);
        if (!cancelled) {
          setFrameworks(fwRes.items ?? []);
          setEngagements(engRes.items ?? []);
          setTotal(engRes.total ?? 0);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router, retryCount]);

  /* ------------------------------------------------------------------ */
  /*  Create dialog accessibility                                        */
  /* ------------------------------------------------------------------ */
  const createFormRef = useRef<HTMLFormElement>(null);
  const prevFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (showCreate) {
      setFormErrors({});
      prevFocusRef.current = document.activeElement as HTMLElement;
      requestAnimationFrame(() => {
        createFormRef.current?.querySelector<HTMLElement>("input")?.focus();
      });
    } else if (prevFocusRef.current) {
      prevFocusRef.current.focus();
      prevFocusRef.current = null;
    }
  }, [showCreate]);

  useEffect(() => {
    if (!showCreate) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") setShowCreate(false);
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [showCreate]);

  const handleCreateKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key !== "Tab" || !createFormRef.current) return;
    const focusable = createFormRef.current.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }, []);

  /* ------------------------------------------------------------------ */
  /*  Create handler                                                     */
  /* ------------------------------------------------------------------ */
  async function handleCreate() {
    const errors: Record<string, string> = {};
    if (!entityName.trim()) errors.entityName = "Entity name is required";
    if (!frameworkId) errors.frameworkId = "Select an accounting framework";
    if (!periodStart) errors.periodStart = "Start date is required";
    if (!periodEnd) errors.periodEnd = "End date is required";
    if (periodStart && periodEnd && periodStart >= periodEnd)
      errors.periodEnd = "End date must be after start date";
    setFormErrors(errors);
    if (Object.keys(errors).length > 0 || !tenantId) return;
    setCreating(true);
    try {
      const eng = await api.afs.createEngagement(tenantId, {
        entity_name: entityName,
        framework_id: frameworkId,
        period_start: periodStart,
        period_end: periodEnd,
        prior_engagement_id: priorEngagementId || undefined,
      });
      toast.success("Engagement created");
      setShowCreate(false);
      setEntityName("");
      setFrameworkId("");
      setPeriodStart("");
      setPeriodEnd("");
      setPriorEngagementId("");
      setFormErrors({});
      router.push(`/afs/${eng.engagement_id}/setup`);
    } catch (e) {
      toast.error(
        e instanceof Error ? e.message : "Failed to create engagement",
      );
    } finally {
      setCreating(false);
    }
  }

  /* ------------------------------------------------------------------ */
  /*  Client-side filtering                                              */
  /* ------------------------------------------------------------------ */
  const filtered = engagements.filter((e) => {
    if (
      search &&
      !e.entity_name.toLowerCase().includes(search.toLowerCase())
    )
      return false;
    if (statusFilter && e.status !== statusFilter) return false;
    return true;
  });

  /* ------------------------------------------------------------------ */
  /*  Framework lookup helper                                            */
  /* ------------------------------------------------------------------ */
  function frameworkName(fwId: string): string {
    const fw = frameworks.find((f) => f.framework_id === fwId);
    return fw?.name ?? "Unknown framework";
  }

  /* ------------------------------------------------------------------ */
  /*  Render                                                             */
  /* ------------------------------------------------------------------ */
  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
            Annual Financial Statements
          </h1>
          <p className="mt-1 text-sm text-va-text2">
            AI-powered financial statement generation with IFRS/GAAP
            compliance.
          </p>
        </div>
        <div className="flex gap-2">
          <Link href="/afs/frameworks">
            <VAButton variant="secondary">Custom Framework</VAButton>
          </Link>
          <VAButton variant="primary" onClick={() => setShowCreate(true)}>
            New Engagement
          </VAButton>
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <VAListSkeleton count={3} />
      )}

      {/* Error */}
      {!loading && error && (
        <VAErrorAlert
          message={error}
          onRetry={() => setRetryCount((c) => c + 1)}
          className="mb-4"
        />
      )}

      {/* Loaded content */}
      {!loading && !error && (
        <>
          {/* Empty state — no engagements at all */}
          {engagements.length === 0 && (
            <VAEmptyState
              icon="file-text"
              title="No AFS engagements yet"
              description="Create an engagement to start generating financial statements."
              actionLabel="New engagement"
              onAction={() => setShowCreate(true)}
            />
          )}

          {/* Engagements exist */}
          {engagements.length > 0 && (
            <>
              <VAListToolbar
                searchValue={search}
                onSearchChange={setSearch}
                searchPlaceholder="Search by entity name..."
                filters={[
                  {
                    key: "status",
                    label: "All statuses",
                    options: STATUS_OPTIONS,
                  },
                ]}
                filterValues={{ status: statusFilter }}
                onFilterChange={(_key, value) => setStatusFilter(value)}
                onClearFilters={() => {
                  setSearch("");
                  setStatusFilter("");
                }}
              />

              {/* No results after filtering */}
              {filtered.length === 0 && (
                <VAEmptyState
                  variant="no-results"
                  title="No engagements match your search"
                />
              )}

              {/* Engagement cards */}
              {filtered.length > 0 && (
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {filtered.map((eng) => (
                    <Link
                      key={eng.engagement_id}
                      href={
                        eng.status === "setup"
                          ? `/afs/${eng.engagement_id}/setup`
                          : eng.status === "published"
                            ? `/afs/${eng.engagement_id}/output`
                            : eng.status === "review" || eng.status === "approved"
                              ? `/afs/${eng.engagement_id}/review`
                              : `/afs/${eng.engagement_id}/sections`
                      }
                      className="group cursor-pointer"
                    >
                      <VACard className="h-full p-5 transition-colors group-hover:border-va-blue/50">
                        <div className="flex items-start justify-between gap-2">
                          <h3 className="text-sm font-semibold text-va-text line-clamp-2">
                            {eng.entity_name}
                          </h3>
                          <div className="flex items-center gap-1">
                            {eng.prior_engagement_id && (
                              <VABadge variant="violet">Linked</VABadge>
                            )}
                            <VABadge variant={statusBadgeVariant(eng.status)}>
                              {eng.status}
                            </VABadge>
                          </div>
                        </div>
                        <p className="mt-2 text-xs text-va-text2">
                          {frameworkName(eng.framework_id)}
                        </p>
                        <p className="mt-1 text-xs text-va-muted">
                          {eng.period_start} &mdash; {eng.period_end}
                        </p>
                        {eng.status !== "setup" && (
                          <p className="mt-2 text-xs font-medium text-va-blue">
                            {eng.status === "published" ? "View Outputs" : "Edit Sections"} &rarr;
                          </p>
                        )}
                      </VACard>
                    </Link>
                  ))}
                </div>
              )}

              {/* Total count footer */}
              <p className="mt-4 text-xs text-va-muted">
                Showing {filtered.length} of {total} engagement
                {total !== 1 ? "s" : ""}
              </p>
            </>
          )}
        </>
      )}

      {/* ---------------------------------------------------------------- */}
      {/*  Create engagement dialog                                        */}
      {/* ---------------------------------------------------------------- */}
      {showCreate && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={() => setShowCreate(false)}
        >
          <form
            ref={createFormRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="afs-create-title"
            aria-describedby="afs-create-desc"
            onSubmit={(e) => {
              e.preventDefault();
              handleCreate();
            }}
            onClick={(e) => e.stopPropagation()}
            onKeyDown={handleCreateKeyDown}
            className="mx-4 w-full max-w-md rounded-va-lg border border-va-border bg-va-panel p-6 shadow-va-md"
          >
            <h3 id="afs-create-title" className="text-lg font-semibold text-va-text">
              New AFS Engagement
            </h3>
            <p id="afs-create-desc" className="mt-2 text-sm text-va-text2">
              Create an engagement to start generating financial statements.
            </p>

            <div className="mt-4 space-y-3">
              {/* Entity name */}
              <div>
                <label htmlFor="afs-entity" className="mb-1 block text-sm font-medium text-va-text">
                  Entity Name
                </label>
                <VAInput
                  id="afs-entity"
                  value={entityName}
                  onChange={(e) => { setEntityName(e.target.value); setFormErrors((p) => ({ ...p, entityName: "" })); }}
                  placeholder="e.g. Acme Holdings (Pty) Ltd"
                  error={formErrors.entityName}
                />
              </div>

              {/* Framework */}
              <div>
                <label htmlFor="afs-framework" className="mb-1 block text-sm font-medium text-va-text">
                  Accounting Framework
                </label>
                <VASelect
                  id="afs-framework"
                  value={frameworkId}
                  onChange={(e) => { setFrameworkId(e.target.value); setFormErrors((p) => ({ ...p, frameworkId: "" })); }}
                  error={formErrors.frameworkId}
                >
                  <option value="">Select framework...</option>
                  {frameworks.map((fw) => (
                    <option key={fw.framework_id} value={fw.framework_id}>
                      {fw.name}
                    </option>
                  ))}
                </VASelect>
              </div>

              {/* Period start */}
              <div>
                <label htmlFor="afs-start" className="mb-1 block text-sm font-medium text-va-text">
                  Period Start
                </label>
                <VAInput
                  id="afs-start"
                  type="date"
                  value={periodStart}
                  onChange={(e) => { setPeriodStart(e.target.value); setFormErrors((p) => ({ ...p, periodStart: "" })); }}
                  error={formErrors.periodStart}
                />
              </div>

              {/* Period end */}
              <div>
                <label htmlFor="afs-end" className="mb-1 block text-sm font-medium text-va-text">
                  Period End
                </label>
                <VAInput
                  id="afs-end"
                  type="date"
                  value={periodEnd}
                  onChange={(e) => { setPeriodEnd(e.target.value); setFormErrors((p) => ({ ...p, periodEnd: "" })); }}
                  error={formErrors.periodEnd}
                />
              </div>

              {/* Prior engagement (optional) */}
              <div className="sm:col-span-2">
                <label className="mb-1 block text-sm font-medium text-va-text">
                  Prior Engagement (optional)
                </label>
                <VASelect
                  value={priorEngagementId}
                  onChange={(e) => setPriorEngagementId(e.target.value)}
                >
                  <option value="">None (fresh engagement)</option>
                  {engagements
                    .filter(
                      (e) =>
                        e.status === "approved" || e.status === "published",
                    )
                    .map((e) => (
                      <option
                        key={e.engagement_id}
                        value={e.engagement_id}
                      >
                        {e.entity_name} ({e.period_start} &ndash;{" "}
                        {e.period_end})
                      </option>
                    ))}
                </VASelect>
                <p className="mt-1 text-xs text-va-muted">
                  Link to a prior period to enable roll-forward of sections
                  and comparatives.
                </p>
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-3">
              <VAButton
                type="button"
                variant="secondary"
                onClick={() => setShowCreate(false)}
              >
                Cancel
              </VAButton>
              <VAButton type="submit" variant="primary" loading={creating}>
                {creating ? "Creating..." : "Create Engagement"}
              </VAButton>
            </div>
          </form>
        </div>
      )}
    </main>
  );
}
