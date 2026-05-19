"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";

import { ErrorState } from "@/components/feedback/error-state";
import { Spinner } from "@/components/feedback/spinner";
import { PageHeader } from "@/components/layout/page-header";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ResearchAskPanel } from "@/features/research/ask-panel";
import { ResearchAuthorities } from "@/features/research/authorities-browser";
import { ResearchConnections } from "@/features/research/connections-panel";
import { ResearchCorpusManager } from "@/features/research/corpus-manager";
import { ResearchSessions } from "@/features/research/sessions-panel";
import { ResearchTimeline } from "@/features/research/research-timeline";
import { caseEndpoints } from "@/lib/api/endpoints";
import { qk } from "@/lib/api/query-keys";

export default function ResearchEnginePage() {
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
        eyebrow={`Research & Precedent · ${caseQ.data?.court_or_forum ?? ""}`}
        title={caseQ.data?.case_name ?? "Research Engine"}
        subtitle="Project-scoped legal research. Ingest precedents, classify the query, retrieve and rerank authorities by jurisdiction / court / recency, synthesise a cited answer, and persist every session as research memory for downstream packages."
      />

      <Tabs defaultValue="ask">
        <TabsList>
          <TabsTrigger value="ask">Ask</TabsTrigger>
          <TabsTrigger value="corpus">Corpus</TabsTrigger>
          <TabsTrigger value="authorities">Authorities</TabsTrigger>
          <TabsTrigger value="timeline">Timeline</TabsTrigger>
          <TabsTrigger value="sessions">Sessions</TabsTrigger>
          <TabsTrigger value="connections">Connections</TabsTrigger>
        </TabsList>

        <TabsContent value="ask">
          <ResearchAskPanel caseId={caseId} />
        </TabsContent>
        <TabsContent value="corpus">
          <ResearchCorpusManager caseId={caseId} />
        </TabsContent>
        <TabsContent value="authorities">
          <ResearchAuthorities caseId={caseId} />
        </TabsContent>
        <TabsContent value="timeline">
          <ResearchTimeline caseId={caseId} />
        </TabsContent>
        <TabsContent value="sessions">
          <ResearchSessions caseId={caseId} />
        </TabsContent>
        <TabsContent value="connections">
          <ResearchConnections caseId={caseId} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
