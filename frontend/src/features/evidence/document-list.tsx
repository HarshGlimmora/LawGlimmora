"use client";

import { useQuery } from "@tanstack/react-query";
import { FileText } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { Spinner } from "@/components/feedback/spinner";
import { evidenceEndpoints } from "@/lib/api/endpoints";
import { qk } from "@/lib/api/query-keys";
import { fmtDateTime } from "@/lib/format";

const STATUS_TONE: Record<string, "success" | "warning" | "danger" | "default"> = {
  completed: "success",
  extracting: "warning",
  pending: "default",
  failed: "danger",
};

export function DocumentList({ caseId }: { caseId: number }) {
  const q = useQuery({
    queryKey: qk.evidenceDocuments(caseId),
    queryFn: () => evidenceEndpoints.listDocuments(caseId),
  });

  if (q.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-ink-mute">
        <Spinner /> Loading documents…
      </div>
    );
  }
  if (q.isError) return <ErrorState onRetry={() => q.refetch()} />;

  const docs = q.data ?? [];
  if (docs.length === 0) {
    return (
      <EmptyState
        title="No evidence ingested yet"
        description="Drop a PDF in the upload panel above. Once extraction completes, it will appear here."
        icon={<FileText className="h-5 w-5" />}
      />
    );
  }

  return (
    <ul className="surface divide-y divide-rule-soft">
      {docs.map((d) => (
        <li key={d.document_id} className="flex items-start justify-between gap-4 px-5 py-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <FileText className="h-3.5 w-3.5 text-accent" />
              <span className="truncate font-display text-base text-ink">
                {d.evidence_title}
              </span>
              <Badge tone="outline" className="ml-1">{d.doc_type}</Badge>
            </div>
            <div className="mt-1 text-xs text-ink-mute">
              {d.filename} · {d.page_count} {d.page_count === 1 ? "page" : "pages"} · uploaded{" "}
              {fmtDateTime(d.uploaded_at)}
            </div>
          </div>
          <Badge tone={STATUS_TONE[d.processing_status] ?? "default"} className="shrink-0">
            {d.processing_status}
          </Badge>
        </li>
      ))}
    </ul>
  );
}
