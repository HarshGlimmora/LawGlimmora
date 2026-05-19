import Link from "next/link";

import { cn } from "@/lib/utils";

/**
 * Custom wordmark — serif "Glimmora" with a sealed dot. Avoids the
 * generic "logo as an icon-plus-text" template.
 */
export function Brandmark({
  href = "/",
  className,
  size = "md",
}: {
  href?: string;
  className?: string;
  size?: "sm" | "md";
}) {
  return (
    <Link
      href={href}
      className={cn(
        "group inline-flex items-baseline gap-2 font-display tracking-tight text-ink",
        size === "sm" ? "text-base" : "text-lg",
        className,
      )}
    >
      <span className="relative">
        Glimmora
        <span
          className="absolute -right-2 top-1.5 h-1 w-1 rounded-full bg-seal"
          aria-hidden
        />
      </span>
      <span className="font-mono text-[0.62rem] uppercase tracking-[0.22em] text-ink-mute">
        Lawyer
      </span>
    </Link>
  );
}
