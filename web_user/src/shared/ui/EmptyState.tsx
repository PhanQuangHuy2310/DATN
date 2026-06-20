import { type ReactNode } from "react";
import { SearchX } from "lucide-react";
import { cn } from "@/shared/lib/cn";

export interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-3 px-6 py-12 text-center", className)}>
      <div className="flex size-16 items-center justify-center rounded-full bg-chalk text-fog">
        {icon ?? <SearchX className="size-7" />}
      </div>
      <div className="max-w-sm space-y-1">
        <p className="font-medium text-ink">{title}</p>
        {description && <p className="text-sm text-fog">{description}</p>}
      </div>
      {action}
    </div>
  );
}
