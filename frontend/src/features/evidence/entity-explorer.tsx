"use client";

import { useQuery } from "@tanstack/react-query";
import { Tag, Users } from "lucide-react";
import { useMemo, useState } from "react";

import { Eyebrow } from "@/components/atoms/eyebrow";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { Spinner } from "@/components/feedback/spinner";
import { evidenceEndpoints } from "@/lib/api/endpoints";
import { qk } from "@/lib/api/query-keys";
import { cn } from "@/lib/utils";

interface Props {
  caseId: number;
}

const PARTITION_ORDER = [
  "parties",
  "timeline",
  "legal_basis",
  "factual_evidence",
  "procedural_facts",
] as const;

const PARTITION_LABEL: Record<string, string> = {
  parties: "Parties",
  timeline: "Timeline",
  legal_basis: "Legal basis",
  factual_evidence: "Factual evidence",
  procedural_facts: "Procedural facts",
};

/**
 * Entity & partition explorer.
 *
 * Loads the case-level partitions (parties, timeline, legal_basis,
 * factual_evidence, procedural_facts) plus the full flat entities list.
 * The user filters by partition (chips), optionally further filters by
 * entity_type, and a free-text search narrows by value or context. Each
 * row links back to its source chunk via the citation label.
 */
export function EntityExplorer({ caseId }: Props) {
  const partsQ = useQuery({
    queryKey: qk.evidencePartitions(caseId),
    queryFn: () => evidenceEndpoints.listPartitions(caseId),
  });
  const entsQ = useQuery({
    queryKey: qk.evidenceEntities(caseId),
    queryFn: () => evidenceEndpoints.listEntities(caseId),
  });

  const [partition, setPartition] = useState<string>("parties");
  const [typeFilter, setTypeFilter] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const partitionsByName = useMemo(() => {
    const map: Record<string, typeof entsQ.data> = {};
    (partsQ.data ?? []).forEach((p) => {
      map[p.partition_type] = (p.entities as typeof entsQ.data) ?? [];
    });
    return map;
  }, [partsQ.data, entsQ.data]);

  const entitiesInPartition = partitionsByName[partition] ?? [];
  const typesInPartition = useMemo(() => {
    const counts = new Map<string, number>();
    entitiesInPartition.forEach((e) =>
      counts.set(e.entity_type, (counts.get(e.entity_type) ?? 0) + 1),
    );
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
  }, [entitiesInPartition]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return entitiesInPartition.filter((e) => {
      if (typeFilter && e.entity_type !== typeFilter) return false;
      if (!q) return true;
      return (
        e.value.toLowerCase().includes(q) ||
        e.normalized_value.toLowerCase().includes(q) ||
        e.context_excerpt.toLowerCase().includes(q)
      );
    });
  }, [entitiesInPartition, typeFilter, search]);

  if (partsQ.isLoading || entsQ.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-ink-mute">
        <Spinner /> Loading entities…
      </div>
    );
  }
  if (partsQ.isError || entsQ.isError) {
    return (
      <ErrorState
        onRetry={() => {
          partsQ.refetch();
          entsQ.refetch();
        }}
      />
    );
  }

  const totalEntities = entsQ.data?.length ?? 0;
  if (totalEntities === 0) {
    return (
      <EmptyState
        title="No entities yet"
        description="Upload at least one PDF to populate the entity layers (parties, timeline, legal basis, factual evidence, procedural facts)."
        icon={<Tag className="h-5 w-5" />}
      />
    );
  }

  const partitionsKnown = PARTITION_ORDER.filter((p) => partitionsByName[p] !== undefined);
  const extraPartitions = (partsQ.data ?? [])
    .map((p) => p.partition_type)
    .filter((p) => !PARTITION_ORDER.includes(p as (typeof PARTITION_ORDER)[number]));
  const partitionsToShow = [...partitionsKnown, ...extraPartitions];

  return (
    <div className="space-y-5">
      <section className="surface p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Eyebrow>Partitions</Eyebrow>
          <span className="font-mono text-[0.62rem] text-ink-mute">
            {totalEntities} entities across {partsQ.data?.length ?? 0} partitions
          </span>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {partitionsToShow.map((p) => {
            const count = (partitionsByName[p] ?? []).length;
            const active = p === partition;
            return (
              <button
                key={p}
                type="button"
                onClick={() => {
                  setPartition(p);
                  setTypeFilter(null);
                }}
                className={cn(
                  "rounded-full border px-3 py-1 text-xs transition-colors",
                  active
                    ? "border-accent bg-accent-wash text-accent"
                    : "border-rule bg-card text-ink-soft hover:border-accent/40 hover:text-ink",
                )}
              >
                {PARTITION_LABEL[p] ?? p} · {count}
              </button>
            );
          })}
        </div>
      </section>

      <section className="surface p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Eyebrow>
            {PARTITION_LABEL[partition] ?? partition} ({entitiesInPartition.length})
          </Eyebrow>
          <Input
            type="search"
            placeholder="Search value or context…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="max-w-xs"
          />
        </div>

        {typesInPartition.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            <button
              type="button"
              onClick={() => setTypeFilter(null)}
              className={cn(
                "rounded-full border px-2.5 py-0.5 text-[0.7rem] transition-colors",
                typeFilter === null
                  ? "border-accent bg-accent-wash text-accent"
                  : "border-rule bg-card text-ink-soft hover:border-accent/40",
              )}
            >
              All types
            </button>
            {typesInPartition.map(([t, n]) => (
              <button
                key={t}
                type="button"
                onClick={() => setTypeFilter(t === typeFilter ? null : t)}
                className={cn(
                  "rounded-full border px-2.5 py-0.5 text-[0.7rem] transition-colors",
                  t === typeFilter
                    ? "border-accent bg-accent-wash text-accent"
                    : "border-rule bg-card text-ink-soft hover:border-accent/40",
                )}
              >
                {t} · {n}
              </button>
            ))}
          </div>
        )}

        {filtered.length === 0 ? (
          <p className="mt-6 text-sm text-ink-mute">
            No entities match the current filters.
          </p>
        ) : (
          <ul className="mt-4 divide-y divide-rule-soft">
            {filtered.slice(0, 200).map((e) => (
              <li key={e.entity_id} className="flex flex-col gap-1.5 py-3 text-xs">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="accent">{e.entity_type}</Badge>
                  <span className="font-display text-sm text-ink">{e.value}</span>
                  {e.normalized_value && e.normalized_value !== e.value && (
                    <span className="font-mono text-[0.65rem] text-ink-mute">
                      → {e.normalized_value}
                    </span>
                  )}
                  <span className="ml-auto font-mono text-[0.62rem] text-accent">
                    {e.citation_label}
                  </span>
                </div>
                {e.context_excerpt && (
                  <p className="line-clamp-2 text-ink-soft">
                    “{e.context_excerpt}”
                  </p>
                )}
                <div className="flex items-center gap-3 font-mono text-[0.6rem] text-ink-faint">
                  <span>conf {(e.confidence * 100).toFixed(0)}%</span>
                  <span>chunk {e.source_chunk_id.slice(0, 12)}</span>
                  <span>p. {e.source_page}</span>
                </div>
              </li>
            ))}
          </ul>
        )}

        {filtered.length > 200 && (
          <p className="mt-3 text-[0.7rem] text-ink-mute">
            Showing first 200 of {filtered.length} matches — narrow the filter to see more.
          </p>
        )}
      </section>
    </div>
  );
}
