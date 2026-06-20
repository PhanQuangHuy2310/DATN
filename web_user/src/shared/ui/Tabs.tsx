import { cn } from "@/shared/lib/cn";

export interface TabItem {
  value: string;
  label: string;
  count?: number;
}

export interface TabsProps {
  items: TabItem[];
  value: string;
  onChange: (value: string) => void;
  variant?: "pill" | "underline";
  className?: string;
}

export function Tabs({ items, value, onChange, variant = "pill", className }: TabsProps) {
  if (variant === "underline") {
    return (
      <div className={cn("flex gap-1 border-b border-line", className)}>
        {items.map((it) => (
          <button
            key={it.value}
            type="button"
            onClick={() => onChange(it.value)}
            className={cn(
              "relative -mb-px border-b-2 px-4 py-2.5 text-sm font-medium transition-colors",
              value === it.value
                ? "border-cobalt text-ink"
                : "border-transparent text-fog hover:text-ink",
            )}
          >
            {it.label}
            {it.count != null && <span className="ml-1.5 text-xs text-fog">({it.count})</span>}
          </button>
        ))}
      </div>
    );
  }
  return (
    <div className={cn("inline-flex gap-1 rounded-[8.8px] border border-line bg-white p-1", className)}>
      {items.map((it) => (
        <button
          key={it.value}
          type="button"
          onClick={() => onChange(it.value)}
          className={cn(
            "rounded-[6px] px-3.5 py-1.5 text-sm font-medium transition-colors",
            value === it.value ? "bg-cobalt text-white" : "text-fog hover:bg-paper hover:text-ink",
          )}
        >
          {it.label}
          {it.count != null && (
            <span className={cn("ml-1.5 text-xs", value === it.value ? "text-white/80" : "text-fog")}>
              {it.count}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}
