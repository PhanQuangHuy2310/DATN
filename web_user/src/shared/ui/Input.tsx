import { forwardRef, type InputHTMLAttributes, type ReactNode } from "react";
import { cn } from "@/shared/lib/cn";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
  error?: string;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
  wrapperClassName?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, hint, error, leftIcon, rightIcon, id, className, wrapperClassName, ...props }, ref) => {
    const inputId = id ?? props.name;
    return (
      <div className={cn("flex flex-col gap-1.5", wrapperClassName)}>
        {label && (
          <label htmlFor={inputId} className="text-[13px] font-medium text-graphite">
            {label}
          </label>
        )}
        <div className="relative flex items-center">
          {leftIcon && (
            <span className="pointer-events-none absolute left-3 text-fog">{leftIcon}</span>
          )}
          <input
            ref={ref}
            id={inputId}
            className={cn(
              "h-10 w-full rounded-[8.8px] border bg-white px-3 text-sm text-ink placeholder:text-fog/70",
              "transition-colors focus:outline-none focus:border-cobalt focus:ring-2 focus:ring-cobalt/15",
              leftIcon && "pl-9",
              rightIcon && "pr-9",
              error ? "border-error" : "border-line",
              className,
            )}
            aria-invalid={!!error}
            {...props}
          />
          {rightIcon && <span className="absolute right-3 text-fog">{rightIcon}</span>}
        </div>
        {error ? (
          <span className="text-xs text-error">{error}</span>
        ) : hint ? (
          <span className="text-xs text-fog">{hint}</span>
        ) : null}
      </div>
    );
  },
);
Input.displayName = "Input";
