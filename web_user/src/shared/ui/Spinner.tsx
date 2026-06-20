import { Loader2 } from "lucide-react";
import { cn } from "@/shared/lib/cn";

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("size-5 animate-spin text-cobalt", className)} aria-label="Đang tải" />;
}
