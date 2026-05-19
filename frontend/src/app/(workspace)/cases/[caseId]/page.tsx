"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, BookOpen, FileText, Lock, MessagesSquare, Mic, ScrollText } from "lucide-react";
import Link from "next/link";
import { notFound, useParams } from "next/navigation";

import { Eyebrow } from "@/components/atoms/eyebrow";
import { ErrorState } from "@/components/feedback/error-state";
import { Spinner } from "@/components/feedback/spinner";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { caseEndpoints } from "@/lib/api/endpoints";
import { qk } from "@/lib/api/query-keys";
import { ApiError } from "@/lib/api/client";
import { fmtDate } from "@/lib/format";

const URGENCY_TONE: Record<string, "danger" | "accent" | "default"> = {
  Critical: "danger",
  Urgent: "danger",
  Elevated: "accent",
  Routine: "default",
};

export default function CaseDetailPage() {
  const params = useParams<{ caseId: string }>();
  const caseId = Number(params.caseId);
  const q = useQuery({
    queryKey: qk.caseDetail(caseId),
    queryFn: () => caseEndpoints.get(caseId),
  });

  if (q.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-ink-mute">
        <Spinner /> Loading case…
      </div>
    );
  }
  if (q.isError) {
    if (q.error instanceof ApiError && q.error.status === 404) notFound();
    return <ErrorState onRetry={() => q.refetch()} />;
  }
  const c = q.data!;
  const urgency = URGENCY_TONE[c.urgency_level] ?? "default";
  const confTone =
    c.confidentiality_level === "Privileged" || c.confidentiality_level === "Sealed"
      ? "warning"
      : "default";

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow={c.court_or_forum}
        title={c.case_name}
        subtitle={c.short_case_summary}
        action={
          <Button asChild variant="primary">
            <Link href={`/cases/${c.id}/evidence`}>
              Open evidence vault
              <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        }
      />
      <div className="flex flex-wrap gap-1.5">
        <Badge>{c.case_status}</Badge>
        <Badge tone={urgency}>{c.urgency_level}</Badge>
        <Badge tone={confTone}>{c.confidentiality_level}</Badge>
        <Badge tone="outline">{c.case_type}</Badge>
      </div>

      <Separator />

      <div className="grid gap-8 lg:grid-cols-[1.4fr_1fr]">
        <div className="space-y-6">
          <Card className="p-6">
            <Eyebrow>Parties &amp; role</Eyebrow>
            <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-4 text-sm">
              <Kv label="Client" value={c.client_name} />
              <Kv label="Your role" value={c.your_role_in_case} />
              <Kv label="Opposing party" value={c.opposing_party_name} />
              <Kv label="Jurisdiction" value={c.jurisdiction} />
              <Kv label="All parties" value={c.party_names} colSpan />
            </dl>
          </Card>

          {c.internal_notes && (
            <Card className="p-6">
              <Eyebrow>Internal notes</Eyebrow>
              <p className="mt-3 whitespace-pre-line text-[0.92rem] leading-relaxed text-ink-soft">
                {c.internal_notes}
              </p>
            </Card>
          )}
        </div>

        <div className="space-y-6">
          <Card className="p-6">
            <Eyebrow>Key dates</Eyebrow>
            <dl className="mt-4 space-y-3 text-sm">
              <Kv label="Filing date" value={fmtDate(c.filing_date)} />
              <Kv label="Next hearing" value={fmtDate(c.next_hearing_date)} />
            </dl>
          </Card>

          <Card className="p-6">
            <Eyebrow>Case workspace</Eyebrow>
            <ul className="mt-4 divide-y divide-rule-soft">
              <PackageRow caseId={c.id} live label="Evidence Vault" icon={<FileText className="h-3.5 w-3.5" />} href={`/cases/${c.id}/evidence`} />
              <PackageRow caseId={c.id} live label="Research & Precedent Engine" icon={<BookOpen className="h-3.5 w-3.5" />} href={`/cases/${c.id}/research`} />
              <PackageRow caseId={c.id} label="Case Study Simulator" icon={<Mic className="h-3.5 w-3.5" />} />
              <PackageRow caseId={c.id} label="Lawyer Copilot Workspace" icon={<MessagesSquare className="h-3.5 w-3.5" />} />
              <PackageRow caseId={c.id} live label="Final Case Intelligence Report" icon={<ScrollText className="h-3.5 w-3.5" />} href={`/cases/${c.id}/report`} />
            </ul>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Kv({ label, value, colSpan }: { label: string; value: string; colSpan?: boolean }) {
  return (
    <div className={colSpan ? "col-span-2" : undefined}>
      <dt className="font-mono text-[0.6rem] uppercase tracking-[0.16em] text-ink-mute">
        {label}
      </dt>
      <dd className="mt-0.5 text-ink-soft">{value || "—"}</dd>
    </div>
  );
}

function PackageRow({
  label,
  icon,
  live,
  href,
}: {
  caseId: number;
  label: string;
  icon: React.ReactNode;
  live?: boolean;
  href?: string;
}) {
  const body = (
    <div className="flex items-center justify-between gap-3 py-3 text-sm">
      <span className="inline-flex items-center gap-2 text-ink-soft">
        <span className="text-ink-mute">{icon}</span>
        <span>{label}</span>
      </span>
      {live ? (
        <Badge tone="success">Live</Badge>
      ) : (
        <span className="inline-flex items-center gap-1 text-[0.7rem] text-ink-faint">
          <Lock className="h-3 w-3" /> Coming
        </span>
      )}
    </div>
  );
  return live && href ? (
    <li>
      <Link href={href} className="block transition-colors hover:text-ink">
        {body}
      </Link>
    </li>
  ) : (
    <li>{body}</li>
  );
}
