import { type HTMLAttributes } from "react";
import { cn } from "@/shared/lib/cn";

type Tone = "neutral" | "cobalt" | "success" | "warning" | "error" | "outline";

const tones: Record<Tone, string> = {
  neutral: "bg-chalk text-graphite",
  cobalt: "bg-cobalt-soft text-cobalt",
  success: "bg-success-soft text-success",
  warning: "bg-warning-soft text-warning",
  error: "bg-error-soft text-error",
  outline: "border border-line text-fog",
};

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
  dot?: boolean;
}

export function Badge({ tone = "neutral", dot, className, children, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
        tones[tone],
        className,
      )}
      {...props}
    >
      {dot && <span className="size-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}
