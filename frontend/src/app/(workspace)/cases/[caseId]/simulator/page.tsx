"use client";

import { useParams } from "next/navigation";

import { PackagePlaceholder } from "@/features/placeholders/package-placeholder";

export default function SimulatorPage() {
  const params = useParams<{ caseId: string }>();
  return (
    <PackagePlaceholder
      eyebrow="Package 3"
      title="Case Study Simulator"
      status="planned"
      description="Voice rehearsal with the case file. Opposing counsel, witness cross-examination, mock courtroom, and chronology builder — each scenario draws on the evidence vault and research engine."
      capabilities={[
        "Push-to-talk with the case-grounded opposing counsel",
        "Witness cross-examination drills with branching",
        "Mock-courtroom sessions with structured transcripts",
        "Chronology builder seeded from the evidence partitions",
        "Session replay with citations and weak-spot tagging",
      ]}
      caseId={Number(params.caseId)}
    />
  );
}
