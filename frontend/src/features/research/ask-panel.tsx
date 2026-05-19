"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  ChevronDown,
  ChevronRight,
  Download,
  Save,
  ScrollText,
  Sparkles,
} from "lucide-react";
import { useState } from "react";

import { Eyebrow } from "@/components/atoms/eyebrow";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ErrorState } from "@/components/feedback/error-state";
import { Spinner } from "@/components/feedback/spinner";
import { ApiError } from "@/lib/api/client";
import { researchEndpoints } from "@/lib/api/endpoints";
import { qk } from "@/lib/api/query-keys";
import { fmtDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import type {
  RankedHit,
  ResearchAnswer,
  ResearchQueryType,
  ResearchScoreBreakdown,
  ResearchSearchBody,
  SupportingAuthority,
} from "@/types/api";

interface Props {
  caseId: number;
}

const SCORE_LABEL: Record<keyof ResearchScoreBreakdown, string> = {
  jurisdiction_match: "jurisdiction",
  court_rank: "court rank",
  issue_overlap: "issue overlap",
  fact_similarity: "fact match",
  outcome_alignment: "outcome",
  recency: "recency",
  authority_level: "authority",
  doctrinal_relevance: "doctrine",
};

const BINDING_TONE: Record<string, "success" | "accent" | "default"> = {
  binding: "success",
  persuasive: "accent",
  informational: "default",
};

/**
 * Research Engine — Ask tab.
 *
 * Lays out the full lawyer flow on one canvas:
 *   1. Query box + filters (jurisdiction / courts / issues / practice areas /
 *      date range / query type / top_k).
 *   2. Calls POST /research → renders ResearchAnswer (top answer, applicable
 *      law, strongest authorities, distinguishable authorities, excerpts,
 *      risk flags, next steps).
 *   3. Right rail: 9-factor rerank breakdown for the top hit + retrieval
 *      summary (collapsible "debug" panel).
 *   4. Save-session button persists the round-trip with optional pinned
 *      docs + unresolved questions (free-text).
 *
 * Every claim in the answer is bound to a citation_label that resolves
 * back to a chunk_id — no synthesised text is shown without an excerpt.
 */
export function ResearchAskPanel({ caseId }: Props) {
  const qc = useQueryClient();

  // ── query state ────────────────────────────────────────────────────
  const [queryText, setQueryText] = useState("");
  const [queryType, setQueryType] = useState<ResearchQueryType>("legal_question");
  const [jurisdiction, setJurisdiction] = useState("");
  const [courts, setCourts] = useState("");
  const [issueTags, setIssueTags] = useState("");
  const [practiceAreas, setPracticeAreas] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [topK, setTopK] = useState(15);

  // ── result state ───────────────────────────────────────────────────
  const [answer, setAnswer] = useState<ResearchAnswer | null>(null);
  const [ranked, setRanked] = useState<RankedHit[]>([]);
  const [serverError, setServerError] = useState<string | null>(null);
  const [showDebug, setShowDebug] = useState(false);

  // ── save-session state ─────────────────────────────────────────────
  const [pinned, setPinned] = useState<Set<string>>(new Set());
  const [unresolved, setUnresolved] = useState("");
  const [notes, setNotes] = useState("");
  const [savedSessionId, setSavedSessionId] = useState<string | null>(null);

  const buildBody = (): ResearchSearchBody => ({
    query_text: queryText.trim(),
    query_type: queryType,
    jurisdiction_filter: jurisdiction.trim() || null,
    court_filter: parseList(courts),
    issue_filter: parseList(issueTags),
    practice_area_filter: parseList(practiceAreas),
    date_from: dateFrom || null,
    date_to: dateTo || null,
    top_k: topK,
  });

  const ask = useMutation({
    mutationFn: () => researchEndpoints.run(caseId, buildBody()),
    onMutate: () => {
      setServerError(null);
      setSavedSessionId(null);
    },
    onSuccess: (resp) => {
      setAnswer(resp.answer);
      setRanked(resp.ranked);
      setPinned(new Set());
    },
    onError: (err) =>
      setServerError(
        err instanceof ApiError ? err.message : "Research call failed.",
      ),
  });

  const save = useMutation({
    mutationFn: () => {
      if (!answer) throw new Error("No answer to save.");
      return researchEndpoints.saveSession(caseId, {
        answer_id: answer.answer_id,
        query_text: queryText.trim(),
        query_type: queryType,
        ranked_hits: ranked,
        answer,
        user_notes: notes.trim() || undefined,
        pinned_document_ids: Array.from(pinned),
        unresolved_questions: parseList(unresolved, "\n"),
      });
    },
    onSuccess: (resp) => {
      setSavedSessionId(resp.session_id);
      qc.invalidateQueries({ queryKey: qk.researchSessions(caseId) });
    },
  });

  const togglePin = (documentId: string) => {
    setPinned((prev) => {
      const next = new Set(prev);
      if (next.has(documentId)) next.delete(documentId);
      else next.add(documentId);
      return next;
    });
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
      <div className="space-y-6">
        {/* Query + filters */}
        <section className="surface p-5 space-y-4">
          <Eyebrow>Research query</Eyebrow>
          <Textarea
            rows={3}
            value={queryText}
            onChange={(e) => setQueryText(e.target.value)}
            placeholder="e.g. When is specific performance available for immovable property under Section 10 of the Specific Relief Act?"
            disabled={ask.isPending}
          />
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label>Query type</Label>
              <Select
                value={queryType}
                onValueChange={(v) => setQueryType(v as ResearchQueryType)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="legal_question">Legal question</SelectItem>
                  <SelectItem value="fact_pattern">Fact pattern</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="topk">Top K</Label>
              <Input
                id="topk"
                type="number"
                min={1}
                max={100}
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value || 15))}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="jurisdiction">Jurisdiction</Label>
              <Input
                id="jurisdiction"
                placeholder="e.g. India"
                value={jurisdiction}
                onChange={(e) => setJurisdiction(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="courts">Court filter (comma-sep)</Label>
              <Input
                id="courts"
                placeholder="Supreme Court, Delhi High Court"
                value={courts}
                onChange={(e) => setCourts(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="issues">Issue tags (comma-sep)</Label>
              <Input
                id="issues"
                placeholder="specific performance, section 10"
                value={issueTags}
                onChange={(e) => setIssueTags(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="practice">Practice areas (comma-sep)</Label>
              <Input
                id="practice"
                placeholder="contract, specific relief"
                value={practiceAreas}
                onChange={(e) => setPracticeAreas(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="date-from">Decided after</Label>
              <Input
                id="date-from"
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="date-to">Decided before</Label>
              <Input
                id="date-to"
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
              />
            </div>
          </div>
          <div className="flex items-center justify-end gap-3">
            {serverError && (
              <span className="text-xs text-danger">{serverError}</span>
            )}
            <Button
              variant="primary"
              disabled={ask.isPending || queryText.trim().length === 0}
              onClick={() => ask.mutate()}
            >
              {ask.isPending ? <Spinner /> : <Sparkles className="h-4 w-4" />}
              Run research
            </Button>
          </div>
        </section>

        {ask.isError && !serverError && <ErrorState onRetry={() => ask.mutate()} />}

        {answer && <AnswerPanel answer={answer} pinned={pinned} togglePin={togglePin} />}

        {answer && (
          <section className="surface p-5 space-y-3">
            <Eyebrow>Save research session</Eyebrow>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="unresolved">Unresolved questions (one per line)</Label>
                <Textarea
                  id="unresolved"
                  rows={3}
                  value={unresolved}
                  onChange={(e) => setUnresolved(e.target.value)}
                  placeholder="e.g. Effect of 2018 amendment on Section 10"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="notes">Notes</Label>
                <Textarea
                  id="notes"
                  rows={3}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Cite first; check for overruling."
                />
              </div>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="text-xs text-ink-mute">
                Pinned: {pinned.size} {pinned.size === 1 ? "doc" : "docs"}
                {savedSessionId && (
                  <span className="ml-2 text-success">· saved {savedSessionId}</span>
                )}
              </div>
              <Button
                variant="primary"
                disabled={save.isPending}
                onClick={() => save.mutate()}
              >
                {save.isPending ? <Spinner /> : <Save className="h-4 w-4" />}
                Save to research memory
              </Button>
            </div>
          </section>
        )}
      </div>

      {/* Right rail: retrieval + rerank breakdown */}
      <aside className="space-y-4">
        <section className="surface p-5">
          <Eyebrow>Retrieval summary</Eyebrow>
          {!answer && (
            <p className="mt-3 text-sm text-ink-mute">
              Run a query — this panel shows the BM25 + multi-factor reranker
              decisions for every hit.
            </p>
          )}
          {answer && (
            <dl className="mt-3 space-y-2 text-xs">
              {Object.entries(answer.retrieval_summary).map(([k, v]) => (
                <div key={k} className="flex items-baseline justify-between">
                  <dt className="font-mono text-[0.62rem] uppercase tracking-[0.16em] text-ink-mute">
                    {k.replace(/_/g, " ")}
                  </dt>
                  <dd className="font-mono text-ink">{v}</dd>
                </div>
              ))}
              <div className="flex items-baseline justify-between">
                <dt className="font-mono text-[0.62rem] uppercase tracking-[0.16em] text-ink-mute">
                  source
                </dt>
                <dd>
                  <Badge
                    tone={answer.synthesis_source === "fallback" ? "warning" : "accent"}
                  >
                    {answer.synthesis_source}
                  </Badge>
                </dd>
              </div>
              <div className="flex items-baseline justify-between">
                <dt className="font-mono text-[0.62rem] uppercase tracking-[0.16em] text-ink-mute">
                  confidence
                </dt>
                <dd className="font-mono text-ink">
                  {(answer.confidence * 100).toFixed(0)}%
                </dd>
              </div>
              <div className="flex items-baseline justify-between">
                <dt className="font-mono text-[0.62rem] uppercase tracking-[0.16em] text-ink-mute">
                  generated
                </dt>
                <dd className="text-ink-soft">{fmtDateTime(answer.generated_at)}</dd>
              </div>
            </dl>
          )}
        </section>

        {ranked.length > 0 && (
          <section className="surface p-5">
            <button
              type="button"
              onClick={() => setShowDebug((s) => !s)}
              className="flex w-full items-center justify-between"
            >
              <Eyebrow>Reranker breakdown ({ranked.length})</Eyebrow>
              {showDebug ? (
                <ChevronDown className="h-3.5 w-3.5 text-ink-mute" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5 text-ink-mute" />
              )}
            </button>
            {showDebug && (
              <ol className="mt-3 space-y-3 text-xs">
                {ranked.map((r, i) => (
                  <li
                    key={r.chunk_id}
                    className="rounded border border-rule-soft bg-parchment-soft/40 p-3"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-[0.62rem] text-ink-mute">
                        #{i + 1}
                      </span>
                      <span className="truncate font-display text-sm text-ink">
                        {r.document_title || r.document_id}
                      </span>
                      <Badge
                        tone={BINDING_TONE[r.binding_level] ?? "default"}
                        className="ml-auto"
                      >
                        {r.binding_level}
                      </Badge>
                    </div>
                    <div className="mt-1 font-mono text-[0.62rem] text-accent">
                      {r.citation_label}
                    </div>
                    <div className="mt-2 grid grid-cols-4 gap-1.5">
                      {(
                        Object.entries(r.breakdown) as [
                          keyof ResearchScoreBreakdown,
                          number,
                        ][]
                      ).map(([k, v]) => (
                        <div
                          key={k}
                          className="flex flex-col rounded border border-rule-soft bg-card px-1.5 py-1"
                        >
                          <span className="font-mono text-[0.55rem] uppercase tracking-[0.14em] text-ink-faint">
                            {SCORE_LABEL[k]}
                          </span>
                          <span className="font-mono text-[0.7rem] text-ink">
                            {v.toFixed(2)}
                          </span>
                        </div>
                      ))}
                    </div>
                    <div className="mt-2 font-mono text-[0.7rem] text-ink-soft">
                      final = {r.final_score.toFixed(3)}
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </section>
        )}
      </aside>
    </div>
  );
}

// ─── inner: answer panel ──────────────────────────────────────────────

function AnswerPanel({
  answer,
  pinned,
  togglePin,
}: {
  answer: ResearchAnswer;
  pinned: Set<string>;
  togglePin: (id: string) => void;
}) {
  const exportLink = () => {
    // The answer is in-memory before it's saved as a session, so we can't
    // /export it yet. Once the user clicks "Save to research memory" the
    // Sessions tab provides export buttons. This button stays inert here.
    return undefined;
  };
  void exportLink;

  return (
    <article className="surface p-5 space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <Eyebrow>Answer</Eyebrow>
        <Badge tone={answer.synthesis_source === "fallback" ? "warning" : "accent"}>
          {answer.synthesis_source}
        </Badge>
      </header>

      <div>
        <h3 className="font-display text-lg text-ink">Top answer</h3>
        <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-ink-soft">
          {answer.top_answer || "(empty)"}
        </p>
      </div>

      {answer.applicable_law.length > 0 && (
        <div>
          <Eyebrow>Applicable law</Eyebrow>
          <ul className="mt-2 space-y-1 text-sm text-ink-soft">
            {answer.applicable_law.map((l, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-accent" />
                {l}
              </li>
            ))}
          </ul>
        </div>
      )}

      <AuthorityList
        title="Strongest authorities"
        items={answer.strongest_authorities}
        pinned={pinned}
        togglePin={togglePin}
        tone="success"
      />

      {answer.distinguishable_authorities.length > 0 && (
        <AuthorityList
          title="Distinguishable / weaker"
          items={answer.distinguishable_authorities}
          pinned={pinned}
          togglePin={togglePin}
          tone="warning"
        />
      )}

      {answer.excerpts.length > 0 && (
        <div>
          <Eyebrow>Excerpts ({answer.excerpts.length})</Eyebrow>
          <ul className="mt-2 space-y-2">
            {answer.excerpts.map((e, i) => (
              <li
                key={i}
                className="rounded border border-rule-soft bg-parchment-soft/40 p-3 text-xs"
              >
                <div className="font-mono text-[0.62rem] text-accent">
                  {e.citation_label}
                </div>
                <p className="mt-1 line-clamp-4 text-ink-soft">“{e.snippet}”</p>
              </li>
            ))}
          </ul>
        </div>
      )}

      {answer.risk_flags.length > 0 && (
        <div>
          <Eyebrow>Risk flags</Eyebrow>
          <ul className="mt-2 space-y-1 text-xs">
            {answer.risk_flags.map((r, i) => (
              <li key={i} className="text-warning">⚠︎ {r}</li>
            ))}
          </ul>
        </div>
      )}

      {answer.next_steps.length > 0 && (
        <div>
          <Eyebrow>Recommended next steps</Eyebrow>
          <ul className="mt-2 space-y-1 text-sm">
            {answer.next_steps.map((s, i) => (
              <li key={i} className="flex items-start gap-2 text-ink-soft">
                <ArrowRight className="mt-0.5 h-3.5 w-3.5 text-accent" />
                {s}
              </li>
            ))}
          </ul>
        </div>
      )}

      {answer.next_question && (
        <div className="rounded border border-accent/30 bg-accent-wash/60 p-3 text-sm text-ink">
          <span className="font-mono text-[0.62rem] uppercase tracking-[0.16em] text-accent">
            Suggested next question
          </span>
          <p className="mt-1.5">{answer.next_question}</p>
        </div>
      )}
    </article>
  );
}

function AuthorityList({
  title,
  items,
  pinned,
  togglePin,
  tone,
}: {
  title: string;
  items: SupportingAuthority[];
  pinned: Set<string>;
  togglePin: (id: string) => void;
  tone: "success" | "warning";
}) {
  if (items.length === 0) return null;
  return (
    <div>
      <Eyebrow>
        {title} ({items.length})
      </Eyebrow>
      <ul className="mt-2 space-y-2">
        {items.map((a) => {
          const isPinned = pinned.has(a.document_id);
          return (
            <li
              key={`${a.document_id}-${a.top_chunk_citation_label}`}
              className="rounded border border-rule-soft bg-parchment-soft/40 p-3"
            >
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={tone}>{a.tier}</Badge>
                <Badge tone={BINDING_TONE[a.binding_level] ?? "default"}>
                  {a.binding_level}
                </Badge>
                <span className="truncate font-display text-sm text-ink">
                  {a.title || "(untitled)"}
                </span>
                <button
                  type="button"
                  onClick={() => togglePin(a.document_id)}
                  className={cn(
                    "ml-auto rounded-full border px-2 py-0.5 text-[0.65rem] transition-colors",
                    isPinned
                      ? "border-accent bg-accent-wash text-accent"
                      : "border-rule bg-card text-ink-mute hover:border-accent/40",
                  )}
                >
                  {isPinned ? "Pinned" : "Pin"}
                </button>
              </div>
              <div className="mt-1 flex flex-wrap items-baseline gap-2 font-mono text-[0.62rem] text-ink-mute">
                {a.citation && <span>{a.citation}</span>}
                {a.court && <span>· {a.court}</span>}
                {a.date_decided && <span>· {a.date_decided}</span>}
                <span className="ml-auto text-accent">{a.top_chunk_citation_label}</span>
              </div>
              {a.relevance_summary && (
                <p className="mt-2 text-xs text-ink-soft">{a.relevance_summary}</p>
              )}
              {a.distinguishing_reason && (
                <p className="mt-1 text-xs text-warning">
                  Distinguishing: {a.distinguishing_reason}
                </p>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function parseList(raw: string, sep = ","): string[] {
  return raw
    .split(sep)
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

// Re-exported so the page can route the Download icon into the sessions
// tab as a hint to find the saved memo.
export const _kept = { ScrollText, Download };
