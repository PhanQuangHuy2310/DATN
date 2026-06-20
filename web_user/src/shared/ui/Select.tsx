import { forwardRef, type SelectHTMLAttributes } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/shared/lib/cn";

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  options: SelectOption[];
  placeholder?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, error, options, placeholder, id, className, ...props }, ref) => {
    const fieldId = id ?? props.name;
    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label htmlFor={fieldId} className="text-[13px] font-medium text-graphite">
            {label}
          </label>
        )}
        <div className="relative">
          <select
            ref={ref}
            id={fieldId}
            className={cn(
              "h-10 w-full appearance-none rounded-[8.8px] border bg-white pl-3 pr-9 text-sm text-ink",
              "transition-colors focus:outline-none focus:border-cobalt focus:ring-2 focus:ring-cobalt/15",
              error ? "border-error" : "border-line",
              className,
            )}
            {...props}
          >
            {placeholder && <option value="">{placeholder}</option>}
            {options.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-fog" />
        </div>
        {error && <span className="text-xs text-error">{error}</span>}
      </div>
    );
  },
);
Select.displayName = "Select";
