import { useState, type ReactNode } from "react";
import { cn } from "@/shared/lib/cn";

export interface TooltipProps {
  content: ReactNode;
  children: ReactNode;
  side?: "top" | "bottom";
  open?: boolean;
  tone?: "ink" | "error";
}

export function Tooltip({ content, children, side = "top", open, tone = "ink" }: TooltipProps) {
  const [hover, setHover] = useState(false);
  const visible = open ?? hover;
  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      {children}
      {visible && content && (
        <span
          role="tooltip"
          className={cn(
            "pointer-events-none absolute left-1/2 z-30 w-max max-w-xs -translate-x-1/2 rounded-[8.8px] px-2.5 py-1.5 text-xs text-white",
            tone === "error" ? "bg-error" : "bg-ink",
            side === "top" ? "bottom-full mb-2" : "top-full mt-2",
          )}
        >
          {content}
        </span>
      )}
    </span>
  );
}
