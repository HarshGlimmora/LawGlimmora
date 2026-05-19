"use client";

import { ArrowUpRight } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { fmtDate } from "@/lib/format";
import type { Case } from "@/types/api";

const URGENCY_TONE: Record<string, "danger" | "accent" | "default"> = {
  Critical: "danger",
  Urgent: "danger",
  Elevated: "accent",
  Routine: "default",
};

const CONF_TONE: Record<string, "warning" | "default"> = {
  Privileged: "warning",
  Sealed: "warning",
};

export function CaseCard({ data }: { data: Case }) {
  const urgency = URGENCY_TONE[data.urgency_level] ?? "default";
  const conf = CONF_TONE[data.confidentiality_level] ?? "default";

  return (
    <article className="group surface relative overflow-hidden p-5 transition-shadow hover:shadow-[0_1px_0_#E4DDCC,0_8px_24px_-12px_rgba(15,20,25,0.18)]">
      <Link
        href={`/cases/${data.id}`}
        className="absolute inset-0"
        aria-label={`Open case ${data.case_name}`}
      />
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h3 className="truncate font-display text-lg text-ink">{data.case_name}</h3>
          <div className="mt-1 truncate text-sm text-ink-mute">
            {data.court_or_forum} · {data.case_type}
          </div>
        </div>
        <ArrowUpRight className="h-4 w-4 shrink-0 text-ink-faint transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-accent" />
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <div>
          <dt className="font-mono text-[0.6rem] uppercase tracking-[0.16em] text-ink-mute">
            Filed
          </dt>
          <dd className="text-ink-soft">{fmtDate(data.filing_date)}</dd>
        </div>
        <div>
          <dt className="font-mono text-[0.6rem] uppercase tracking-[0.16em] text-ink-mute">
            Next hearing
          </dt>
          <dd className="text-ink-soft">{fmtDate(data.next_hearing_date)}</dd>
        </div>
      </dl>

      <div className="mt-4 flex flex-wrap gap-1.5">
        <Badge>{data.case_status}</Badge>
        <Badge tone={urgency}>{data.urgency_level}</Badge>
        <Badge tone={conf}>{data.confidentiality_level}</Badge>
      </div>
    </article>
  );
}
