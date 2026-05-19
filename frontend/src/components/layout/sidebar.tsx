"use client";

import {
  BookOpen,
  FileText,
  Gavel,
  LayoutDashboard,
  Lock,
  MessagesSquare,
  Mic,
  ScrollText,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const NAV_PRIMARY = [
  { href: "/dashboard", label: "Workspace", icon: LayoutDashboard },
];

interface CaseNavItem {
  href: string;
  label: string;
  icon: typeof LayoutDashboard;
  status: "live" | "soon";
}

function caseNav(caseId: number): CaseNavItem[] {
  return [
    { href: `/cases/${caseId}`, label: "Case overview", icon: Gavel, status: "live" },
    { href: `/cases/${caseId}/evidence`, label: "Evidence vault", icon: FileText, status: "live" },
    { href: `/cases/${caseId}/research`, label: "Research engine", icon: BookOpen, status: "live" },
    { href: `/cases/${caseId}/simulator`, label: "Case simulator", icon: Mic, status: "soon" },
    { href: `/cases/${caseId}/copilot`, label: "Copilot workspace", icon: MessagesSquare, status: "soon" },
    { href: `/cases/${caseId}/report`, label: "Final report", icon: ScrollText, status: "live" },
  ];
}

export function WorkspaceSidebar({ activeCaseId }: { activeCaseId?: number }) {
  const pathname = usePathname();

  return (
    <aside className="hidden border-r border-rule-soft bg-parchment-soft/60 md:flex md:w-64 md:shrink-0 md:flex-col">
      <nav className="flex-1 space-y-8 px-4 py-6">
        <div className="space-y-1">
          <div className="px-2 pb-2 font-mono text-[0.62rem] uppercase tracking-[0.22em] text-ink-mute">
            Chambers
          </div>
          {NAV_PRIMARY.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors",
                  active
                    ? "bg-card text-ink shadow-sm"
                    : "text-ink-soft hover:bg-card/60 hover:text-ink",
                )}
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </div>

        {activeCaseId && (
          <div className="space-y-1">
            <div className="px-2 pb-2 font-mono text-[0.62rem] uppercase tracking-[0.22em] text-ink-mute">
              Case · #{activeCaseId}
            </div>
            {caseNav(activeCaseId).map((item) => {
              const active = pathname === item.href;
              const Icon = item.icon;
              const disabled = item.status === "soon";
              return (
                <Link
                  key={item.href}
                  href={disabled ? "#" : item.href}
                  aria-disabled={disabled}
                  onClick={(e) => disabled && e.preventDefault()}
                  className={cn(
                    "flex items-center justify-between gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors",
                    active
                      ? "bg-card text-ink shadow-sm"
                      : disabled
                        ? "text-ink-faint hover:bg-transparent"
                        : "text-ink-soft hover:bg-card/60 hover:text-ink",
                  )}
                >
                  <span className="flex items-center gap-2.5">
                    <Icon className="h-4 w-4" />
                    {item.label}
                  </span>
                  {disabled && <Lock className="h-3 w-3 text-ink-faint" aria-hidden />}
                </Link>
              );
            })}
          </div>
        )}
      </nav>

      <div className="border-t border-rule-soft px-4 py-4 font-mono text-[0.62rem] uppercase tracking-[0.18em] text-ink-faint">
        Private alpha
      </div>
    </aside>
  );
}
