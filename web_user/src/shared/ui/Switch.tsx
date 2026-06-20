import { cn } from "@/shared/lib/cn";

export interface SwitchProps {
  checked: boolean;
  onChange: (next: boolean) => void;
  disabled?: boolean;
  label?: string;
  id?: string;
}

/** Toggle with a smooth 200ms slide (e.g. AVAILABLE ↔ RENTED). */
export function Switch({ checked, onChange, disabled, label, id }: SwitchProps) {
  return (
    <label
      htmlFor={id}
      className={cn(
        "inline-flex items-center gap-2.5 text-sm text-ink",
        disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer",
      )}
    >
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative h-6 w-11 rounded-full transition-colors duration-200",
          checked ? "bg-success" : "bg-ash",
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 left-0.5 size-5 rounded-full bg-white transition-transform duration-200",
            checked && "translate-x-5",
          )}
        />
      </button>
      {label && <span>{label}</span>}
    </label>
  );
}
