import Link from "next/link";

import { Brandbar } from "@/components/layout/brandbar";
import { Eyebrow } from "@/components/atoms/eyebrow";
import { Button } from "@/components/ui/button";

export const metadata = { title: "Not found · Glimmora Lawyer" };

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col">
      <Brandbar />
      <main className="flex-1">
        <div className="container flex min-h-[60vh] flex-col items-start justify-center gap-5 py-16">
          <Eyebrow>404 · Not on file</Eyebrow>
          <h1 className="max-w-2xl text-balance">
            This page is not in your workspace.
          </h1>
          <p className="max-w-xl text-[0.95rem] leading-relaxed text-ink-soft">
            The case file you tried to open does not exist, has been moved, or
            you may not have access. Head back to your workspace and try again
            from the dashboard.
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <Button asChild variant="primary">
              <Link href="/dashboard">Open the workspace</Link>
            </Button>
            <Button asChild variant="ghost">
              <Link href="/login">Sign in instead</Link>
            </Button>
          </div>
        </div>
      </main>
      <footer className="border-t border-rule-soft py-5">
        <div className="container font-mono text-[0.62rem] uppercase tracking-[0.18em] text-ink-faint">
          Glimmora Law · Private alpha
        </div>
      </footer>
    </div>
  );
}
