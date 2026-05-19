import { Spinner } from "@/components/feedback/spinner";

export default function WorkspaceLoading() {
  return (
    <div className="flex min-h-[40vh] items-center gap-2 text-sm text-ink-mute">
      <Spinner /> Loading workspace…
    </div>
  );
}
