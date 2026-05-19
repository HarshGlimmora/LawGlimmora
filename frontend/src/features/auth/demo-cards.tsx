"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Eyebrow } from "@/components/atoms/eyebrow";
import { Spinner } from "@/components/feedback/spinner";
import { ApiError } from "@/lib/api/client";
import { authEndpoints } from "@/lib/api/endpoints";
import { qk } from "@/lib/api/query-keys";

const DEMOS = [
  {
    slug: "anika" as const,
    name: "Anika Rao",
    role: "Counsel · Commercial Litigation",
    blurb:
      "Partner at Rao & Mehta Associates. Pre-loaded with the Aurelia Ventures dispute pending before the Bombay High Court.",
  },
  {
    slug: "vikram" as const,
    name: "Vikram Shastri",
    role: "Senior Counsel · Constitutional & Writ",
    blurb:
      "Independent senior counsel. Pre-loaded with a live writ petition before the Bombay High Court under Article 226.",
  },
];

export function DemoCards() {
  const router = useRouter();
  const qc = useQueryClient();
  const mutation = useMutation({
    mutationFn: (slug: "anika" | "vikram") => authEndpoints.demoLogin(slug),
    onSuccess: (user) => {
      qc.setQueryData(qk.me, user);
      router.replace(user.has_profile ? "/dashboard" : "/profile-setup");
    },
  });

  const error =
    mutation.error instanceof ApiError ? mutation.error.message : null;

  return (
    <section className="surface p-7">
      <Eyebrow>One-tap demo access</Eyebrow>
      <p className="mt-2 text-sm text-ink-mute">
        Two seeded lawyer accounts with a fully formed profile and a pre-loaded case —
        open the workspace instantly.
      </p>
      <div className="mt-5 space-y-4">
        {DEMOS.map((d, i) => (
          <article
            key={d.slug}
            className="group rounded-md border border-rule bg-parchment-soft/70 p-5 animate-fade-in"
            style={{ animationDelay: `${120 * (i + 1)}ms`, animationFillMode: "backwards" }}
          >
            <div className="font-display text-base text-ink">{d.name}</div>
            <div className="mt-0.5 font-mono text-[0.66rem] uppercase tracking-[0.18em] text-accent">
              {d.role}
            </div>
            <p className="mt-3 text-sm leading-relaxed text-ink-soft">{d.blurb}</p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="mt-4 w-full justify-between"
              onClick={() => mutation.mutate(d.slug)}
              disabled={mutation.isPending}
            >
              <span className="inline-flex items-center gap-2">
                {mutation.isPending && mutation.variables === d.slug && <Spinner />}
                Sign in as {d.name.split(" ")[0]}
              </span>
              <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
            </Button>
          </article>
        ))}
        {error && <p className="text-sm text-danger">{error}</p>}
      </div>
    </section>
  );
}
