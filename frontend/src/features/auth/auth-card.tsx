"use client";

import { useState } from "react";

import { LoginForm } from "@/features/auth/login-form";
import { SignupForm } from "@/features/auth/signup-form";
import { Eyebrow } from "@/components/atoms/eyebrow";
import { cn } from "@/lib/utils";

export function AuthCard() {
  const [tab, setTab] = useState<"login" | "signup">("login");

  return (
    <section className="surface overflow-hidden">
      <div className="px-7 pt-7">
        <Eyebrow>Counsel access</Eyebrow>
        <div role="tablist" className="mt-5 flex items-center gap-1 border-b border-rule-soft">
          <TabButton active={tab === "login"} onClick={() => setTab("login")}>
            Sign in
          </TabButton>
          <TabButton active={tab === "signup"} onClick={() => setTab("signup")}>
            Create account
          </TabButton>
        </div>
      </div>
      <div className="p-7">
        {tab === "login" ? <LoginForm /> : <SignupForm onSignedUp={() => setTab("login")} />}
      </div>
    </section>
  );
}

function TabButton({
  active,
  children,
  onClick,
}: {
  active: boolean;
  children: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={cn(
        "relative -mb-px h-10 px-3 text-sm transition-colors",
        active
          ? "text-ink after:absolute after:inset-x-0 after:-bottom-px after:h-[2px] after:bg-accent"
          : "text-ink-mute hover:text-ink",
      )}
    >
      {children}
    </button>
  );
}
