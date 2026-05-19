import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface PackageCardProps {
  title: string;
  description: string;
  status?: "live" | "soon";
  icon?: React.ReactNode;
  href?: string;
}

export function PackageCard({ title, description, status = "soon", icon }: PackageCardProps) {
  const live = status === "live";
  return (
    <div
      className={cn(
        "surface group p-5",
        live ? "bg-card" : "bg-parchment-soft/50",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          {icon && (
            <span
              className={cn(
                "flex h-8 w-8 items-center justify-center rounded-md border",
                live ? "border-accent/30 bg-accent-wash text-accent" : "border-rule text-ink-mute",
              )}
            >
              {icon}
            </span>
          )}
          <div>
            <div className="font-display text-base text-ink">{title}</div>
            <p className="mt-1 text-sm leading-relaxed text-ink-mute">{description}</p>
          </div>
        </div>
        <Badge tone={live ? "success" : "outline"}>{live ? "Live" : "Coming"}</Badge>
      </div>
    </div>
  );
}
