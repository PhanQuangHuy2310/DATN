import { type HTMLAttributes } from "react";
import { cn } from "@/shared/lib/cn";

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  hoverable?: boolean;
  padded?: boolean;
}

/** Flat Pure-White card on the Paper canvas — hairline border, no shadow. */
export function Card({ hoverable, padded, className, ...props }: CardProps) {
  return (
    <div
      className={cn(
        "rounded-[8.8px] border border-line bg-white",
        padded && "p-5",
        hoverable && "card-hover",
        className,
      )}
      {...props}
    />
  );
}
