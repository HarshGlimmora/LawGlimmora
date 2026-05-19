"use client";

import Link from "next/link";
import { useEffect } from "react";

import { Brandbar } from "@/components/layout/brandbar";
import { Eyebrow } from "@/components/atoms/eyebrow";
import { Button } from "@/components/ui/button";
import { log } from "@/lib/logger";

/**
 * Segment-level error boundary. Catches render-time crashes inside any
 * route below `app/` and gives the lawyer an honest "try again" surface
 * instead of a blank page or an unhandled exception.
 */
export default function GlobalSegmentError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    log.error("render", error.message, { digest: error.digest });
  }, [error]);

  return (
    <div className="flex min-h-screen flex-col">
      <Brandbar />
      <main className="flex-1">
        <div className="container flex min-h-[60vh] flex-col items-start justify-center gap-5 py-16">
          <Eyebrow>Workspace error</Eyebrow>
          <h1 className="max-w-2xl text-balance">
            Something went wrong rendering this page.
          </h1>
          <p className="max-w-xl text-[0.95rem] leading-relaxed text-ink-soft">
            The workspace hit an unexpected error. Try again, or return to your
            dashboard. If this keeps happening, share the trace id with the
            team.
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
      </main>
    </div>
  );
}
