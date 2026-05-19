"use client";

import { useQuery } from "@tanstack/react-query";

import { PageHeader } from "@/components/layout/page-header";
import { CaseForm } from "@/features/case/case-form";
import { caseEndpoints } from "@/lib/api/endpoints";
import { qk } from "@/lib/api/query-keys";

export default function NewCasePage() {
  const cases = useQuery({ queryKey: qk.cases, queryFn: caseEndpoints.list });
  const first = (cases.data?.length ?? 0) === 0;

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader
        eyebrow={first ? "Step 2 · Open a case" : "Open a new case"}
        title={first ? "Open your first case" : "Open a new case"}
        subtitle="A case is the unit of work in Glimmora Lawyer. Each case carries its own evidence vault, research file, simulation transcripts, drafts, and intelligence report. Start with the basics — you can refine the rest from inside the workspace."
      />
      <div className="surface p-7">
        <CaseForm firstCase={first} />
      </div>
    </div>
  );
}
