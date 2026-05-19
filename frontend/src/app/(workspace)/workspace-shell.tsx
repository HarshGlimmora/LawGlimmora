"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { Spinner } from "@/components/feedback/spinner";
import { WorkspaceSidebar } from "@/components/layout/sidebar";
import { authEndpoints, profileEndpoints } from "@/lib/api/endpoints";
import { qk } from "@/lib/api/query-keys";

export function WorkspaceShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const params = useParams<{ caseId?: string }>();
  const activeCaseId = params?.caseId ? Number(params.caseId) : undefined;

  const session = useQuery({
    queryKey: qk.me,
    queryFn: authEndpoints.me,
    retry: false,
  });

  const profile = useQuery({
    queryKey: qk.profile,
    queryFn: profileEndpoints.get,
    retry: false,
    enabled: !!session.data,
  });

  useEffect(() => {
    if (session.isError) router.replace("/login");
  }, [session.isError, router]);

  useEffect(() => {
    if (profile.isSuccess && !profile.data) router.replace("/profile-setup");
  }, [profile.isSuccess, profile.data, router]);

  if (session.isLoading || profile.isLoading) {
    return (
      <main className="flex flex-1 items-center justify-center text-sm text-ink-mute">
        <Spinner /> <span className="ml-2">Loading workspace…</span>
      </main>
    );
  }

  return (
    <div className="flex flex-1">
      <WorkspaceSidebar activeCaseId={activeCaseId} />
      <main className="flex-1">
        <div className="container py-10">{children}</div>
      </main>
    </div>
  );
}
