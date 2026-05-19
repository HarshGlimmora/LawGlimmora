import { Eyebrow } from "@/components/atoms/eyebrow";
import { Ornament } from "@/components/atoms/ornament";
import { AuthCard } from "@/features/auth/auth-card";
import { DemoCards } from "@/features/auth/demo-cards";

export const metadata = { title: "Sign in · Glimmora Lawyer" };

export default function LoginPage() {
  return (
    <div className="grid items-start gap-10 lg:grid-cols-[1.15fr_1fr] lg:gap-14">
      <section className="space-y-7 animate-fade-in">
        <Eyebrow>A serious workspace for serious counsel</Eyebrow>
        <h1 className="text-balance">
          The case file,{" "}
          <span className="font-display italic text-accent">reimagined.</span>
        </h1>
        <p className="max-w-xl text-[1.02rem] leading-relaxed text-ink-soft">
          Glimmora Lawyer is a private workspace for litigators and counsel — one
          matter, one brain. Evidence, research, rehearsal, drafting, and a single
          case intelligence report. This foundation handles your identity, your
          profile, and your first case.
        </p>
        <Ornament />
        <DemoCards />
      </section>

      <div className="animate-fade-in" style={{ animationDelay: "100ms", animationFillMode: "backwards" }}>
        <AuthCard />
      </div>
    </div>
  );
}
