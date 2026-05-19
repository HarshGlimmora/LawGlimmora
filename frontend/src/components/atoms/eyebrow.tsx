import { cn } from "@/lib/utils";

export function Eyebrow({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex items-center gap-2 font-mono text-[0.66rem] uppercase tracking-[0.18em] text-ink-mute",
        className,
      )}
    >
      <span className="h-px w-6 bg-rule" aria-hidden />
      {children}
    </div>
  );
}
