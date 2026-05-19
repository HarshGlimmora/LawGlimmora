"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, RefreshCw } from "lucide-react";

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
 * Contradictions ledger.
 *
 * Reads /api/cases/{id}/evidence/contradictions (written to disk by the
 * FinalReport orchestrator). If the file does not exist yet, the user
 * can press "Compute now" to generate the report once — this triggers
 * the full orchestrator which is a few seconds with Vertex.
 */
export function ContradictionsLedger({ caseId }: Props) {
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: qk.evidenceContradictions(caseId),
    queryFn: () => evidenceEndpoints.listContradictions(caseId),
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
        <Spinner /> Loading contradictions…
      </div>
    );
  }
  if (q.isError) return <ErrorState onRetry={() => q.refetch()} />;

  const items = q.data ?? [];
  if (items.length === 0) {
    return (
      <EmptyState
        title="No contradictions on file"
        description="Glimmora detects contradictions while generating the final report. Run it now to compute the ledger."
        icon={<AlertTriangle className="h-5 w-5" />}
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
        <Eyebrow>Contradictions · {items.length}</Eyebrow>
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
        {items.map((c) => (
          <li key={c.id} className="surface p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Badge tone={SEVERITY_TONE[c.severity] ?? "default"}>{c.severity}</Badge>
                <Badge tone="outline">{c.kind}</Badge>
              </div>
              <span className="font-mono text-[0.62rem] text-ink-mute">{c.id}</span>
            </div>
            <p className="mt-3 font-display text-base text-ink">{c.summary}</p>
            {c.explanation && (
              <p className="mt-1.5 text-sm text-ink-soft">{c.explanation}</p>
            )}
            {c.references.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {c.references.map((r, i) => (
                  <span key={i} className="font-mono text-[0.62rem] text-accent">
                    {r}
                  </span>
                ))}
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
