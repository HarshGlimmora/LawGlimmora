"use client";

import { Check } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface MultiSelectProps {
  options: string[];
  value: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
}

/**
 * Lightweight multi-select. Avoids extra deps — renders inline checkboxes
 * with a chip summary. Good enough for the constants-driven lists.
 */
export function MultiSelect({ options, value, onChange, placeholder }: MultiSelectProps) {
  const [open, setOpen] = useState(false);

  function toggle(opt: string) {
    onChange(value.includes(opt) ? value.filter((v) => v !== opt) : [...value, opt]);
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "flex min-h-10 w-full flex-wrap items-center gap-1.5 rounded-md border border-rule bg-card px-2.5 py-1.5 text-left text-sm",
          "focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-1 focus:ring-offset-parchment",
        )}
      >
        {value.length === 0 && (
          <span className="text-ink-faint">{placeholder ?? "Select…"}</span>
        )}
        {value.map((v) => (
          <Badge key={v} tone="accent" className="font-normal">
            {v}
          </Badge>
        ))}
      </button>
      {open && (
        <>
          <button
            type="button"
            className="fixed inset-0 z-40 cursor-default"
            aria-hidden
            onClick={() => setOpen(false)}
          />
          <div className="absolute left-0 right-0 top-full z-50 mt-1 max-h-60 overflow-auto rounded-md border border-rule bg-card p-1 shadow-md">
            {options.map((opt) => {
              const selected = value.includes(opt);
              return (
                <button
                  type="button"
                  key={opt}
                  onClick={() => toggle(opt)}
                  className={cn(
                    "flex w-full items-center justify-between rounded-sm px-2 py-1.5 text-sm",
                    "hover:bg-parchment-soft",
                    selected && "text-ink",
                  )}
                >
                  <span>{opt}</span>
                  {selected && <Check className="h-3.5 w-3.5 text-accent" />}
                </button>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
