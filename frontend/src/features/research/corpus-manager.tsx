"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BookOpen,
  ClipboardPaste,
  FileUp,
  RefreshCw,
  Trash2,
  X,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useDropzone } from "react-dropzone";

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
import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { Spinner } from "@/components/feedback/spinner";
import { ApiError } from "@/lib/api/client";
import { researchEndpoints } from "@/lib/api/endpoints";
import { qk } from "@/lib/api/query-keys";
import { fmtBytes, fmtDate, fmtDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { MetadataIndexRow } from "@/types/api";

interface Props {
  caseId: number;
}

type Mode = "pdf" | "text";

const BINDING_TONE: Record<string, "success" | "accent" | "default"> = {
  binding: "success",
  persuasive: "accent",
  informational: "default",
};

/**
 * Research Engine — Corpus tab.
 *
 *  Left rail: an ingest panel that lets the lawyer either drop a PDF
 *    (POST /upload) or paste raw text (POST /ingest-text). The upload
 *    flow ingests → enriches with Gemini metadata → chunks → rebuilds
 *    the per-case BM25 + metadata index in one shot.
 *  Right rail: the metadata index — every precedent currently in the
 *    case corpus, with title/citation/court/date/binding/issues. Each
 *    row opens the canonical PrecedentDocument in a detail drawer.
 */
export function ResearchCorpusManager({ caseId }: Props) {
  const qc = useQueryClient();
  const [mode, setMode] = useState<Mode>("pdf");

  const indexQ = useQuery({
    queryKey: qk.researchMetadata(caseId),
    queryFn: () => researchEndpoints.metadataIndex(caseId),
  });

  const rebuild = useMutation({
    mutationFn: () => researchEndpoints.rebuildIndex(caseId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.researchMetadata(caseId) });
      qc.invalidateQueries({ queryKey: qk.researchDocuments(caseId) });
    },
  });

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_1.4fr]">
      <section className="surface p-5 space-y-4">
        <div className="flex items-center justify-between">
          <Eyebrow>Ingest precedent</Eyebrow>
          <div className="flex rounded-full border border-rule p-0.5">
            <button
              type="button"
              onClick={() => setMode("pdf")}
              className={cn(
                "rounded-full px-3 py-1 text-[0.7rem]",
                mode === "pdf" ? "bg-accent-wash text-accent" : "text-ink-mute",
              )}
            >
              PDF
            </button>
            <button
              type="button"
              onClick={() => setMode("text")}
              className={cn(
                "rounded-full px-3 py-1 text-[0.7rem]",
                mode === "text" ? "bg-accent-wash text-accent" : "text-ink-mute",
              )}
            >
              Text
            </button>
          </div>
        </div>
        {mode === "pdf" ? <PdfIngestForm caseId={caseId} /> : <TextIngestForm caseId={caseId} />}
      </section>

      <section className="space-y-3">
        <header className="flex items-center justify-between">
          <h2 className="font-display text-base text-ink">Corpus ({indexQ.data?.length ?? 0})</h2>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => rebuild.mutate()}
            disabled={rebuild.isPending}
          >
            {rebuild.isPending ? <Spinner /> : <RefreshCw className="h-3.5 w-3.5" />}
            Rebuild index
          </Button>
        </header>

        {indexQ.isLoading && (
          <div className="flex items-center gap-2 text-sm text-ink-mute">
            <Spinner /> Loading corpus…
          </div>
        )}
        {indexQ.isError && <ErrorState onRetry={() => indexQ.refetch()} />}
        {indexQ.data && indexQ.data.length === 0 && (
          <EmptyState
            title="No precedents in this case yet"
            description="Ingest a judgment PDF or paste raw text. Metadata is extracted with Vertex Gemini, chunks are anchored to citations, and the BM25 index is rebuilt automatically."
            icon={<BookOpen className="h-5 w-5" />}
          />
        )}
        {indexQ.data && indexQ.data.length > 0 && (
          <CorpusTable caseId={caseId} rows={indexQ.data} />
        )}
      </section>
    </div>
  );
}

// ─── PDF ingest ───────────────────────────────────────────────────────

function PdfIngestForm({ caseId }: { caseId: number }) {
  const qc = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [notes, setNotes] = useState("");
  const [serverError, setServerError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);

  const onDrop = useCallback((accepted: File[]) => {
    if (accepted[0]) {
      setFile(accepted[0]);
      setServerError(null);
      setOkMsg(null);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"] },
    multiple: false,
    maxSize: 25 * 1024 * 1024,
  });

  const mutation = useMutation({
    mutationFn: () => {
      if (!file) throw new Error("Pick a PDF first.");
      return researchEndpoints.uploadPdf(caseId, {
        file,
        notes: notes.trim() || undefined,
      });
    },
    onMutate: () => {
      setServerError(null);
      setOkMsg(null);
    },
    onSuccess: (data) => {
      setOkMsg(
        `Ingested ${data.document_id} · ${data.chunk_count} chunks · ` +
          `${data.index_summary.docs} docs / ${data.index_summary.chunks} chunks in case`,
      );
      setFile(null);
      setNotes("");
      qc.invalidateQueries({ queryKey: qk.researchMetadata(caseId) });
      qc.invalidateQueries({ queryKey: qk.researchDocuments(caseId) });
    },
    onError: (err) =>
      setServerError(
        err instanceof ApiError ? err.message : "Upload failed.",
      ),
  });

  return (
    <div className="space-y-4">
      <div
        {...getRootProps({
          className: cn(
            "flex flex-col items-center justify-center gap-2 rounded-md border border-dashed px-6 py-8 text-center transition-colors",
            isDragActive
              ? "border-accent bg-accent-wash/60"
              : "border-rule bg-parchment-soft/50 hover:border-accent/60",
          ),
        })}
      >
        <input {...getInputProps()} />
        <FileUp className="h-5 w-5 text-accent" />
        <div className="font-display text-sm text-ink">
          {file ? file.name : isDragActive ? "Drop the PDF" : "Drop a precedent PDF or click"}
        </div>
        <p className="text-xs text-ink-mute">PDF only · max 25 MB</p>
        {file && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setFile(null);
            }}
            className="mt-2 inline-flex items-center gap-1 text-xs text-ink-mute hover:text-ink"
          >
            <X className="h-3 w-3" /> Remove ({fmtBytes(file.size)})
          </button>
        )}
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="pdf-notes">Notes (optional)</Label>
        <Textarea
          id="pdf-notes"
          rows={2}
          placeholder="Reporter, source, why this matters."
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </div>
      {serverError && <p className="text-xs text-danger">{serverError}</p>}
      {okMsg && <p className="text-xs text-success">{okMsg}</p>}
      <div className="flex justify-end">
        <Button
          variant="primary"
          disabled={!file || mutation.isPending}
          onClick={() => mutation.mutate()}
        >
          {mutation.isPending ? <Spinner /> : <FileUp className="h-4 w-4" />}
          Ingest precedent
        </Button>
      </div>
    </div>
  );
}

// ─── Text ingest ──────────────────────────────────────────────────────

function TextIngestForm({ caseId }: { caseId: number }) {
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [sourceRef, setSourceRef] = useState("");
  const [notes, setNotes] = useState("");
  const [serverError, setServerError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      researchEndpoints.ingestText(caseId, {
        title: title.trim(),
        body: body.trim(),
        source_reference: sourceRef.trim() || undefined,
        notes: notes.trim() || undefined,
      }),
    onMutate: () => {
      setServerError(null);
      setOkMsg(null);
    },
    onSuccess: (data) => {
      setOkMsg(`Ingested ${data.document_id} · ${data.chunk_count} chunks`);
      setTitle("");
      setBody("");
      setSourceRef("");
      setNotes("");
      qc.invalidateQueries({ queryKey: qk.researchMetadata(caseId) });
      qc.invalidateQueries({ queryKey: qk.researchDocuments(caseId) });
    },
    onError: (err) =>
      setServerError(
        err instanceof ApiError ? err.message : "Ingest failed.",
      ),
  });

  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <Label htmlFor="t-title">Title</Label>
        <Input
          id="t-title"
          placeholder="Acme Industries vs Zenith Holdings"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="t-body">Body (paste judgment text)</Label>
        <Textarea
          id="t-body"
          rows={10}
          placeholder="HEADNOTE…\nFACTS…\nISSUES…\nHELD…"
          value={body}
          onChange={(e) => setBody(e.target.value)}
        />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="t-source">Source reference</Label>
          <Input
            id="t-source"
            placeholder="(2019) 5 SCC 412"
            value={sourceRef}
            onChange={(e) => setSourceRef(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="t-notes">Notes</Label>
          <Input
            id="t-notes"
            placeholder="optional"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </div>
      </div>
      {serverError && <p className="text-xs text-danger">{serverError}</p>}
      {okMsg && <p className="text-xs text-success">{okMsg}</p>}
      <div className="flex justify-end">
        <Button
          variant="primary"
          disabled={
            title.trim().length === 0 ||
            body.trim().length === 0 ||
            mutation.isPending
          }
          onClick={() => mutation.mutate()}
        >
          {mutation.isPending ? <Spinner /> : <ClipboardPaste className="h-4 w-4" />}
          Ingest text
        </Button>
      </div>
    </div>
  );
}

// ─── Corpus table + detail drawer ─────────────────────────────────────

function CorpusTable({
  caseId,
  rows,
}: {
  caseId: number;
  rows: MetadataIndexRow[];
}) {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);

  // Default-open the newest doc when the list grows
  useEffect(() => {
    if (!selected && rows.length > 0 && rows[0]) setSelected(rows[0].document_id);
  }, [rows, selected]);

  const docQ = useQuery({
    enabled: !!selected,
    queryKey: qk.researchDocument(caseId, selected ?? "_"),
    queryFn: () => researchEndpoints.getDocument(caseId, selected!),
  });

  const del = useMutation({
    mutationFn: (id: string) => researchEndpoints.deleteDocument(caseId, id),
    onSuccess: () => {
      setSelected(null);
      qc.invalidateQueries({ queryKey: qk.researchMetadata(caseId) });
      qc.invalidateQueries({ queryKey: qk.researchDocuments(caseId) });
    },
  });

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr]">
      <ul className="surface divide-y divide-rule-soft">
        {rows.map((r) => (
          <li key={r.document_id}>
            <button
              type="button"
              onClick={() => setSelected(r.document_id)}
              className={cn(
                "w-full text-left px-4 py-3 transition-colors",
                selected === r.document_id
                  ? "bg-accent-wash/50"
                  : "hover:bg-parchment-soft",
              )}
            >
              <div className="flex items-center gap-2">
                <span className="truncate font-display text-sm text-ink">
                  {r.title || "(untitled)"}
                </span>
                <Badge
                  tone={BINDING_TONE[r.binding_level] ?? "default"}
                  className="ml-auto shrink-0"
                >
                  {r.binding_level}
                </Badge>
              </div>
              <div className="mt-1 truncate font-mono text-[0.62rem] text-ink-mute">
                {r.citation || "—"} · {r.court || "court ?"}
                {r.date_decided && <> · {fmtDate(r.date_decided)}</>}
              </div>
              <div className="mt-1 flex flex-wrap gap-1">
                {r.issue_tags.slice(0, 3).map((t) => (
                  <span
                    key={t}
                    className="rounded-full bg-parchment-soft px-1.5 py-0.5 font-mono text-[0.55rem] text-ink-mute"
                  >
                    {t}
                  </span>
                ))}
                {r.issue_tags.length > 3 && (
                  <span className="font-mono text-[0.55rem] text-ink-faint">
                    +{r.issue_tags.length - 3}
                  </span>
                )}
              </div>
            </button>
          </li>
        ))}
      </ul>

      <section className="surface p-5">
        {!selected && (
          <p className="text-sm text-ink-mute">
            Pick a precedent to inspect its metadata, chunks, and pages.
          </p>
        )}
        {selected && docQ.isLoading && (
          <div className="flex items-center gap-2 text-sm text-ink-mute">
            <Spinner /> Loading document…
          </div>
        )}
        {selected && docQ.isError && <ErrorState onRetry={() => docQ.refetch()} />}
        {selected && docQ.data && (
          <div className="space-y-4">
            <header className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <Eyebrow>Precedent</Eyebrow>
                <h3 className="mt-1 font-display text-lg text-ink">
                  {docQ.data.meta.title || "(untitled)"}
                </h3>
                <div className="mt-1 font-mono text-[0.7rem] text-ink-mute">
                  {docQ.data.meta.citation || "no citation"} ·{" "}
                  {docQ.data.meta.court || "court ?"}
                  {docQ.data.meta.date_decided && <> · {fmtDate(docQ.data.meta.date_decided)}</>}
                </div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => del.mutate(docQ.data!.document_id)}
                disabled={del.isPending}
              >
                {del.isPending ? <Spinner /> : <Trash2 className="h-3.5 w-3.5" />}
                Delete
              </Button>
            </header>

            <dl className="grid gap-2 text-xs sm:grid-cols-2">
              <Term label="Jurisdiction" value={docQ.data.meta.jurisdiction} />
              <Term label="Outcome" value={docQ.data.meta.outcome || "—"} />
              <Term
                label="Binding"
                value={
                  <Badge tone={BINDING_TONE[docQ.data.meta.binding_level] ?? "default"}>
                    {docQ.data.meta.binding_level}
                  </Badge>
                }
              />
              <Term label="Source" value={docQ.data.meta.source_type} />
              <Term
                label="Confidence"
                value={`${(docQ.data.meta.confidence_score * 100).toFixed(0)}%`}
              />
              <Term label="Pages" value={String(docQ.data.page_count)} />
              <Term
                label="Practice"
                value={docQ.data.meta.practice_areas.join(", ") || "—"}
              />
              <Term label="Status" value={docQ.data.status} />
              <Term
                label="Ingested"
                value={fmtDateTime(docQ.data.ingested_at)}
              />
              <Term label="Filename" value={docQ.data.filename} />
            </dl>

            {docQ.data.meta.judges.length > 0 && (
              <div>
                <Eyebrow>Bench</Eyebrow>
                <p className="mt-1 text-sm text-ink-soft">
                  {docQ.data.meta.judges.join(" · ")}
                </p>
              </div>
            )}
            {docQ.data.meta.issue_tags.length > 0 && (
              <div>
                <Eyebrow>Issue tags</Eyebrow>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {docQ.data.meta.issue_tags.map((t) => (
                    <Badge key={t} tone="outline">{t}</Badge>
                  ))}
                </div>
              </div>
            )}
            {docQ.data.meta.headnote && (
              <div>
                <Eyebrow>Headnote</Eyebrow>
                <p className="mt-1 text-sm text-ink-soft">{docQ.data.meta.headnote}</p>
              </div>
            )}
            {docQ.data.meta.ratio && (
              <div>
                <Eyebrow>Ratio decidendi</Eyebrow>
                <p className="mt-1 text-sm text-ink-soft">{docQ.data.meta.ratio}</p>
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}

function Term({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="font-mono text-[0.6rem] uppercase tracking-[0.16em] text-ink-mute">
        {label}
      </dt>
      <dd className="mt-0.5 text-ink-soft">{value}</dd>
    </div>
  );
}
