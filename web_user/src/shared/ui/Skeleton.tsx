import { type HTMLAttributes } from "react";
import { cn } from "@/shared/lib/cn";

export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("skeleton rounded-[8.8px]", className)}
      aria-hidden
      {...props}
    />
  );
}
