"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bookmark,
  Download,
  ScrollText,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import { useEffect, useState } from "react";

import { Eyebrow } from "@/components/atoms/eyebrow";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { Spinner } from "@/components/feedback/spinner";
import { researchEndpoints } from "@/lib/api/endpoints";
import { qk } from "@/lib/api/query-keys";
import { fmtDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import type {
  ResearchFeedbackBody,
  ResearchSession,
  SupportingAuthority,
} from "@/types/api";

interface Props {
  caseId: number;
}

const BINDING_TONE: Record<string, "success" | "accent" | "default"> = {
  binding: "success",
  persuasive: "accent",
  informational: "default",
};

/**
 * Sessions tab — research memory.
 *
 *  Left rail: list of saved sessions for this case, newest first.
 *  Right rail: the selected session as a research memo with the
 *    full ResearchAnswer rendered out (top answer, applicable law,
 *    strongest + distinguishable authorities, excerpts, risk flags,
 *    next steps). Footer hosts:
 *      - thumbs up / thumbs down feedback (PATCH /feedback)
 *      - editable user_notes + unresolved_questions (also PATCH'd)
 *      - JSON / Markdown / PDF download buttons that hit
 *        /sessions/{id}/export/{fmt}
 */
export function ResearchSessions({ caseId }: Props) {
  const sessQ = useQuery({
    queryKey: qk.researchSessions(caseId),
    queryFn: () => researchEndpoints.listSessions(caseId),
  });

  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedId && sessQ.data && sessQ.data.length > 0 && sessQ.data[0]) {
      setSelectedId(sessQ.data[0].session_id);
    }
  }, [sessQ.data, selectedId]);

  if (sessQ.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-ink-mute">
        <Spinner /> Loading research sessions…
      </div>
    );
  }
  if (sessQ.isError) return <ErrorState onRetry={() => sessQ.refetch()} />;

  const sessions = sessQ.data ?? [];
  if (sessions.length === 0) {
    return (
      <EmptyState
        title="No saved research sessions"
        description="Run a query in the Ask tab and click 'Save to research memory' — each round-trip is persisted here so it can be exported, audited, or fed into downstream packages."
        icon={<ScrollText className="h-5 w-5" />}
      />
    );
  }

  const selected = sessions.find((s) => s.session_id === selectedId) ?? sessions[0];

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_2fr]">
      <aside className="surface divide-y divide-rule-soft">
        {sessions.map((s) => (
          <button
            key={s.session_id}
            type="button"
            onClick={() => setSelectedId(s.session_id)}
            className={cn(
              "block w-full px-4 py-3 text-left transition-colors",
              s.session_id === selected?.session_id
                ? "bg-accent-wash/40"
                : "hover:bg-parchment-soft",
            )}
          >
            <div className="flex items-center gap-2">
              <span className="line-clamp-1 font-display text-sm text-ink">
                {s.query_text}
              </span>
              {s.user_feedback !== "neutral" && (
                <span className="ml-auto">
                  {s.user_feedback === "thumbs_up" ? (
                    <ThumbsUp className="h-3 w-3 text-success" />
                  ) : (
                    <ThumbsDown className="h-3 w-3 text-warning" />
                  )}
                </span>
              )}
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-2 font-mono text-[0.6rem] text-ink-mute">
              <span>{fmtDateTime(s.created_at)}</span>
              <Badge tone="outline" className="font-normal">
                {s.query_type.replace("_", " ")}
              </Badge>
              {s.pinned_document_ids.length > 0 && (
                <span className="flex items-center gap-0.5">
                  <Bookmark className="h-2.5 w-2.5" /> {s.pinned_document_ids.length}
                </span>
              )}
            </div>
          </button>
        ))}
      </aside>

      {selected && <SessionDetail caseId={caseId} session={selected} />}
    </div>
  );
}

// ─── session detail ──────────────────────────────────────────────────

function SessionDetail({
  caseId,
  session,
}: {
  caseId: number;
  session: ResearchSession;
}) {
  const qc = useQueryClient();
  const [notes, setNotes] = useState(session.user_notes ?? "");
  const [unresolved, setUnresolved] = useState(
    (session.unresolved_questions ?? []).join("\n"),
  );

  useEffect(() => {
    setNotes(session.user_notes ?? "");
    setUnresolved((session.unresolved_questions ?? []).join("\n"));
  }, [session.session_id, session.user_notes, session.unresolved_questions]);

  const patch = useMutation({
    mutationFn: (body: ResearchFeedbackBody) =>
      researchEndpoints.patchFeedback(caseId, session.session_id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.researchSessions(caseId) }),
  });

  const exportHref = (fmt: "json" | "markdown" | "pdf") =>
    researchEndpoints.sessionExportUrl(caseId, session.session_id, fmt);

  return (
    <article className="space-y-5">
      <section className="surface p-5">
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <Eyebrow>Research memo</Eyebrow>
            <h2 className="mt-1 font-display text-lg text-ink">{session.query_text}</h2>
            <div className="mt-1 font-mono text-[0.65rem] text-ink-mute">
              {session.session_id} · {fmtDateTime(session.created_at)} ·{" "}
              {session.query_type.replace("_", " ")}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <a href={exportHref("json")} download>
              <Button variant="ghost" size="sm">
                <Download className="h-3.5 w-3.5" /> JSON
              </Button>
            </a>
            <a href={exportHref("markdown")} download>
              <Button variant="ghost" size="sm">
                <Download className="h-3.5 w-3.5" /> MD
              </Button>
            </a>
            <a href={exportHref("pdf")} download>
              <Button variant="ghost" size="sm">
                <Download className="h-3.5 w-3.5" /> PDF
              </Button>
            </a>
          </div>
        </header>

        <div className="mt-4">
          <Eyebrow>Top answer</Eyebrow>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-ink-soft">
            {session.answer.top_answer || "(empty)"}
          </p>
        </div>

        {session.answer.applicable_law.length > 0 && (
          <div className="mt-4">
            <Eyebrow>Applicable law</Eyebrow>
            <ul className="mt-2 space-y-1 text-sm text-ink-soft">
              {session.answer.applicable_law.map((l, i) => (
                <li key={i} className="flex items-start gap-2">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-accent" />
                  {l}
                </li>
              ))}
            </ul>
          </div>
        )}

        <AuthList
          title="Strongest authorities"
          items={session.answer.strongest_authorities}
          tone="success"
          pinned={new Set(session.pinned_document_ids)}
        />
        <AuthList
          title="Distinguishable / weaker"
          items={session.answer.distinguishable_authorities}
          tone="warning"
          pinned={new Set(session.pinned_document_ids)}
        />

        {session.answer.excerpts.length > 0 && (
          <div className="mt-4">
            <Eyebrow>Excerpts</Eyebrow>
            <ul className="mt-2 space-y-2 text-xs">
              {session.answer.excerpts.map((e, i) => (
                <li
                  key={i}
                  className="rounded border border-rule-soft bg-parchment-soft/40 p-3"
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

        {session.answer.risk_flags.length > 0 && (
          <div className="mt-4">
            <Eyebrow>Risk flags</Eyebrow>
            <ul className="mt-2 space-y-1 text-xs">
              {session.answer.risk_flags.map((r, i) => (
                <li key={i} className="text-warning">⚠︎ {r}</li>
              ))}
            </ul>
          </div>
        )}

        {session.answer.next_steps.length > 0 && (
          <div className="mt-4">
            <Eyebrow>Recommended next steps</Eyebrow>
            <ul className="mt-2 space-y-1 text-sm text-ink-soft">
              {session.answer.next_steps.map((s, i) => (
                <li key={i}>• {s}</li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <section className="surface p-5 space-y-4">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <Eyebrow>Feedback</Eyebrow>
          <div className="flex items-center gap-2">
            <Button
              variant={session.user_feedback === "thumbs_up" ? "primary" : "ghost"}
              size="sm"
              onClick={() => patch.mutate({ user_feedback: "thumbs_up" })}
              disabled={patch.isPending}
            >
              <ThumbsUp className="h-3.5 w-3.5" /> Good
            </Button>
            <Button
              variant={session.user_feedback === "thumbs_down" ? "primary" : "ghost"}
              size="sm"
              onClick={() => patch.mutate({ user_feedback: "thumbs_down" })}
              disabled={patch.isPending}
            >
              <ThumbsDown className="h-3.5 w-3.5" /> Bad
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => patch.mutate({ user_feedback: "neutral" })}
              disabled={patch.isPending || session.user_feedback === "neutral"}
            >
              Reset
            </Button>
          </div>
        </header>

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor={`u-${session.session_id}`}>
              Unresolved questions (one per line)
            </Label>
            <Textarea
              id={`u-${session.session_id}`}
              rows={3}
              value={unresolved}
              onChange={(e) => setUnresolved(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={`n-${session.session_id}`}>Notes</Label>
            <Textarea
              id={`n-${session.session_id}`}
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>
        </div>
        <div className="flex justify-end">
          <Button
            variant="primary"
            size="sm"
            onClick={() =>
              patch.mutate({
                user_notes: notes,
                unresolved_questions: unresolved
                  .split("\n")
                  .map((s) => s.trim())
                  .filter(Boolean),
              })
            }
            disabled={patch.isPending}
          >
            {patch.isPending ? <Spinner /> : null} Save notes
          </Button>
        </div>

        {session.pinned_document_ids.length > 0 && (
          <div>
            <Eyebrow>Pinned documents</Eyebrow>
            <ul className="mt-2 space-y-1 text-xs">
              {session.pinned_document_ids.map((d) => (
                <li
                  key={d}
                  className="flex items-center gap-2 rounded border border-rule-soft bg-parchment-soft/40 px-2 py-1"
                >
                  <Bookmark className="h-3 w-3 text-accent" />
                  <span className="font-mono text-ink-soft">{d}</span>
                  <button
                    type="button"
                    className="ml-auto text-ink-mute hover:text-ink"
                    disabled={patch.isPending}
                    onClick={() =>
                      patch.mutate({
                        pinned_document_ids: session.pinned_document_ids.filter(
                          (x) => x !== d,
                        ),
                      })
                    }
                  >
                    remove
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="space-y-1.5">
          <Eyebrow>Add a pinned document</Eyebrow>
          <PinForm
            existing={session.pinned_document_ids}
            onAdd={(id) =>
              patch.mutate({
                pinned_document_ids: [...session.pinned_document_ids, id],
              })
            }
          />
        </div>
      </section>
    </article>
  );
}

function PinForm({
  existing,
  onAdd,
}: {
  existing: string[];
  onAdd: (documentId: string) => void;
}) {
  const [draft, setDraft] = useState("");
  return (
    <form
      className="flex items-center gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        const id = draft.trim();
        if (!id || existing.includes(id)) return;
        onAdd(id);
        setDraft("");
      }}
    >
      <Input
        placeholder="doc-…"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
      />
      <Button type="submit" variant="ghost" size="sm" disabled={!draft.trim()}>
        Pin
      </Button>
    </form>
  );
}

function AuthList({
  title,
  items,
  tone,
  pinned,
}: {
  title: string;
  items: SupportingAuthority[];
  tone: "success" | "warning";
  pinned: Set<string>;
}) {
  if (items.length === 0) return null;
  return (
    <div className="mt-4">
      <Eyebrow>
        {title} ({items.length})
      </Eyebrow>
      <ul className="mt-2 space-y-2">
        {items.map((a, i) => {
          const isPinned = pinned.has(a.document_id);
          return (
            <li
              key={`${a.document_id}-${i}`}
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
                {isPinned && (
                  <Bookmark className="ml-auto h-3 w-3 text-accent" />
                )}
              </div>
              <div className="mt-1 flex flex-wrap items-baseline gap-2 font-mono text-[0.62rem] text-ink-mute">
                {a.citation && <span>{a.citation}</span>}
                {a.court && <span>· {a.court}</span>}
                {a.date_decided && <span>· {a.date_decided}</span>}
                <span className="ml-auto text-accent">
                  {a.top_chunk_citation_label}
                </span>
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
