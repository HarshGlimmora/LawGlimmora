import { Lock } from "lucide-react";

import { EmptyState } from "@/components/feedback/empty-state";

interface ComingSoonTabProps {
  title: string;
  description: string;
}

export function ComingSoonTab({ title, description }: ComingSoonTabProps) {
  return (
    <EmptyState
      title={`${title} — coming in this milestone`}
      description={description}
      icon={<Lock className="h-5 w-5" />}
    />
  );
}
