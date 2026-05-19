"use client";

import { useQuery } from "@tanstack/react-query";
import { BookOpen, FileText, Gavel, MessagesSquare, Mic, Plus, ScrollText } from "lucide-react";
import Link from "next/link";

import { CaseCard } from "@/components/cards/case-card";
import { PackageCard } from "@/components/cards/package-card";
import { StatCard } from "@/components/cards/stat-card";
import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { Spinner } from "@/components/feedback/spinner";
import { Eyebrow } from "@/components/atoms/eyebrow";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { caseEndpoints, profileEndpoints } from "@/lib/api/endpoints";
import { qk } from "@/lib/api/query-keys";

export default function DashboardPage() {
  const profile = useQuery({ queryKey: qk.profile, queryFn: profileEndpoints.get });
  const cases = useQuery({ queryKey: qk.cases, queryFn: caseEndpoints.list });

  if (profile.isLoading || cases.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-ink-mute">
        <Spinner /> Loading workspace…
      </div>
    );
  }
  if (cases.isError) {
    return <ErrorState onRetry={() => cases.refetch()} />;
  }

  const list = cases.data ?? [];
  const today = new Date().toISOString().slice(0, 10);
  const upcoming = list.filter((c) => c.next_hearing_date && c.next_hearing_date >= today).length;
  const urgent = list.filter((c) => ["Urgent", "Critical"].includes(c.urgency_level)).length;

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow={`Workspace · ${profile.data?.firm_name ?? "Independent counsel"}`}
        title={`Good day, ${profile.data?.display_name ?? "Counsel"}.`}
        subtitle="Your active matters, hearings, and case workspaces. Each case carries its own evidence, research, rehearsal, and intelligence layers."
        action={
          <Button asChild variant="primary">
            <Link href="/cases/new">
              <Plus className="h-4 w-4" />
              New case
            </Link>
          </Button>
        }
      />

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard value={list.length} label="Active cases" />
        <StatCard value={upcoming} label="Upcoming hearings" />
        <StatCard value={urgent} label="Urgent matters" />
        <StatCard value={profile.data?.years_of_experience ?? 0} label="Years at the bar" />
      </section>

      <Separator />

      <div className="grid gap-10 lg:grid-cols-[1.6fr_1fr]">
        <section className="space-y-4">
          <Eyebrow>Your cases</Eyebrow>
          {list.length === 0 ? (
            <EmptyState
              title="No cases yet"
              description="Open your first matter to set up its workspace."
              action={
                <Button asChild variant="primary">
                  <Link href="/cases/new">Open a case</Link>
                </Button>
              }
            />
          ) : (
            <div className="grid gap-4">
              {list.map((c) => (
                <CaseCard key={c.id} data={c} />
              ))}
            </div>
          )}
        </section>

        <section className="space-y-3">
          <Eyebrow>Future packages</Eyebrow>
          <p className="text-sm text-ink-mute">
            Each case workspace will host these five layers. Architecture and persistence are already in place.
          </p>
          <div className="space-y-3 pt-1">
            <PackageCard
              title="Evidence Vault"
              description="Citeable chunks, entity extraction, missing-evidence detection, argument-fit scoring."
              status="live"
              icon={<FileText className="h-4 w-4" />}
            />
            <PackageCard
              title="Research & Precedent Engine"
              description="Natural-language legal search, judgment summarisation, citation suggestions."
              icon={<BookOpen className="h-4 w-4" />}
            />
            <PackageCard
              title="Case Study Simulator"
              description="Voice rehearsal — opposing counsel, witness cross, mock courtroom, chronology builder."
              icon={<Mic className="h-4 w-4" />}
            />
            <PackageCard
              title="Lawyer Copilot Workspace"
              description="Voice-to-note drafting, petition drafts, follow-ups, multilingual output."
              icon={<MessagesSquare className="h-4 w-4" />}
            />
            <PackageCard
              title="Final Case Intelligence Report"
              description="Strength, weakness, hearing readiness, recommended next actions — one scorecard."
              icon={<ScrollText className="h-4 w-4" />}
            />
          </div>
        </section>
      </div>
    </div>
  );
}
