"use client";

import { api, type ActivityItem } from "@/lib/api";
import { VASpinner } from "@/components/ui";
import { formatDateTime } from "@/lib/format";
import { useEffect, useState } from "react";

interface EntityTimelineProps {
  tenantId: string;
  resourceType: string;
  resourceId: string;
}

export function EntityTimeline({
  tenantId,
  resourceType,
  resourceId,
}: EntityTimelineProps) {
  const [items, setItems] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const res = await api.activity.list(tenantId, {
          resource_type: resourceType,
          resource_id: resourceId,
          limit: 50,
        });
        if (!cancelled) setItems(res.items ?? []);
      } catch (e) {
        if (!cancelled)
          setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [tenantId, resourceType, resourceId]);

  if (loading) return <VASpinner label="Loading history\u2026" />;

  if (error) {
    return (
      <p className="text-sm text-va-danger">{error}</p>
    );
  }

  if (items.length === 0) {
    return <p className="text-sm text-va-text2">No history yet.</p>;
  }

  return (
    <div className="relative space-y-4 pl-6">
      <div className="absolute left-[9px] top-2 bottom-2 w-px bg-va-border" />
      {items.map((item) => (
        <div key={item.id} className="relative flex items-start gap-3">
          <div
            className={`absolute left-[-15px] mt-1.5 h-2.5 w-2.5 rounded-full ring-2 ring-va-midnight ${
              item.type === "comment" ? "bg-va-blue" : "bg-va-violet"
            }`}
          />
          <div className="min-w-0 flex-1">
            <p className="text-sm text-va-text">{item.summary}</p>
            <div className="mt-0.5 flex items-center gap-2 text-xs text-va-text2">
              {item.user_id && (
                <span className="font-mono">{item.user_id.slice(0, 8)}</span>
              )}
              <span>{formatDateTime(item.timestamp)}</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
