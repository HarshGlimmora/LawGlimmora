"use client";

import { useQuery } from "@tanstack/react-query";
import { FileText, ListChecks, ScrollText } from "lucide-react";
import { useEffect, useState } from "react";

import { Eyebrow } from "@/components/atoms/eyebrow";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { Spinner } from "@/components/feedback/spinner";
import { evidenceEndpoints } from "@/lib/api/endpoints";
import { qk } from "@/lib/api/query-keys";
import { fmtDateTime } from "@/lib/format";

interface Props {
  caseId: number;
}

/**
 * Canonical store viewer.
 *
 * 1. Lists every ingested document in a left-rail picker (default = newest).
 * 2. For the selected document, fetches the canonical JSON
 *    (/api/cases/{id}/evidence/documents/{doc_id}) and renders the
 *    document-level summary, the per-page text, and a chunk index with
 *    citation labels — the same artifacts the backend persists to disk.
 *
 * This is intentionally read-only: it's the lawyer's window into what the
 * extraction pipeline actually produced, so they can sanity-check the
 * citations against the original PDF.
 */
export function CanonicalStore({ caseId }: Props) {
  const docsQ = useQuery({
    queryKey: qk.evidenceDocuments(caseId),
    queryFn: () => evidenceEndpoints.listDocuments(caseId),
  });

  const docs = docsQ.data ?? [];
  const [selected, setSelected] = useState<string | null>(null);

  // Default-select the newest document once the list loads.
  useEffect(() => {
    if (!selected && docs.length > 0 && docs[0]) setSelected(docs[0].document_id);
  }, [docs, selected]);

  const docQ = useQuery({
    enabled: !!selected,
    queryKey: qk.evidenceDocument(caseId, selected ?? "_none_"),
    queryFn: () => evidenceEndpoints.getDocument(caseId, selected!),
  });

  if (docsQ.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-ink-mute">
        <Spinner /> Loading documents…
      </div>
    );
  }
  if (docsQ.isError) return <ErrorState onRetry={() => docsQ.refetch()} />;
  if (docs.length === 0) {
    return (
      <EmptyState
        title="No documents to browse"
        description="Upload a PDF in the first tab. Once extraction completes, its canonical JSON will appear here."
        icon={<ScrollText className="h-5 w-5" />}
      />
    );
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_2fr]">
      <aside className="surface p-5">
        <Eyebrow>Documents</Eyebrow>
        <div className="mt-3">
          <Select value={selected ?? undefined} onValueChange={setSelected}>
            <SelectTrigger>
              <SelectValue placeholder="Select a document" />
            </SelectTrigger>
            <SelectContent>
              {docs.map((d) => (
                <SelectItem key={d.document_id} value={d.document_id}>
                  {d.evidence_title}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {docQ.data && (
          <dl className="mt-5 space-y-3 text-xs">
            <div>
              <dt className="font-mono text-[0.62rem] uppercase tracking-[0.16em] text-ink-mute">
                Filename
              </dt>
              <dd className="mt-0.5 truncate text-ink-soft">{docQ.data.document.filename}</dd>
            </div>
            <div>
              <dt className="font-mono text-[0.62rem] uppercase tracking-[0.16em] text-ink-mute">
                Type
              </dt>
              <dd className="mt-0.5">
                <Badge tone="outline">{docQ.data.document.doc_type}</Badge>
              </dd>
            </div>
            <div>
              <dt className="font-mono text-[0.62rem] uppercase tracking-[0.16em] text-ink-mute">
                Pages
              </dt>
              <dd className="mt-0.5 text-ink-soft">{docQ.data.document.page_count}</dd>
            </div>
            <div>
              <dt className="font-mono text-[0.62rem] uppercase tracking-[0.16em] text-ink-mute">
                Uploaded
              </dt>
              <dd className="mt-0.5 text-ink-soft">
                {fmtDateTime(docQ.data.document.uploaded_at)}
              </dd>
            </div>
            <div>
              <dt className="font-mono text-[0.62rem] uppercase tracking-[0.16em] text-ink-mute">
                Status
              </dt>
              <dd className="mt-0.5">
                <Badge
                  tone={
                    docQ.data.document.processing_status === "completed"
                      ? "success"
                      : docQ.data.document.processing_status === "failed"
                      ? "danger"
                      : "warning"
                  }
                >
                  {docQ.data.document.processing_status}
                </Badge>
              </dd>
            </div>
            <div>
              <dt className="font-mono text-[0.62rem] uppercase tracking-[0.16em] text-ink-mute">
                Totals
              </dt>
              <dd className="mt-0.5 text-ink-soft">
                {docQ.data.summary.total_pages} pages · {docQ.data.summary.total_words} words
                · {docQ.data.chunks.length} chunks · {docQ.data.entities.length} entities
              </dd>
            </div>
          </dl>
        )}
      </aside>

      <section className="space-y-5">
        {docQ.isLoading && (
          <div className="flex items-center gap-2 text-sm text-ink-mute">
            <Spinner /> Loading canonical JSON…
          </div>
        )}
        {docQ.isError && <ErrorState onRetry={() => docQ.refetch()} />}

        {docQ.data && (
          <>
            <article className="surface p-5">
              <header className="flex items-center justify-between">
                <Eyebrow>Document</Eyebrow>
                <Badge tone="accent">
                  <FileText className="h-3 w-3" />
                  {docQ.data.document.document_id}
                </Badge>
              </header>
              <h2 className="mt-2 font-display text-lg text-ink">
                {docQ.data.document.evidence_title}
              </h2>
              {docQ.data.document.notes && (
                <p className="mt-2 text-sm text-ink-soft">{docQ.data.document.notes}</p>
              )}
            </article>

            <article className="surface p-5">
              <header className="flex items-center justify-between">
                <Eyebrow>Pages</Eyebrow>
                <span className="font-mono text-[0.62rem] text-ink-mute">
                  {docQ.data.pages.length} pages
                </span>
              </header>
              <ol className="mt-3 space-y-3">
                {docQ.data.pages.map((p) => (
                  <li key={p.page_number} className="rounded-md border border-rule-soft bg-parchment-soft/40 p-3">
                    <div className="flex items-center justify-between">
                      <Badge tone="outline">Page {p.page_number}</Badge>
                      <span className="font-mono text-[0.62rem] text-ink-mute">
                        {p.word_count}w · {p.character_count}c
                      </span>
                    </div>
                    {p.citations.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {p.citations.map((c) => (
                          <span
                            key={c.citation_id}
                            className="font-mono text-[0.62rem] text-accent"
                          >
                            {c.citation_label}
                          </span>
                        ))}
                      </div>
                    )}
                    <p className="mt-2 line-clamp-4 whitespace-pre-wrap text-xs text-ink-soft">
                      {p.clean_text || p.raw_text || "(no extracted text)"}
                    </p>
                  </li>
                ))}
              </ol>
            </article>

            <article className="surface p-5">
              <header className="flex items-center justify-between">
                <Eyebrow>Chunks</Eyebrow>
                <span className="font-mono text-[0.62rem] text-ink-mute">
                  {docQ.data.chunks.length} chunks
                </span>
              </header>
              {docQ.data.chunks.length === 0 ? (
                <p className="mt-3 text-sm text-ink-mute">
                  No chunks were produced — either extraction failed or the document is
                  empty.
                </p>
              ) : (
                <ul className="mt-3 space-y-2">
                  {docQ.data.chunks.map((c, idx) => {
                    const ch = c as Record<string, unknown>;
                    const anchor = (ch.citation_anchor || {}) as Record<string, unknown>;
                    const label = String(anchor.citation_label || "");
                    const ctype = String(ch.chunk_type || "unidentified");
                    const wc = Number(ch.word_count || 0);
                    const clean = String(ch.clean_text || ch.text || "");
                    return (
                      <li
                        key={String(ch.chunk_id || idx)}
                        className="rounded-md border border-rule-soft bg-parchment-soft/40 p-3"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <Badge tone="outline">{ctype}</Badge>
                            <span className="font-mono text-[0.62rem] text-ink-mute">
                              {wc} words
                            </span>
                          </div>
                          <span className="truncate font-mono text-[0.62rem] text-accent">
                            {label}
                          </span>
                        </div>
                        <p className="mt-2 line-clamp-3 whitespace-pre-wrap text-xs text-ink-soft">
                          {clean}
                        </p>
                      </li>
                    );
                  })}
                </ul>
              )}
            </article>

            <article className="surface p-5">
              <header className="flex items-center justify-between">
                <Eyebrow>Pipeline run</Eyebrow>
                <Badge tone="accent">
                  <ListChecks className="h-3 w-3" />
                  {docQ.data.summary.extraction_duration_ms} ms
                </Badge>
              </header>
              <p className="mt-2 text-xs text-ink-mute">
                Total extraction time across page splitting, entity
                resolution, partitioning, and chunk citation anchoring.
              </p>
            </article>
          </>
        )}
      </section>
    </div>
  );
}
