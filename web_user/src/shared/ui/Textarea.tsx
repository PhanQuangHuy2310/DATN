import { forwardRef, type TextareaHTMLAttributes } from "react";
import { cn } from "@/shared/lib/cn";

export interface TextareaProps
  extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  hint?: string;
  shake?: boolean;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ label, error, hint, shake, id, className, ...props }, ref) => {
    const fieldId = id ?? props.name;
    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label htmlFor={fieldId} className="text-[13px] font-medium text-graphite">
            {label}
          </label>
        )}
        <textarea
          ref={ref}
          id={fieldId}
          className={cn(
            "min-h-24 w-full resize-y rounded-[8.8px] border bg-white px-3 py-2.5 text-sm text-ink placeholder:text-fog/70",
            "transition-colors focus:outline-none focus:border-cobalt focus:ring-2 focus:ring-cobalt/15",
            error ? "border-error" : "border-line",
            shake && "shake border-error",
            className,
          )}
          aria-invalid={!!error}
          {...props}
        />
        {error ? (
          <span className="text-xs text-error">{error}</span>
        ) : hint ? (
          <span className="text-xs text-fog">{hint}</span>
        ) : null}
      </div>
    );
  },
);
Textarea.displayName = "Textarea";
