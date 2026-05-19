"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Link2,
  RefreshCw,
} from "lucide-react";

import { Eyebrow } from "@/components/atoms/eyebrow";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { Spinner } from "@/components/feedback/spinner";
import { ApiError } from "@/lib/api/client";
import { researchEndpoints } from "@/lib/api/endpoints";
import { qk } from "@/lib/api/query-keys";
import { fmtDateTime } from "@/lib/format";
import type { DownstreamPayload } from "@/types/api";

interface Props {
  caseId: number;
}

const SIGNAL_LABEL: Record<string, string> = {
  binding_support: "Binding support",
  persuasive_support: "Persuasive support",
  jurisdiction_coverage: "Jurisdiction coverage",
  recency_score: "Recency",
  outcome_alignment: "Outcome alignment",
  issue_coverage: "Issue coverage",
};

/**
 * Connections tab — preview of the DownstreamPayload that Packages 3/4/5
 * consume. Shows top authorities, case-strength signals (six normalised
 * scores), unresolved issues, and the source counts. A "Rebuild" button
 * recomputes the payload from current session + corpus state.
 */
export function ResearchConnections({ caseId }: Props) {
  const qc = useQueryClient();

  const q = useQuery({
    queryKey: qk.researchDownstream(caseId),
    queryFn: () => researchEndpoints.getDownstream(caseId),
    retry: false,
  });

  const build = useMutation({
    mutationFn: () => researchEndpoints.buildDownstream(caseId),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.researchDownstream(caseId) }),
  });

  if (q.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-ink-mute">
        <Spinner /> Loading downstream payload…
      </div>
    );
  }
  if (q.isError) {
    if (q.error instanceof ApiError && q.error.status === 409) {
      return (
        <EmptyState
          title="Downstream payload not built yet"
          description="This is the JSON contract consumed by Packages 3 (Simulation), 4 (Copilot), and 5 (Final Report). Build it now to see what each downstream package would see right now."
          icon={<Link2 className="h-5 w-5" />}
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
    <div className="space-y-5">
      <section className="surface flex flex-wrap items-center justify-between gap-3 p-5">
        <div>
          <Eyebrow>Downstream payload</Eyebrow>
          <div className="mt-1 font-mono text-[0.7rem] text-ink-mute">
            Built {fmtDateTime(payload.generated_at)} · {payload.session_count} session
            {payload.session_count === 1 ? "" : "s"} · {payload.corpus_doc_count} docs
          </div>
        </div>
        <Button
          variant="primary"
          size="sm"
          onClick={() => build.mutate()}
          disabled={build.isPending}
        >
          {build.isPending ? <Spinner /> : <RefreshCw className="h-3.5 w-3.5" />}
          Rebuild
        </Button>
      </section>

      <Signals payload={payload} />
      <TopAuthorities payload={payload} />
      <UnresolvedIssues payload={payload} />
      <DownstreamConsumers />
    </div>
  );
}

function Signals({ payload }: { payload: DownstreamPayload }) {
  const entries = Object.entries(payload.case_strength_signals);
  if (entries.length === 0) {
    return (
      <section className="surface p-5">
        <Eyebrow>Case-strength signals</Eyebrow>
        <p className="mt-2 text-sm text-ink-mute">
          No signals computed — ingest a precedent first.
        </p>
      </section>
    );
  }
  return (
    <section>
      <Eyebrow>Case-strength signals</Eyebrow>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {entries.map(([k, v]) => (
          <div key={k} className="surface flex flex-col gap-1.5 p-4">
            <span className="font-mono text-[0.6rem] uppercase tracking-[0.16em] text-ink-mute">
              {SIGNAL_LABEL[k] ?? k.replace(/_/g, " ")}
            </span>
            <div className="flex items-baseline gap-2">
              <span className="font-display text-2xl text-ink">
                {(v * 100).toFixed(0)}
              </span>
              <span className="text-[0.7rem] text-ink-mute">/ 100</span>
            </div>
            <div className="mt-1 h-1 w-full rounded-full bg-rule-soft">
              <div
                className="h-1 rounded-full bg-accent"
                style={{ width: `${Math.max(0, Math.min(1, v)) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function TopAuthorities({ payload }: { payload: DownstreamPayload }) {
  if (payload.top_authorities.length === 0) {
    return (
      <section className="surface p-5">
        <Eyebrow>Top authorities</Eyebrow>
        <p className="mt-2 text-sm text-ink-mute">
          Save research sessions first — the strongest authorities they cite
          surface here for the downstream packages.
        </p>
      </section>
    );
  }
  return (
    <section className="surface p-5">
      <Eyebrow>Top authorities ({payload.top_authorities.length})</Eyebrow>
      <ul className="mt-3 space-y-2">
        {payload.top_authorities.map((a, i) => (
          <li
            key={`${a.document_id}-${i}`}
            className="rounded border border-rule-soft bg-parchment-soft/40 p-3"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-[0.62rem] text-ink-mute">#{i + 1}</span>
              <span className="truncate font-display text-sm text-ink">
                {a.title || "(untitled)"}
              </span>
              <Badge tone="accent" className="ml-auto">
                score {a.similarity_score.toFixed(2)}
              </Badge>
            </div>
            <div className="mt-1 flex flex-wrap items-baseline gap-2 font-mono text-[0.62rem] text-ink-mute">
              {a.citation && <span>{a.citation}</span>}
              {a.court && <span>· {a.court}</span>}
              {a.date_decided && <span>· {a.date_decided}</span>}
              <span className="ml-auto text-accent">{a.top_chunk_citation_label}</span>
            </div>
            {a.relevance_summary && (
              <p className="mt-1 text-xs text-ink-soft">{a.relevance_summary}</p>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function UnresolvedIssues({ payload }: { payload: DownstreamPayload }) {
  if (payload.unresolved_legal_issues.length === 0) {
    return (
      <section className="surface p-5">
        <Eyebrow>Unresolved legal issues</Eyebrow>
        <p className="mt-2 text-sm text-ink-mute">
          Nothing flagged. As sessions are saved with `unresolved_questions`,
          they accumulate here for the Final Report to pick up.
        </p>
      </section>
    );
  }
  return (
    <section className="surface p-5">
      <Eyebrow>
        Unresolved legal issues ({payload.unresolved_legal_issues.length})
      </Eyebrow>
      <ul className="mt-3 space-y-1.5 text-sm text-ink-soft">
        {payload.unresolved_legal_issues.map((q, i) => (
          <li key={i} className="flex items-start gap-2">
            <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-accent" />
            {q}
          </li>
        ))}
      </ul>
    </section>
  );
}

function DownstreamConsumers() {
  return (
    <section className="surface p-5">
      <Eyebrow>Consumed by</Eyebrow>
      <div className="mt-3 grid gap-3 sm:grid-cols-3">
        {[
          [
            "Package 3 — Simulation",
            "Top authorities + timeline + signals seed the case-study sim's facts and adversary model.",
          ],
          [
            "Package 4 — Copilot drafting",
            "Strongest authorities + citation labels feed the brief drafter; unresolved issues become open TODOs.",
          ],
          [
            "Package 5 — Final report",
            "Aggregated signals + open issues + authority chain plug into the readiness scorecard.",
          ],
        ].map(([name, blurb]) => (
          <div
            key={name}
            className="rounded border border-rule-soft bg-parchment-soft/40 p-3"
          >
            <div className="font-display text-sm text-ink">{name}</div>
            <p className="mt-1 text-xs text-ink-soft">{blurb}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
