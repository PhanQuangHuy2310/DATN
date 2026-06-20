import { forwardRef, type ButtonHTMLAttributes } from "react";
import { Loader2 } from "lucide-react";
import { cn } from "@/shared/lib/cn";

type Variant = "primary" | "secondary" | "ghost" | "subtle" | "danger" | "link";
type Size = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  block?: boolean;
}

const base =
  "inline-flex items-center justify-center gap-2 rounded-[8.8px] font-medium transition-colors disabled:opacity-50 disabled:pointer-events-none select-none";

const variants: Record<Variant, string> = {
  // The only filled chromatic button — Cobalt Stamp is the elevation.
  primary: "bg-cobalt text-white hover:bg-cobalt-hover",
  secondary: "bg-charcoal text-white hover:bg-ink",
  ghost: "bg-transparent border border-line text-ink hover:bg-paper",
  subtle: "bg-chalk text-ink hover:bg-ash/60",
  danger: "bg-error text-white hover:opacity-90",
  link: "bg-transparent text-cobalt hover:underline px-0",
};

const sizes: Record<Size, string> = {
  sm: "h-8 px-3 text-[13px]",
  md: "h-10 px-[18px] text-sm",
  lg: "h-12 px-6 text-base",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    { variant = "primary", size = "md", loading, block, className, children, disabled, type = "button", ...props },
    ref,
  ) => (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      className={cn(
        base,
        variants[variant],
        variant !== "link" && sizes[size],
        block && "w-full",
        className,
      )}
      {...props}
    >
      {loading && <Loader2 className="size-4 animate-spin" aria-hidden />}
      {children}
    </button>
  ),
);
Button.displayName = "Button";
