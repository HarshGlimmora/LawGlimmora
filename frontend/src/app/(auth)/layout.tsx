import { Brandbar } from "@/components/layout/brandbar";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <Brandbar />
      <main className="flex-1">
        <div className="container py-12 lg:py-16">{children}</div>
      </main>
      <footer className="border-t border-rule-soft py-5">
        <div className="container flex items-center justify-between font-mono text-[0.62rem] uppercase tracking-[0.18em] text-ink-faint">
          <span>Glimmora Law · Private alpha</span>
          <span>Bombay · Delhi · Bengaluru</span>
        </div>
      </footer>
    </div>
  );
}
