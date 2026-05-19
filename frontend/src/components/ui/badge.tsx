import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[0.72rem] font-medium",
  {
    variants: {
      tone: {
        default: "border-rule bg-parchment-soft text-ink-soft",
        accent: "border-accent/30 bg-accent-wash text-accent",
        success: "border-success/30 bg-success-wash text-success",
        warning: "border-warning/30 bg-warning-wash text-warning",
        danger: "border-danger/30 bg-danger-wash text-danger",
        outline: "border-rule bg-transparent text-ink-soft",
      },
    },
    defaultVariants: { tone: "default" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}
