import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { Brandbar } from "@/components/layout/brandbar";
import { WorkspaceShell } from "@/app/(workspace)/workspace-shell";

export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  if (!cookies().has("glimmora_session")) {
    redirect("/login");
  }
  return (
    <div className="flex min-h-screen flex-col">
      <Brandbar userLabel="Counsel" />
      <WorkspaceShell>{children}</WorkspaceShell>
    </div>
  );
}
