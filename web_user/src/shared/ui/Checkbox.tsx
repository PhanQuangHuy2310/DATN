import { type InputHTMLAttributes } from "react";
import { Check } from "lucide-react";
import { cn } from "@/shared/lib/cn";

export interface CheckboxProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label?: string;
}

export function Checkbox({ label, className, id, ...props }: CheckboxProps) {
  const fieldId = id ?? props.name;
  return (
    <label
      htmlFor={fieldId}
      className={cn(
        "group inline-flex cursor-pointer items-center gap-2 text-sm text-ink select-none",
        props.disabled && "cursor-not-allowed opacity-50",
        className,
      )}
    >
      <span className="relative inline-flex">
        <input
          id={fieldId}
          type="checkbox"
          className="peer size-[18px] appearance-none rounded-[5px] border border-line bg-white transition-colors checked:border-cobalt checked:bg-cobalt focus:outline-none focus:ring-2 focus:ring-cobalt/20"
          {...props}
        />
        <Check className="pointer-events-none absolute left-0 top-0 size-[18px] scale-75 p-px text-white opacity-0 transition peer-checked:opacity-100" />
      </span>
      {label && <span>{label}</span>}
    </label>
  );
}
