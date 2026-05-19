"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";

import { ErrorState } from "@/components/feedback/error-state";
import { Spinner } from "@/components/feedback/spinner";
import { PageHeader } from "@/components/layout/page-header";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CanonicalStore } from "@/features/evidence/canonical-store";
import { ContradictionsLedger } from "@/features/evidence/contradictions-ledger";
import { DocumentList } from "@/features/evidence/document-list";
import { EntityExplorer } from "@/features/evidence/entity-explorer";
import { EvidenceChat } from "@/features/evidence/evidence-chat";
import { FinalAnalysis } from "@/features/evidence/final-analysis";
import { MissingEvidence } from "@/features/evidence/missing-evidence";
import { UploadDropzone } from "@/features/evidence/upload-dropzone";
import { caseEndpoints } from "@/lib/api/endpoints";
import { qk } from "@/lib/api/query-keys";

export default function EvidenceVaultPage() {
  const params = useParams<{ caseId: string }>();
  const caseId = Number(params.caseId);
  const caseQ = useQuery({
    queryKey: qk.caseDetail(caseId),
    queryFn: () => caseEndpoints.get(caseId),
  });

  if (caseQ.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-ink-mute">
        <Spinner /> Loading case…
      </div>
    );
  }
  if (caseQ.isError) return <ErrorState onRetry={() => caseQ.refetch()} />;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={`Evidence Vault · ${caseQ.data?.court_or_forum ?? ""}`}
        title={caseQ.data?.case_name ?? "Evidence Vault"}
        subtitle="Ingest evidence as PDFs. Glimmora extracts text, segments it into citeable chunks, normalises entities, partitions them by legal meaning, and indexes them for retrieval and chat."
      />

      <Tabs defaultValue="upload">
        <TabsList>
          <TabsTrigger value="upload">Upload &amp; ingest</TabsTrigger>
          <TabsTrigger value="store">Canonical store</TabsTrigger>
          <TabsTrigger value="entities">Entities</TabsTrigger>
          <TabsTrigger value="contradictions">Contradictions</TabsTrigger>
          <TabsTrigger value="missing">Missing evidence</TabsTrigger>
          <TabsTrigger value="chat">Evidence chat</TabsTrigger>
          <TabsTrigger value="analysis">Final analysis</TabsTrigger>
        </TabsList>

        <TabsContent value="upload">
          <div className="grid gap-8 lg:grid-cols-[1fr_1.2fr]">
            <section className="surface p-6">
              <UploadDropzone caseId={caseId} />
            </section>
            <section className="space-y-3">
              <h2 className="font-display text-base text-ink">Ingested documents</h2>
              <DocumentList caseId={caseId} />
            </section>
          </div>
        </TabsContent>

        <TabsContent value="store">
          <CanonicalStore caseId={caseId} />
        </TabsContent>
        <TabsContent value="entities">
          <EntityExplorer caseId={caseId} />
        </TabsContent>
        <TabsContent value="contradictions">
          <ContradictionsLedger caseId={caseId} />
        </TabsContent>
        <TabsContent value="missing">
          <MissingEvidence caseId={caseId} />
        </TabsContent>

        <TabsContent value="chat">
          <EvidenceChat caseId={caseId} />
        </TabsContent>

        <TabsContent value="analysis">
          <FinalAnalysis caseId={caseId} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
