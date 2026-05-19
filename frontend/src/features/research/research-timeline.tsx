"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, RefreshCw } from "lucide-react";
import { useMemo } from "react";

import { Eyebrow } from "@/components/atoms/eyebrow";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { Spinner } from "@/components/feedback/spinner";
import { ApiError } from "@/lib/api/client";
import { researchEndpoints } from "@/lib/api/endpoints";
import { qk } from "@/lib/api/query-keys";
import { fmtDate } from "@/lib/format";
import type { DownstreamTimelineItem } from "@/types/api";

interface Props {
  caseId: number;
}

/**
 * Timeline tab.
 *
 * Pulls the DownstreamPayload (the same artifact Packages 3/4/5 read)
 * and renders its `timeline_items` chronologically — newest first. Each
 * item is anchored to the precedent it came from.
 *
 * The payload is built by POST /downstream/build, and cached by the
 * backend until the next build. If the case never built one, we show a
 * "Build now" CTA that triggers the orchestrator end-to-end.
 */
export function ResearchTimeline({ caseId }: Props) {
  const qc = useQueryClient();

  const q = useQuery({
    queryKey: qk.researchDownstream(caseId),
    queryFn: () => researchEndpoints.getDownstream(caseId),
    // 409 (downstream_not_built) is a normal first-time state — treat as null.
    retry: false,
  });

  const build = useMutation({
    mutationFn: () => researchEndpoints.buildDownstream(caseId),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.researchDownstream(caseId) }),
  });

  if (q.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-ink-mute">
        <Spinner /> Loading timeline…
      </div>
    );
  }

  // 409 not-built → ApiError with status 409; surface a build CTA.
  if (q.isError) {
    const err = q.error;
    if (err instanceof ApiError && err.status === 409) {
      return (
        <EmptyState
          title="Timeline not built yet"
          description="Build the downstream payload — it aggregates timeline events, top authorities, and case-strength signals across every research session in this case."
          icon={<CalendarClock className="h-5 w-5" />}
          action={
            <Button
              variant="primary"
              onClick={() => build.mutate()}
              disabled={build.isPending}
            >
              {build.isPending ? <Spinner /> : <RefreshCw className="h-4 w-4" />}
              Build now
            </Button>
          }
        />
      );
    }
    return <ErrorState onRetry={() => q.refetch()} />;
  }

  const payload = q.data!;
  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <Eyebrow>Timeline · {payload.timeline_items.length} events</Eyebrow>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => build.mutate()}
          disabled={build.isPending}
        >
          {build.isPending ? <Spinner /> : <RefreshCw className="h-3.5 w-3.5" />}
          Rebuild
        </Button>
      </header>

      {payload.timeline_items.length === 0 ? (
        <EmptyState
          title="No dated events on file"
          description="Decision dates appear here once corpus documents have `date_decided` set — either via Gemini metadata enrichment or the regex fallback."
          icon={<CalendarClock className="h-5 w-5" />}
        />
      ) : (
        <TimelineList items={payload.timeline_items} />
      )}
    </div>
  );
}

function TimelineList({ items }: { items: DownstreamTimelineItem[] }) {
  // Group by year for a scannable rail.
  const groups = useMemo(() => {
    const byYear = new Map<string, DownstreamTimelineItem[]>();
    for (const it of items) {
      const year = (it.date || "").slice(0, 4) || "—";
      const list = byYear.get(year) ?? [];
      list.push(it);
      byYear.set(year, list);
    }
    return Array.from(byYear.entries()).sort((a, b) => b[0].localeCompare(a[0]));
  }, [items]);

  return (
    <ol className="space-y-6">
      {groups.map(([year, group]) => (
        <li key={year}>
          <header className="flex items-center gap-3">
            <span className="font-display text-2xl text-ink">{year}</span>
            <span className="font-mono text-[0.62rem] text-ink-mute">
              {group.length} {group.length === 1 ? "event" : "events"}
            </span>
          </header>
          <ul className="mt-2 space-y-2 border-l border-rule pl-4">
            {group.map((it, i) => (
              <li
                key={`${it.source_document_id}-${i}`}
                className="surface px-4 py-3 text-sm"
              >
                <div className="flex flex-wrap items-baseline gap-2">
                  <Badge tone="accent">{fmtDate(it.date)}</Badge>
                  <span className="font-display text-ink">{it.event}</span>
                </div>
                <div className="mt-1 font-mono text-[0.62rem] text-ink-mute">
                  {it.source_citation_label}
                </div>
              </li>
            ))}
          </ul>
        </li>
      ))}
    </ol>
  );
}
