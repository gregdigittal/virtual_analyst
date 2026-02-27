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
  VASpinner,
  useToast,
} from "@/components/ui";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

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

  // Create dialog
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);

  // Create form fields
  const [entityName, setEntityName] = useState("");
  const [frameworkId, setFrameworkId] = useState("");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");

  /* ------------------------------------------------------------------ */
  /*  Data loading                                                       */
  /* ------------------------------------------------------------------ */
  useEffect(() => {
    let cancelled = false;
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
  }, [router]);

  /* ------------------------------------------------------------------ */
  /*  Create handler                                                     */
  /* ------------------------------------------------------------------ */
  async function handleCreate() {
    if (!tenantId || !entityName || !frameworkId || !periodStart || !periodEnd)
      return;
    setCreating(true);
    try {
      const eng = await api.afs.createEngagement(tenantId, {
        entity_name: entityName,
        framework_id: frameworkId,
        period_start: periodStart,
        period_end: periodEnd,
      });
      toast.success("Engagement created");
      setShowCreate(false);
      setEntityName("");
      setFrameworkId("");
      setPeriodStart("");
      setPeriodEnd("");
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
        <VAButton variant="primary" onClick={() => setShowCreate(true)}>
          New Engagement
        </VAButton>
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-20">
          <VASpinner />
        </div>
      )}

      {/* Error */}
      {!loading && error && (
        <VACard className="p-6">
          <p className="text-sm text-va-danger">{error}</p>
        </VACard>
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
                      className="group"
                    >
                      <VACard className="h-full p-5 transition-colors group-hover:border-va-blue/50">
                        <div className="flex items-start justify-between gap-2">
                          <h3 className="text-sm font-semibold text-va-text line-clamp-2">
                            {eng.entity_name}
                          </h3>
                          <VABadge variant={statusBadgeVariant(eng.status)}>
                            {eng.status}
                          </VABadge>
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleCreate();
            }}
            className="mx-4 w-full max-w-md rounded-va-lg border border-va-border bg-va-panel p-6 shadow-va-md"
          >
            <h3 className="text-lg font-semibold text-va-text">
              New AFS Engagement
            </h3>
            <p className="mt-2 text-sm text-va-text2">
              Create an engagement to start generating financial statements.
            </p>

            <div className="mt-4 space-y-3">
              {/* Entity name */}
              <div>
                <label className="mb-1 block text-sm font-medium text-va-text">
                  Entity Name
                </label>
                <VAInput
                  value={entityName}
                  onChange={(e) => setEntityName(e.target.value)}
                  placeholder="e.g. Acme Holdings (Pty) Ltd"
                  required
                />
              </div>

              {/* Framework */}
              <div>
                <label className="mb-1 block text-sm font-medium text-va-text">
                  Accounting Framework
                </label>
                <VASelect
                  value={frameworkId}
                  onChange={(e) => setFrameworkId(e.target.value)}
                  required
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
                <label className="mb-1 block text-sm font-medium text-va-text">
                  Period Start
                </label>
                <VAInput
                  type="date"
                  value={periodStart}
                  onChange={(e) => setPeriodStart(e.target.value)}
                  required
                />
              </div>

              {/* Period end */}
              <div>
                <label className="mb-1 block text-sm font-medium text-va-text">
                  Period End
                </label>
                <VAInput
                  type="date"
                  value={periodEnd}
                  onChange={(e) => setPeriodEnd(e.target.value)}
                  required
                />
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
              <VAButton type="submit" variant="primary" disabled={creating}>
                {creating ? "Creating..." : "Create Engagement"}
              </VAButton>
            </div>
          </form>
        </div>
      )}
    </main>
  );
}
