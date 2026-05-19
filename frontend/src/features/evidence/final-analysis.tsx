"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileBarChart, RefreshCw } from "lucide-react";

import { Eyebrow } from "@/components/atoms/eyebrow";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { Spinner } from "@/components/feedback/spinner";
import { reportEndpoints } from "@/lib/api/endpoints";
import { qk } from "@/lib/api/query-keys";
import { fmtDateTime } from "@/lib/format";
import type { FinalReport, Severity } from "@/types/api";

interface Props {
  caseId: number;
}

const SCORE_LABEL: Record<string, string> = {
  evidence_strength_score: "Evidence strength",
  evidence_weakness_score: "Evidence weakness",
  completeness_score: "Completeness",
  contradiction_risk_score: "Contradiction risk",
  missing_evidence_risk_score: "Missing-evidence risk",
  timeline_integrity_score: "Timeline integrity",
  legal_basis_strength_score: "Legal-basis strength",
  readiness_score: "Readiness",
  pitch_success_estimate: "Pitch success",
};
// True when higher = better. Risk/weakness scores are lower-better.
const SCORE_HIGHER_BETTER: Record<string, boolean> = {
  evidence_strength_score: true,
  evidence_weakness_score: false,
  completeness_score: true,
  contradiction_risk_score: false,
  missing_evidence_risk_score: false,
  timeline_integrity_score: true,
  legal_basis_strength_score: true,
  readiness_score: true,
  pitch_success_estimate: true,
};

function ScoreTile({ name, value }: { name: string; value: number }) {
  const higherBetter = SCORE_HIGHER_BETTER[name] ?? true;
  // Healthy: >=70 for higher-better, <=30 for lower-better.
  // Caution: 40-69 / 31-60. Otherwise risk.
  const healthy = higherBetter ? value >= 70 : value <= 30;
  const caution = higherBetter ? value >= 40 && value < 70 : value > 30 && value <= 60;
  const tone = healthy ? "success" : caution ? "warning" : "danger";
  return (
    <div className="surface flex flex-col gap-1.5 p-4">
      <span className="font-mono text-[0.6rem] uppercase tracking-[0.16em] text-ink-mute">
        {SCORE_LABEL[name] ?? name}
      </span>
      <div className="flex items-baseline gap-2">
        <span className="font-display text-2xl text-ink">{value}</span>
        <span className="text-[0.7rem] text-ink-mute">/ 100</span>
        <Badge tone={tone as never} className="ml-auto">
          {higherBetter ? "higher better" : "lower better"}
        </Badge>
      </div>
    </div>
  );
}

const SEVERITY_TONE: Record<Severity, "default" | "warning" | "danger" | "accent"> = {
  low: "default",
  medium: "accent",
  high: "warning",
  critical: "danger",
};

const PRIORITY_TONE: Record<string, "default" | "warning" | "danger" | "accent"> = {
  low: "default",
  medium: "accent",
  high: "warning",
  critical: "danger",
};

/**
 * Final analysis dashboard.
 *
 * - GET /api/cases/{id}/report returns {report, dashboard}.
 * - If `report` is null, surface a "Generate" CTA that POSTs /report/generate.
 * - Once present: render the 9-score card, executive summary, strongest/
 *   weakest issues, contradictions, missing-evidence, recommendations,
 *   source map, and the final conclusion. Provide export buttons for
 *   JSON, TXT, and PDF — all served by the existing backend route.
 */
export function FinalAnalysis({ caseId }: Props) {
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: qk.report(caseId),
    queryFn: () => reportEndpoints.get(caseId),
  });

  const generate = useMutation({
    mutationFn: () => reportEndpoints.generate(caseId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.report(caseId) });
      qc.invalidateQueries({ queryKey: qk.evidenceContradictions(caseId) });
      qc.invalidateQueries({ queryKey: qk.evidenceMissing(caseId) });
    },
  });

  if (q.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-ink-mute">
        <Spinner /> Loading final report…
      </div>
    );
  }
  if (q.isError) return <ErrorState onRetry={() => q.refetch()} />;

  const report = q.data?.report as FinalReport | null | undefined;

  if (!report) {
    return (
      <EmptyState
        title="Final report not generated yet"
        description="Run the 14-step report orchestrator — scoring, recommendations, contradictions, missing-evidence, executive summary, and conclusion."
        icon={<FileBarChart className="h-5 w-5" />}
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
                <RefreshCw className="h-4 w-4" /> Generate now
              </>
            )}
          </Button>
        }
      />
    );
  }

  const exportLink = (fmt: "json" | "text" | "pdf") => reportEndpoints.exportUrl(caseId, fmt);

  return (
    <div className="space-y-6">
      <section className="surface flex flex-wrap items-center justify-between gap-3 p-5">
        <div>
          <Eyebrow>Final report</Eyebrow>
          <div className="mt-1 flex items-center gap-2 font-mono text-[0.7rem] text-ink-mute">
            <span>{report.report_id}</span>
            <span>·</span>
            <span>generated {fmtDateTime(report.generated_at)}</span>
            <Badge tone={report.narrative_source === "fallback" ? "warning" : "accent"}>
              narrative: {report.narrative_source}
            </Badge>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <a href={exportLink("json")} download>
            <Button variant="ghost" size="sm">
              <Download className="h-3.5 w-3.5" /> JSON
            </Button>
          </a>
          <a href={exportLink("text")} download>
            <Button variant="ghost" size="sm">
              <Download className="h-3.5 w-3.5" /> TXT
            </Button>
          </a>
          <a href={exportLink("pdf")} download>
            <Button variant="ghost" size="sm">
              <Download className="h-3.5 w-3.5" /> PDF
            </Button>
          </a>
          <Button
            variant="primary"
            size="sm"
            onClick={() => generate.mutate()}
            disabled={generate.isPending}
          >
            {generate.isPending ? <Spinner /> : <RefreshCw className="h-3.5 w-3.5" />}
            Regenerate
          </Button>
        </div>
      </section>

      <section>
        <Eyebrow>9-score readiness card</Eyebrow>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Object.entries(report.scores).map(([k, v]) => (
            <ScoreTile key={k} name={k} value={v as number} />
          ))}
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <article className="surface p-5">
          <Eyebrow>Strongest issue</Eyebrow>
          <p className="mt-2 font-display text-lg text-ink">
            {report.strongest_issue || "—"}
          </p>
          {report.strongest_points.length > 0 && (
            <ul className="mt-3 space-y-2 text-xs">
              {report.strongest_points.slice(0, 4).map((p, i) => (
                <li key={i} className="rounded border border-rule-soft bg-parchment-soft/40 p-2">
                  <div className="font-mono text-[0.62rem] text-accent">
                    {p.citation_label}
                  </div>
                  <p className="mt-1 line-clamp-3 text-ink-soft">“{p.snippet}”</p>
                </li>
              ))}
            </ul>
          )}
        </article>
        <article className="surface p-5">
          <Eyebrow>Weakest issue</Eyebrow>
          <p className="mt-2 font-display text-lg text-ink">
            {report.weakest_issue || "—"}
          </p>
          {report.weakest_points.length > 0 && (
            <ul className="mt-3 space-y-2 text-xs">
              {report.weakest_points.slice(0, 4).map((p, i) => (
                <li key={i} className="rounded border border-rule-soft bg-parchment-soft/40 p-2">
                  <div className="font-mono text-[0.62rem] text-accent">
                    {p.citation_label}
                  </div>
                  <p className="mt-1 line-clamp-3 text-ink-soft">“{p.snippet}”</p>
                </li>
              ))}
            </ul>
          )}
        </article>
      </section>

      <section className="surface p-5">
        <Eyebrow>Executive summary</Eyebrow>
        <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-ink-soft">
          {report.executive_summary || "—"}
        </p>
      </section>

      {report.contradiction_summary.length > 0 && (
        <section className="surface p-5">
          <Eyebrow>Contradictions ({report.contradiction_summary.length})</Eyebrow>
          <ul className="mt-3 space-y-2">
            {report.contradiction_summary.map((c) => (
              <li
                key={c.contradiction_id}
                className="rounded-md border border-rule-soft bg-parchment-soft/40 p-3"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={SEVERITY_TONE[c.severity] ?? "default"}>{c.severity}</Badge>
                  <Badge tone="outline">{c.kind}</Badge>
                </div>
                <p className="mt-2 text-sm text-ink">{c.summary}</p>
                {c.explanation && (
                  <p className="mt-1 text-xs text-ink-soft">{c.explanation}</p>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {report.missing_evidence_summary.length > 0 && (
        <section className="surface p-5">
          <Eyebrow>Missing evidence ({report.missing_evidence_summary.length})</Eyebrow>
          <ul className="mt-3 space-y-2">
            {report.missing_evidence_summary.map((m) => (
              <li
                key={m.missing_id}
                className="rounded-md border border-rule-soft bg-parchment-soft/40 p-3"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={SEVERITY_TONE[m.severity] ?? "default"}>{m.severity}</Badge>
                  <Badge tone="outline">{m.category}</Badge>
                </div>
                <p className="mt-2 text-sm text-ink">{m.why_it_matters}</p>
                <p className="mt-1 text-xs text-ink-soft">→ {m.recommendation}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {report.recommendations.length > 0 && (
        <section className="surface p-5">
          <Eyebrow>Recommendations ({report.recommendations.length})</Eyebrow>
          <ul className="mt-3 divide-y divide-rule-soft">
            {report.recommendations.map((r) => (
              <li key={r.recommendation_id} className="flex flex-col gap-1 py-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={PRIORITY_TONE[r.priority] ?? "default"}>{r.priority}</Badge>
                  <Badge tone="outline">{r.action_type}</Badge>
                  <span className="font-display text-sm text-ink">{r.title}</span>
                </div>
                <p className="text-xs text-ink-soft">{r.description}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {report.source_map.length > 0 && (
        <section className="surface p-5">
          <Eyebrow>Source map ({report.source_map.length})</Eyebrow>
          <ul className="mt-3 grid gap-2 sm:grid-cols-2">
            {report.source_map.map((s, i) => (
              <li
                key={i}
                className="rounded-md border border-rule-soft bg-parchment-soft/40 p-3 text-xs"
              >
                <div className="font-mono text-[0.62rem] text-accent">{s.label}</div>
                <p className="mt-1 text-ink-soft">{s.reason_used}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {report.final_conclusion && (
        <section className="surface p-5">
          <Eyebrow>Final conclusion</Eyebrow>
          <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-ink-soft">
            {report.final_conclusion}
          </p>
        </section>
      )}
    </div>
  );
}
