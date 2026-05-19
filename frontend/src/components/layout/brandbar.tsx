"use client";

import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";

import { Brandmark } from "@/components/layout/brandmark";
import { Button } from "@/components/ui/button";
import { authEndpoints } from "@/lib/api/endpoints";
import { qk } from "@/lib/api/query-keys";
import { log } from "@/lib/logger";

interface BrandbarProps {
  userLabel?: string;
  workspace?: string;
}

export function Brandbar({ userLabel, workspace }: BrandbarProps) {
  const router = useRouter();
  const qc = useQueryClient();

  async function onLogout() {
    try {
      await authEndpoints.logout();
    } catch (err) {
      // Network errors must not strand the user on the workspace. Clear
      // local state regardless so the redirect lands them on /login.
      log.warn("auth", "logout request failed; clearing client state anyway", err);
    } finally {
      qc.setQueryData(qk.me, null);
      qc.clear();
      router.replace("/login");
    }
  }

  return (
    <header className="sticky top-0 z-30 border-b border-rule-soft bg-parchment/85 backdrop-blur">
      <div className="container flex h-14 items-center justify-between">
        <Brandmark />
        <div className="flex items-center gap-4">
          {workspace && (
            <span className="hidden text-[0.78rem] text-ink-mute md:inline">
              {workspace}
            </span>
          )}
          {userLabel && (
            <span className="hidden font-mono text-[0.7rem] uppercase tracking-[0.16em] text-ink-soft md:inline">
              {userLabel}
            </span>
          )}
          {userLabel && (
            <Button variant="ghost" size="sm" onClick={onLogout}>
              <LogOut className="h-3.5 w-3.5" />
              Sign out
            </Button>
          )}
        </div>
      </div>
    </header>
  );
}
