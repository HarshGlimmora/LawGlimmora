"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Bot, RotateCcw, User } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Eyebrow } from "@/components/atoms/eyebrow";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EmptyState } from "@/components/feedback/empty-state";
import { Spinner } from "@/components/feedback/spinner";
import { useConstants } from "@/hooks/use-constants";
import { chatEndpoints } from "@/lib/api/endpoints";
import { qk } from "@/lib/api/query-keys";
import { fmtDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Answer } from "@/types/api";

export function EvidenceChat({ caseId }: { caseId: number }) {
  const qc = useQueryClient();
  const constants = useConstants();
  const [draft, setDraft] = useState("");
  const [lastAnswer, setLastAnswer] = useState<Answer | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const history = useQuery({
    queryKey: qk.evidenceChat(caseId),
    queryFn: () => chatEndpoints.history(caseId),
  });

  const ask = useMutation({
    mutationFn: (query: string) => chatEndpoints.ask(caseId, { query }),
    onSuccess: (resp) => {
      setLastAnswer(resp.answer);
      setDraft("");
      qc.invalidateQueries({ queryKey: qk.evidenceChat(caseId) });
    },
  });

  const clear = useMutation({
    mutationFn: () => chatEndpoints.clear(caseId),
    onSuccess: () => {
      setLastAnswer(null);
      qc.invalidateQueries({ queryKey: qk.evidenceChat(caseId) });
    },
  });

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [history.data, lastAnswer]);

  const turns = history.data?.turns ?? [];

  return (
    <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
      <section className="surface flex flex-col">
        <header className="flex items-center justify-between border-b border-rule-soft px-5 py-3">
          <Eyebrow>Conversation</Eyebrow>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => clear.mutate()}
            disabled={turns.length === 0 || clear.isPending}
          >
            <RotateCcw className="h-3.5 w-3.5" /> Clear
          </Button>
        </header>

        <div ref={scrollRef} className="max-h-[480px] min-h-[260px] flex-1 space-y-4 overflow-y-auto p-5">
          {turns.length === 0 ? (
            <EmptyState
              title="Ask the case anything"
              description="Pose a question — Glimmora searches the entities, chunks, contradictions, and missing-evidence layers and answers with citations."
              icon={<Bot className="h-5 w-5" />}
            />
          ) : (
            turns.map((t) => (
              <article key={t.turn_id} className="flex items-start gap-3 animate-fade-in">
                <span
                  className={cn(
                    "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[0.6rem] uppercase",
                    t.role === "assistant"
                      ? "border-accent/40 bg-accent-wash text-accent"
                      : "border-rule bg-card text-ink-soft",
                  )}
                >
                  {t.role === "assistant" ? <Bot className="h-3 w-3" /> : <User className="h-3 w-3" />}
                </span>
                <div className="min-w-0 flex-1 space-y-1.5">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[0.6rem] uppercase tracking-[0.16em] text-ink-mute">
                      {t.role === "assistant" ? "Glimmora" : "You"}
                    </span>
                    <span className="text-[0.6rem] text-ink-faint">{fmtDateTime(t.ts)}</span>
                    {t.intent && (
                      <Badge tone="outline" className="font-normal">
                        {t.intent.replace(/_/g, " ")}
                      </Badge>
                    )}
                  </div>
                  <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink-soft">
                    {t.message}
                  </p>
                </div>
              </article>
            ))
          )}
          {ask.isPending && (
            <div className="flex items-center gap-2 text-xs text-ink-mute">
              <Spinner /> Synthesising answer…
            </div>
          )}
        </div>

        <form
          className="border-t border-rule-soft p-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (draft.trim()) ask.mutate(draft.trim());
          }}
        >
          <div className="flex items-center gap-2">
            <Input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Ask a question about this case…"
              disabled={ask.isPending}
            />
            <Button type="submit" variant="primary" disabled={!draft.trim() || ask.isPending}>
              <ArrowRight className="h-4 w-4" />
              <span className="sr-only">Send</span>
            </Button>
          </div>
        </form>
      </section>

      <aside className="space-y-4">
        <section className="surface p-5">
          <Eyebrow>Suggested prompts</Eyebrow>
          <ul className="mt-3 space-y-2">
            {(constants.data?.suggested_prompts ?? []).map((p) => (
              <li key={p}>
                <button
                  type="button"
                  onClick={() => setDraft(p)}
                  className="w-full rounded-md border border-rule bg-card px-3 py-2 text-left text-xs text-ink-soft transition-colors hover:border-accent/40 hover:text-ink"
                >
                  {p}
                </button>
              </li>
            ))}
          </ul>
        </section>

        {lastAnswer && (
          <section className="surface p-5">
            <Eyebrow>Last answer · {lastAnswer.synthesis_source}</Eyebrow>
            <div className="mt-3 space-y-2">
              <div className="text-[0.7rem] text-ink-mute">
                Confidence {(lastAnswer.confidence * 100).toFixed(0)}%
              </div>
              {lastAnswer.supporting_sources.length > 0 && (
                <ul className="space-y-1.5 text-xs">
                  {lastAnswer.supporting_sources.map((s, i) => (
                    <li key={i} className="rounded border border-rule-soft bg-parchment-soft/60 p-2">
                      <div className="font-mono text-[0.62rem] text-accent">
                        {s.citation_label}
                      </div>
                      {s.snippet && (
                        <p className="mt-1 line-clamp-3 text-ink-soft">{s.snippet}</p>
                      )}
                    </li>
                  ))}
                </ul>
              )}
              {lastAnswer.warnings.length > 0 && (
                <div className="mt-2 space-y-1">
                  {lastAnswer.warnings.map((w, i) => (
                    <p key={i} className="text-xs text-warning">⚠︎ {w}</p>
                  ))}
                </div>
              )}
            </div>
          </section>
        )}
      </aside>
    </div>
  );
}
