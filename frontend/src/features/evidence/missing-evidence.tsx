"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileQuestion, RefreshCw } from "lucide-react";

import { Eyebrow } from "@/components/atoms/eyebrow";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { Spinner } from "@/components/feedback/spinner";
import { evidenceEndpoints, reportEndpoints } from "@/lib/api/endpoints";
import { qk } from "@/lib/api/query-keys";
import type { Severity } from "@/types/api";

interface Props {
  caseId: number;
}

const SEVERITY_TONE: Record<Severity, "default" | "warning" | "danger" | "accent"> = {
  low: "default",
  medium: "accent",
  high: "warning",
  critical: "danger",
};

/**
 * Missing-evidence checklist.
 *
 * Mirrors the contradictions ledger: reads the disk artifact written by
 * the FinalReport orchestrator and offers a "compute now" button when
 * the ledger is empty.
 */
export function MissingEvidence({ caseId }: Props) {
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: qk.evidenceMissing(caseId),
    queryFn: () => evidenceEndpoints.listMissingEvidence(caseId),
  });

  const generate = useMutation({
    mutationFn: () => reportEndpoints.generate(caseId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.evidenceContradictions(caseId) });
      qc.invalidateQueries({ queryKey: qk.evidenceMissing(caseId) });
      qc.invalidateQueries({ queryKey: qk.report(caseId) });
    },
  });

  if (q.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-ink-mute">
        <Spinner /> Loading missing-evidence checklist…
      </div>
    );
  }
  if (q.isError) return <ErrorState onRetry={() => q.refetch()} />;

  const items = q.data ?? [];
  if (items.length === 0) {
    return (
      <EmptyState
        title="No missing-evidence items on file"
        description="Glimmora identifies expected-but-absent documents during final report generation. Run it now to populate the checklist."
        icon={<FileQuestion className="h-5 w-5" />}
        action={
          <Button
            variant="primary"
            onClick={() => generate.mutate()}
            disabled={generate.isPending}
          >
            {generate.isPending ? (
              <>
                <Spinner /> Generating…
              </>
            ) : (
              <>
                <RefreshCw className="h-4 w-4" /> Compute now
              </>
            )}
          </Button>
        }
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Eyebrow>Missing evidence · {items.length}</Eyebrow>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => generate.mutate()}
          disabled={generate.isPending}
        >
          {generate.isPending ? <Spinner /> : <RefreshCw className="h-3.5 w-3.5" />}
          Recompute
        </Button>
      </div>
      <ul className="space-y-3">
        {items.map((m) => (
          <li key={m.id} className="surface p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Badge tone={SEVERITY_TONE[m.severity] ?? "default"}>{m.severity}</Badge>
                <Badge tone="outline">{m.category}</Badge>
              </div>
              <span className="font-mono text-[0.62rem] text-ink-mute">{m.id}</span>
            </div>
            {m.why_it_matters && (
              <div className="mt-3">
                <div className="font-mono text-[0.62rem] uppercase tracking-[0.16em] text-ink-mute">
                  Why it matters
                </div>
                <p className="mt-0.5 text-sm text-ink">{m.why_it_matters}</p>
              </div>
            )}
            {m.recommendation && (
              <div className="mt-3">
                <div className="font-mono text-[0.62rem] uppercase tracking-[0.16em] text-ink-mute">
                  Recommendation
                </div>
                <p className="mt-0.5 text-sm text-ink-soft">{m.recommendation}</p>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
