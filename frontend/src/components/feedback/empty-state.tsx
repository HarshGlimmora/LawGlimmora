import { cn } from "@/lib/utils";

interface EmptyStateProps {
  title: string;
  description?: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
}

export function EmptyState({ title, description, action, icon, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-start gap-3 rounded-md border border-dashed border-rule bg-parchment-soft/60 p-8 text-left",
        className,
      )}
    >
      {icon && <div className="text-accent">{icon}</div>}
      <div className="font-display text-base text-ink">{title}</div>
      {description && <p className="text-sm text-ink-mute">{description}</p>}
      {action && <div className="pt-1">{action}</div>}
    </div>
  );
}
