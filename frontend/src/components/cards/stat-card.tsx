import { Card } from "@/components/ui/card";

interface StatCardProps {
  value: string | number;
  label: string;
  hint?: string;
}

export function StatCard({ value, label, hint }: StatCardProps) {
  return (
    <Card className="px-5 py-4">
      <div className="font-display text-3xl font-medium text-ink">{value}</div>
      <div className="mt-1 font-mono text-[0.62rem] uppercase tracking-[0.18em] text-ink-mute">
        {label}
      </div>
      {hint && <div className="mt-2 text-xs text-ink-mute">{hint}</div>}
    </Card>
  );
}
