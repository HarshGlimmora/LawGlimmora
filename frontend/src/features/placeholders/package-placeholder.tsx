import { ArrowLeft, Lock } from "lucide-react";
import Link from "next/link";

import { Eyebrow } from "@/components/atoms/eyebrow";
import { Button } from "@/components/ui/button";

interface PackagePlaceholderProps {
  eyebrow: string;
  title: string;
  status: "backend-ready" | "planned";
  description: string;
  capabilities: string[];
  caseId: number;
}

export function PackagePlaceholder({
  eyebrow,
  title,
  status,
  description,
  capabilities,
  caseId,
}: PackagePlaceholderProps) {
  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div className="space-y-3 animate-fade-in">
        <Eyebrow>{eyebrow}</Eyebrow>
        <h1>{title}</h1>
        <p className="text-[0.95rem] leading-relaxed text-ink-soft">{description}</p>
      </div>

      <div className="surface p-7">
        <div className="flex items-center gap-2 font-mono text-[0.66rem] uppercase tracking-[0.18em] text-accent">
          <Lock className="h-3 w-3" />
          {status === "backend-ready" ? "Backend live · UI pending" : "Backend planned"}
        </div>
        <ul className="mt-5 space-y-2.5">
          {capabilities.map((cap) => (
            <li key={cap} className="flex items-start gap-2.5 text-sm text-ink-soft">
              <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-accent" aria-hidden />
              {cap}
            </li>
          ))}
        </ul>
      </div>

      <Button asChild variant="ghost">
        <Link href={`/cases/${caseId}`}>
          <ArrowLeft className="h-4 w-4" />
          Back to case
        </Link>
      </Button>
    </div>
  );
}
