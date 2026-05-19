"use client";

import { useParams } from "next/navigation";

import { PackagePlaceholder } from "@/features/placeholders/package-placeholder";

export default function ReportPage() {
  const params = useParams<{ caseId: string }>();
  return (
    <PackagePlaceholder
      eyebrow="Package 5"
      title="Final Case Intelligence Report"
      status="backend-ready"
      description="A single scorecard: strengths, weaknesses, hearing readiness, contradictions, missing evidence, and recommended next actions. The backend already computes the nine scores, issue matrix, and PDF / JSON / text exports. UI lands in the next milestone."
      capabilities={[
        "Nine-score readiness card with explanations and factors",
        "Issue matrix with strongest and weakest items pinned",
        "Contradiction and missing-evidence ledgers",
        "Action-ranked recommendations with citations",
        "Export to PDF, JSON, or plain-text brief",
      ]}
      caseId={Number(params.caseId)}
    />
  );
}
