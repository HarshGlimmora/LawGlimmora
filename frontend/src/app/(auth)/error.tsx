"use client";

import { useEffect } from "react";

import { Eyebrow } from "@/components/atoms/eyebrow";
import { Button } from "@/components/ui/button";
import { log } from "@/lib/logger";

export default function AuthError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    log.error("auth", error.message, { digest: error.digest });
  }, [error]);

  return (
    <div className="mx-auto max-w-md py-10">
      <Eyebrow>Sign-in error</Eyebrow>
      <h1 className="mt-3">Sign-in failed to load.</h1>
      <p className="mt-3 text-sm text-ink-soft">
        The sign-in surface crashed. This is usually a transient network
        issue. Try again, or refresh the page.
      </p>
      {error.digest && (
        <code className="mt-3 inline-block rounded border border-rule bg-card px-2 py-1 font-mono text-[0.7rem] text-ink-mute">
          trace: {error.digest}
        </code>
      )}
      <div className="mt-5">
        <Button variant="primary" onClick={() => reset()}>
          Try again
        </Button>
      </div>
    </div>
  );
}
