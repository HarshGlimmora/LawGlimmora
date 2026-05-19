"use client";

import { useParams } from "next/navigation";

import { PackagePlaceholder } from "@/features/placeholders/package-placeholder";

export default function CopilotPage() {
  const params = useParams<{ caseId: string }>();
  return (
    <PackagePlaceholder
      eyebrow="Package 4"
      title="Lawyer Copilot Workspace"
      status="planned"
      description="A drafting and dispatch surface for counsel. Voice-to-note capture, petition drafts, follow-ups, and multilingual output — all grounded in the case context."
      capabilities={[
        "Voice-to-note capture with speaker diarisation",
        "Petition and pleading drafts grounded in case facts",
        "Follow-up checklists and notice-period reminders",
        "Multilingual output (English, Hindi, Marathi, more)",
        "Outbox of dispatches with copies preserved in the vault",
      ]}
      caseId={Number(params.caseId)}
    />
  );
}
