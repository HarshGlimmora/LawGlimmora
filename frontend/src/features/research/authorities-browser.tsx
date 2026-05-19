"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { GitCompare, Library, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { Eyebrow } from "@/components/atoms/eyebrow";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { Spinner } from "@/components/feedback/spinner";
import { researchEndpoints } from "@/lib/api/endpoints";
import { qk } from "@/lib/api/query-keys";
import { fmtDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { MetadataIndexRow, RankedHit } from "@/types/api";

interface Props {
  caseId: number;
}

const BINDING_TONE: Record<string, "success" | "accent" | "default"> = {
  binding: "success",
  persuasive: "accent",
  informational: "default",
};

/**
 * Authorities tab — three jobs in one canvas:
 *
 *   1. Browse the case corpus filtered by court, jurisdiction, binding
 *      tier, and a free-text search (matches title / citation / issue).
 *      A compare-bucket lets the lawyer pick up to 3 precedents and
 *      open a side-by-side panel.
 *   2. Citation lookup — type a citation string and hit /lookup/citation
 *      to find precedents that contain it. Server does a case-insensitive
 *      substring match across `citation` + `title`.
 *   3. Find-similar — given a doc_id, server seeds a synthetic query from
 *      that doc's headnote / ratio / holding chunks and returns reranked
 *      neighbours.
 */
export function ResearchAuthorities({ caseId }: Props) {
  const [compare, setCompare] = useState<MetadataIndexRow[]>([]);
  const toggleCompare = (row: MetadataIndexRow) => {
    setCompare((prev) => {
      const idx = prev.findIndex((p) => p.document_id === row.document_id);
      if (idx >= 0) return prev.filter((_, i) => i !== idx);
      if (prev.length >= 3) return prev; // cap
      return [...prev, row];
    });
  };

  return (
    <div className="space-y-6">
      <CitationLookup caseId={caseId} />
      <FindSimilar caseId={caseId} />
      <BrowseTable
        caseId={caseId}
        compare={compare}
        toggleCompare={toggleCompare}
      />
      {compare.length >= 2 && <CompareTable rows={compare} />}
    </div>
  );
}

// ─── citation lookup ──────────────────────────────────────────────────

function CitationLookup({ caseId }: { caseId: number }) {
  const [q, setQ] = useState("");
  const [submitted, setSubmitted] = useState("");
  const lookup = useQuery({
    enabled: submitted.length > 0,
    queryKey: ["research", "lookup", caseId, submitted],
    queryFn: () => researchEndpoints.lookupCitation(caseId, submitted),
  });

  return (
    <section className="surface p-5">
      <div className="flex items-end gap-3">
        <div className="flex-1 space-y-1.5">
          <Eyebrow>Citation lookup</Eyebrow>
          <Input
            placeholder="e.g. (2019) 5 SCC 412   or   AIR 2003 SC"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") setSubmitted(q.trim());
            }}
          />
        </div>
        <Button
          variant="primary"
          onClick={() => setSubmitted(q.trim())}
          disabled={q.trim().length === 0 || lookup.isFetching}
        >
          {lookup.isFetching ? <Spinner /> : <Search className="h-4 w-4" />}
          Lookup
        </Button>
      </div>
      {submitted && (
        <div className="mt-4">
          {lookup.isLoading && (
            <div className="flex items-center gap-2 text-xs text-ink-mute">
              <Spinner /> Searching…
            </div>
          )}
          {lookup.isError && <ErrorState onRetry={() => lookup.refetch()} />}
          {lookup.data && lookup.data.matches.length === 0 && (
            <p className="text-sm text-ink-mute">
              No matches for &ldquo;{submitted}&rdquo;.
            </p>
          )}
          {lookup.data && lookup.data.matches.length > 0 && (
            <ul className="divide-y divide-rule-soft">
              {lookup.data.matches.map((m) => (
                <li key={m.document_id} className="py-2 text-sm">
                  <div className="flex items-center gap-2">
                    <span className="font-display text-ink">{m.title || "(untitled)"}</span>
                    <Badge tone={BINDING_TONE[m.binding_level] ?? "default"}>
                      {m.binding_level}
                    </Badge>
                  </div>
                  <div className="font-mono text-[0.62rem] text-ink-mute">
                    {m.citation || "—"} · {m.court || "court ?"}
                    {m.date_decided && <> · {fmtDate(m.date_decided)}</>}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}

// ─── find similar ─────────────────────────────────────────────────────

function FindSimilar({ caseId }: { caseId: number }) {
  const indexQ = useQuery({
    queryKey: qk.researchMetadata(caseId),
    queryFn: () => researchEndpoints.metadataIndex(caseId),
  });
  const [seed, setSeed] = useState<string>("");
  const [results, setResults] = useState<RankedHit[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const find = useMutation({
    mutationFn: () => researchEndpoints.similar(caseId, seed, 10),
    onMutate: () => {
      setError(null);
      setResults(null);
    },
    onSuccess: (data) => setResults(data.results),
    onError: (e) => setError((e as Error).message),
  });

  const docs = indexQ.data ?? [];

  return (
    <section className="surface p-5">
      <Eyebrow>Find similar precedents</Eyebrow>
      <div className="mt-2 flex flex-wrap items-end gap-3">
        <div className="flex-1 min-w-[260px] space-y-1.5">
          <label className="text-xs text-ink-mute">Seed document</label>
          <select
            className="w-full rounded-md border border-rule bg-card px-3 py-2 text-sm"
            value={seed}
            onChange={(e) => setSeed(e.target.value)}
          >
            <option value="">— pick one —</option>
            {docs.map((d) => (
              <option key={d.document_id} value={d.document_id}>
                {d.title || "(untitled)"} {d.citation && `— ${d.citation}`}
              </option>
            ))}
          </select>
        </div>
        <Button
          variant="primary"
          disabled={!seed || find.isPending}
          onClick={() => find.mutate()}
        >
          {find.isPending ? <Spinner /> : <GitCompare className="h-4 w-4" />}
          Find similar
        </Button>
      </div>
      {error && <p className="mt-3 text-xs text-danger">{error}</p>}
      {results && results.length === 0 && (
        <p className="mt-3 text-sm text-ink-mute">
          No similar precedents found (the seed is the only relevant doc in the
          corpus, or rerank scored everything below threshold).
        </p>
      )}
      {results && results.length > 0 && (
        <ul className="mt-3 space-y-2">
          {results.map((r, i) => (
            <li
              key={r.chunk_id}
              className="rounded border border-rule-soft bg-parchment-soft/40 p-3"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-[0.62rem] text-ink-mute">#{i + 1}</span>
                <span className="truncate font-display text-sm text-ink">
                  {r.document_title || r.document_id}
                </span>
                <Badge tone={BINDING_TONE[r.binding_level] ?? "default"} className="ml-auto">
                  score {r.final_score.toFixed(2)}
                </Badge>
              </div>
              <div className="mt-1 font-mono text-[0.62rem] text-accent">
                {r.citation_label}
              </div>
              {r.snippet && (
                <p className="mt-1 line-clamp-2 text-xs text-ink-soft">{r.snippet}</p>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// ─── browse + compare ─────────────────────────────────────────────────

function BrowseTable({
  caseId,
  compare,
  toggleCompare,
}: {
  caseId: number;
  compare: MetadataIndexRow[];
  toggleCompare: (r: MetadataIndexRow) => void;
}) {
  const q = useQuery({
    queryKey: qk.researchMetadata(caseId),
    queryFn: () => researchEndpoints.metadataIndex(caseId),
  });

  const [search, setSearch] = useState("");
  const [bindingFilter, setBindingFilter] = useState<string | null>(null);

  const filtered = useMemo(() => {
    const rows = q.data ?? [];
    const s = search.trim().toLowerCase();
    return rows.filter((r) => {
      if (bindingFilter && r.binding_level !== bindingFilter) return false;
      if (!s) return true;
      return (
        r.title.toLowerCase().includes(s) ||
        r.citation.toLowerCase().includes(s) ||
        r.court.toLowerCase().includes(s) ||
        r.issue_tags.some((t) => t.toLowerCase().includes(s)) ||
        r.practice_areas.some((t) => t.toLowerCase().includes(s))
      );
    });
  }, [q.data, search, bindingFilter]);

  const compareIds = new Set(compare.map((c) => c.document_id));

  if (q.isLoading) {
    return (
      <section className="surface p-5">
        <div className="flex items-center gap-2 text-sm text-ink-mute">
          <Spinner /> Loading authorities…
        </div>
      </section>
    );
  }
  if (q.isError) {
    return (
      <section className="surface p-5">
        <ErrorState onRetry={() => q.refetch()} />
      </section>
    );
  }
  if ((q.data ?? []).length === 0) {
    return (
      <EmptyState
        title="No authorities in the corpus yet"
        description="Ingest a precedent in the Corpus tab to populate the authorities browser."
        icon={<Library className="h-5 w-5" />}
      />
    );
  }

  return (
    <section className="surface p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Eyebrow>Authorities ({filtered.length} of {q.data?.length})</Eyebrow>
        <div className="flex items-center gap-2">
          <div className="flex rounded-full border border-rule p-0.5 text-[0.65rem]">
            <button
              type="button"
              onClick={() => setBindingFilter(null)}
              className={cn(
                "rounded-full px-2 py-0.5",
                bindingFilter === null ? "bg-accent-wash text-accent" : "text-ink-mute",
              )}
            >
              all
            </button>
            {(["binding", "persuasive", "informational"] as const).map((b) => (
              <button
                key={b}
                type="button"
                onClick={() => setBindingFilter(b === bindingFilter ? null : b)}
                className={cn(
                  "rounded-full px-2 py-0.5",
                  bindingFilter === b ? "bg-accent-wash text-accent" : "text-ink-mute",
                )}
              >
                {b}
              </button>
            ))}
          </div>
          <Input
            type="search"
            placeholder="title, citation, court, issue…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="max-w-xs"
          />
        </div>
      </div>

      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="text-[0.6rem] uppercase tracking-[0.16em] text-ink-mute">
            <tr className="border-b border-rule-soft">
              <th className="py-2 pl-2 text-left">Title</th>
              <th className="py-2 text-left">Citation</th>
              <th className="py-2 text-left">Court</th>
              <th className="py-2 text-left">Date</th>
              <th className="py-2 text-left">Binding</th>
              <th className="py-2 text-left">Outcome</th>
              <th className="py-2 text-left">Issues</th>
              <th className="py-2 text-right pr-2">Compare</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r) => {
              const checked = compareIds.has(r.document_id);
              return (
                <tr
                  key={r.document_id}
                  className="border-b border-rule-soft last:border-0 hover:bg-parchment-soft/50"
                >
                  <td className="py-2 pl-2 font-display text-ink">{r.title || "(untitled)"}</td>
                  <td className="py-2 font-mono text-[0.65rem] text-ink-mute">
                    {r.citation || "—"}
                  </td>
                  <td className="py-2 text-ink-soft">{r.court || "—"}</td>
                  <td className="py-2 text-ink-soft">
                    {r.date_decided ? fmtDate(r.date_decided) : "—"}
                  </td>
                  <td className="py-2">
                    <Badge tone={BINDING_TONE[r.binding_level] ?? "default"}>
                      {r.binding_level}
                    </Badge>
                  </td>
                  <td className="py-2 text-ink-soft">{r.outcome || "—"}</td>
                  <td className="py-2">
                    <div className="flex flex-wrap gap-1">
                      {r.issue_tags.slice(0, 2).map((t) => (
                        <span
                          key={t}
                          className="rounded-full bg-parchment-soft px-1.5 py-0.5 font-mono text-[0.55rem] text-ink-mute"
                        >
                          {t}
                        </span>
                      ))}
                      {r.issue_tags.length > 2 && (
                        <span className="font-mono text-[0.55rem] text-ink-faint">
                          +{r.issue_tags.length - 2}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="py-2 pr-2 text-right">
                    <button
                      type="button"
                      disabled={!checked && compare.length >= 3}
                      onClick={() => toggleCompare(r)}
                      className={cn(
                        "rounded-full border px-2 py-0.5 text-[0.65rem] transition-colors disabled:opacity-50",
                        checked
                          ? "border-accent bg-accent-wash text-accent"
                          : "border-rule bg-card text-ink-mute hover:border-accent/40",
                      )}
                    >
                      {checked ? "Added" : "Add"}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function CompareTable({ rows }: { rows: MetadataIndexRow[] }) {
  return (
    <section className="surface p-5">
      <Eyebrow>Case comparison ({rows.length})</Eyebrow>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="text-[0.6rem] uppercase tracking-[0.16em] text-ink-mute">
            <tr className="border-b border-rule-soft">
              <th className="py-2 pl-2 text-left">Field</th>
              {rows.map((r) => (
                <th key={r.document_id} className="py-2 pr-2 text-left">
                  {r.title || "(untitled)"}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(
              [
                ["citation", "Citation", (r: MetadataIndexRow) => r.citation || "—"],
                ["court", "Court", (r: MetadataIndexRow) => r.court || "—"],
                [
                  "date",
                  "Date decided",
                  (r: MetadataIndexRow) =>
                    r.date_decided ? fmtDate(r.date_decided) : "—",
                ],
                [
                  "binding",
                  "Binding tier",
                  (r: MetadataIndexRow) => (
                    <Badge tone={BINDING_TONE[r.binding_level] ?? "default"}>
                      {r.binding_level}
                    </Badge>
                  ),
                ],
                ["outcome", "Outcome", (r: MetadataIndexRow) => r.outcome || "—"],
                [
                  "jurisdiction",
                  "Jurisdiction",
                  (r: MetadataIndexRow) => r.jurisdiction,
                ],
                [
                  "issues",
                  "Issue tags",
                  (r: MetadataIndexRow) => r.issue_tags.join(", ") || "—",
                ],
                [
                  "practice",
                  "Practice areas",
                  (r: MetadataIndexRow) => r.practice_areas.join(", ") || "—",
                ],
                [
                  "judges",
                  "Bench",
                  (r: MetadataIndexRow) => r.judges.join(" · ") || "—",
                ],
              ] as const
            ).map(([key, label, get]) => (
              <tr
                key={key}
                className="border-b border-rule-soft last:border-0 align-top"
              >
                <td className="py-2 pl-2 font-mono text-[0.62rem] uppercase tracking-[0.16em] text-ink-mute">
                  {label}
                </td>
                {rows.map((r) => (
                  <td key={r.document_id} className="py-2 pr-2 text-ink-soft">
                    {get(r)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
