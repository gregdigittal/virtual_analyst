"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  api,
  type AFSOutput,
  type AFSEngagement,
  type AFSSection,
} from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import {
  VAButton,
  VACard,
  VABadge,
  VASpinner,
  VAEmptyState,
  useToast,
} from "@/components/ui";

/* ------------------------------------------------------------------ */
/*  Format card configuration                                         */
/* ------------------------------------------------------------------ */

const FORMAT_CARDS: {
  format: string;
  title: string;
  description: string;
}[] = [
  {
    format: "pdf",
    title: "PDF",
    description:
      "Print-ready HTML with cover page and table of contents",
  },
  {
    format: "docx",
    title: "Word Document",
    description:
      "Microsoft Word document with styled sections and tables",
  },
  {
    format: "ixbrl",
    title: "iXBRL",
    description:
      "Inline XBRL with IFRS/US GAAP taxonomy tags",
  },
];

/* ------------------------------------------------------------------ */
/*  Helpers                                                           */
/* ------------------------------------------------------------------ */

function formatFileSize(bytes: number | null): string {
  if (bytes === null || bytes === 0) return "--";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatBadgeVariant(
  format: string,
): "default" | "success" | "warning" | "danger" | "violet" {
  switch (format) {
    case "pdf":
      return "default";
    case "ixbrl":
      return "violet";
    default:
      return "default";
  }
}

function statusBadgeVariant(
  status: string,
): "default" | "success" | "warning" | "danger" | "violet" {
  switch (status) {
    case "generating":
      return "warning";
    case "ready":
      return "success";
    case "error":
      return "danger";
    default:
      return "default";
  }
}

/** Simple inline SVG document icon. */
function DocumentIcon({ className = "" }: { className?: string }) {
  return (
    <svg
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <polyline points="10 9 9 9 8 9" />
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/*  Page component                                                    */
/* ------------------------------------------------------------------ */

export default function AFSOutputPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const engagementId = params.id as string;

  const [tenantId, setTenantId] = useState<string | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [engagement, setEngagement] = useState<AFSEngagement | null>(null);
  const [sections, setSections] = useState<AFSSection[]>([]);
  const [outputs, setOutputs] = useState<AFSOutput[]>([]);
  const [loading, setLoading] = useState(true);
  const [generatingFormat, setGeneratingFormat] = useState<string | null>(null);

  const hasLockedSections = sections.some((s) => s.status === "locked");

  /* ---------------------------------------------------------------- */
  /*  Data loading                                                    */
  /* ---------------------------------------------------------------- */

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) {
        router.replace("/login");
        return;
      }
      api.setAccessToken(ctx.accessToken);
      if (!cancelled) {
        setTenantId(ctx.tenantId);
        setAccessToken(ctx.accessToken);
      }
      try {
        const [eng, secs, outs] = await Promise.all([
          api.afs.getEngagement(ctx.tenantId, engagementId),
          api.afs.listSections(ctx.tenantId, engagementId),
          api.afs.listOutputs(ctx.tenantId, engagementId),
        ]);
        if (!cancelled) {
          setEngagement(eng);
          setSections(secs.items ?? []);
          setOutputs(outs.items ?? []);
        }
      } catch {
        if (!cancelled) toast.error("Failed to load engagement");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [engagementId, router, toast]);

  /* ---------------------------------------------------------------- */
  /*  Generate handler                                                */
  /* ---------------------------------------------------------------- */

  async function handleGenerate(format: string) {
    if (!tenantId) return;
    setGeneratingFormat(format);
    try {
      const output = await api.afs.generateOutput(tenantId, engagementId, {
        format,
      });
      setOutputs((prev) => [output, ...prev]);
      toast.success(`${format.toUpperCase()} output generated`);
    } catch {
      toast.error(`Failed to generate ${format.toUpperCase()} output`);
    } finally {
      setGeneratingFormat(null);
    }
  }

  /* ---------------------------------------------------------------- */
  /*  Download handler                                                */
  /* ---------------------------------------------------------------- */

  async function handleDownload(output: AFSOutput) {
    if (!tenantId) return;
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL || ""}/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/outputs/${encodeURIComponent(output.output_id)}/download`,
        {
          headers: {
            "x-tenant-id": tenantId,
            ...(accessToken
              ? { Authorization: `Bearer ${accessToken}` }
              : {}),
          },
        },
      );
      if (!response.ok) throw new Error("Download failed");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = output.filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error("Failed to download output");
    }
  }

  /* ---------------------------------------------------------------- */
  /*  Loading state                                                   */
  /* ---------------------------------------------------------------- */

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <VASpinner />
      </div>
    );
  }

  /* ---------------------------------------------------------------- */
  /*  Render                                                          */
  /* ---------------------------------------------------------------- */

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-va-border px-6 py-3">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push(`/afs/${engagementId}/sections`)}
            className="text-va-text2 hover:text-va-text"
          >
            &larr;
          </button>
          <h1 className="text-lg font-semibold text-va-text">
            {engagement?.entity_name} — Output
          </h1>
        </div>
        <div className="flex gap-2">
          <VAButton
            variant="secondary"
            onClick={() => router.push(`/afs/${engagementId}/sections`)}
          >
            Sections
          </VAButton>
          <VAButton
            variant="secondary"
            onClick={() => router.push(`/afs/${engagementId}/tax`)}
          >
            Tax
          </VAButton>
          <VAButton
            variant="secondary"
            onClick={() => router.push(`/afs/${engagementId}/review`)}
          >
            Review
          </VAButton>
          <VAButton
            variant="secondary"
            onClick={() =>
              router.push(`/afs/${engagementId}/consolidation`)
            }
          >
            Consolidation
          </VAButton>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-5xl space-y-6">
          {/* Locked-sections warning */}
          {!hasLockedSections && (
            <div className="rounded-va-sm border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-300">
              No locked sections found. Lock sections in the Sections page
              before generating outputs.
            </div>
          )}

          {/* Generate section — format cards */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {FORMAT_CARDS.map((card) => (
              <VACard key={card.format} className="p-6 text-center">
                <DocumentIcon className="mx-auto mb-3 h-10 w-10 text-va-text2" />
                <h3 className="text-base font-semibold text-va-text">
                  {card.title}
                </h3>
                <p className="mt-1 text-sm text-va-text2">
                  {card.description}
                </p>
                <div className="mt-4">
                  {hasLockedSections ? (
                    <VAButton
                      variant="primary"
                      onClick={() => handleGenerate(card.format)}
                      disabled={generatingFormat !== null}
                    >
                      {generatingFormat === card.format ? (
                        <span className="inline-flex items-center gap-2">
                          <VASpinner />
                          Generating...
                        </span>
                      ) : (
                        `Generate ${card.title}`
                      )}
                    </VAButton>
                  ) : (
                    <p className="text-xs text-va-muted">
                      Lock sections to enable generation
                    </p>
                  )}
                </div>
              </VACard>
            ))}
          </div>

          {/* Generated outputs list */}
          <div>
            <h2 className="mb-4 text-lg font-semibold text-va-text">
              Generated Outputs
            </h2>

            {outputs.length === 0 ? (
              <VAEmptyState
                icon="file-text"
                title="No outputs generated yet"
                description="Generate your first output above."
              />
            ) : (
              <VACard className="overflow-x-auto p-0">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr>
                      <th className="border-b border-va-border px-4 py-2 font-medium text-va-text2">
                        Format
                      </th>
                      <th className="border-b border-va-border px-4 py-2 font-medium text-va-text2">
                        Filename
                      </th>
                      <th className="border-b border-va-border px-4 py-2 font-medium text-va-text2">
                        File Size
                      </th>
                      <th className="border-b border-va-border px-4 py-2 font-medium text-va-text2">
                        Generated
                      </th>
                      <th className="border-b border-va-border px-4 py-2 font-medium text-va-text2">
                        Status
                      </th>
                      <th className="border-b border-va-border px-4 py-2 font-medium text-va-text2">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {outputs.map((output) => (
                      <tr key={output.output_id}>
                        <td className="border-b border-va-border/50 px-4 py-2 text-va-text">
                          <VABadge variant={formatBadgeVariant(output.format)}>
                            {output.format.toUpperCase()}
                          </VABadge>
                        </td>
                        <td className="border-b border-va-border/50 px-4 py-2 text-va-text">
                          {output.filename}
                        </td>
                        <td className="border-b border-va-border/50 px-4 py-2 text-va-text">
                          {formatFileSize(output.file_size_bytes)}
                        </td>
                        <td className="border-b border-va-border/50 px-4 py-2 text-va-text">
                          {new Date(output.generated_at).toLocaleString()}
                        </td>
                        <td className="border-b border-va-border/50 px-4 py-2 text-va-text">
                          <VABadge variant={statusBadgeVariant(output.status)}>
                            {output.status}
                          </VABadge>
                        </td>
                        <td className="border-b border-va-border/50 px-4 py-2 text-va-text">
                          {output.status === "ready" ? (
                            <VAButton
                              variant="secondary"
                              onClick={() => handleDownload(output)}
                            >
                              Download
                            </VAButton>
                          ) : output.status === "error" ? (
                            <span
                              className="text-xs text-va-danger"
                              title={output.error_message ?? undefined}
                            >
                              {output.error_message ?? "Generation failed"}
                            </span>
                          ) : (
                            <span className="text-xs text-va-muted">--</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </VACard>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
