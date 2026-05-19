import { Spinner } from "@/components/feedback/spinner";

export default function RootLoading() {
  return (
    <main className="flex min-h-screen items-center justify-center">
      <div className="flex items-center gap-2 text-sm text-ink-mute">
        <Spinner /> Opening the workspace…
      </div>
    </main>
  );
}
