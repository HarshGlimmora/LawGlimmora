"use client";

import Link from "next/link";
import { useEffect } from "react";

import { Eyebrow } from "@/components/atoms/eyebrow";
import { Button } from "@/components/ui/button";
import { log } from "@/lib/logger";

export default function WorkspaceError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    log.error("workspace", error.message, { digest: error.digest });
  }, [error]);

  return (
    <div className="flex min-h-[60vh] flex-col items-start justify-center gap-5 py-16">
      <Eyebrow>Workspace error</Eyebrow>
      <h1 className="max-w-2xl text-balance">
        This page didn&rsquo;t load.
      </h1>
      <p className="max-w-xl text-[0.95rem] leading-relaxed text-ink-soft">
        The workspace shell rendered, but this section crashed. Try again, or
        return to the dashboard. The backend may be momentarily unavailable.
      </p>
      {error.digest && (
        <code className="rounded border border-rule bg-card px-2 py-1 font-mono text-[0.7rem] text-ink-mute">
          trace: {error.digest}
        </code>
      )}
      <div className="mt-2 flex flex-wrap items-center gap-3">
        <Button variant="primary" onClick={() => reset()}>
          Try again
        </Button>
        <Button asChild variant="ghost">
          <Link href="/dashboard">Back to workspace</Link>
        </Button>
      </div>
    </div>
  );
}
