import { useCallback } from "react";
import { cn } from "@/shared/lib/cn";

export interface RangeSliderProps {
  min: number;
  max: number;
  step?: number;
  value: [number, number];
  onChange: (value: [number, number]) => void;
  format?: (v: number) => string;
  label?: string;
  className?: string;
}

/** Dual-thumb range slider (two overlapping native inputs + a cobalt fill). */
export function RangeSlider({
  min,
  max,
  step = 1,
  value,
  onChange,
  format = (v) => String(v),
  label,
  className,
}: RangeSliderProps) {
  const [lo, hi] = value;
  const pct = useCallback((v: number) => ((v - min) / (max - min)) * 100, [min, max]);

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      {label && <span className="text-[13px] font-medium text-graphite">{label}</span>}
      <div className="relative h-5">
        <div className="absolute top-1/2 h-1 w-full -translate-y-1/2 rounded-full bg-chalk" />
        <div
          className="absolute top-1/2 h-1 -translate-y-1/2 rounded-full bg-cobalt"
          style={{ left: `${pct(lo)}%`, right: `${100 - pct(hi)}%` }}
        />
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={lo}
          onChange={(e) => onChange([Math.min(Number(e.target.value), hi - step), hi])}
          className="range-thumb pointer-events-none absolute top-0 h-5 w-full appearance-none bg-transparent"
          aria-label={`${label ?? "Khoảng"} - cận dưới`}
        />
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={hi}
          onChange={(e) => onChange([lo, Math.max(Number(e.target.value), lo + step)])}
          className="range-thumb pointer-events-none absolute top-0 h-5 w-full appearance-none bg-transparent"
          aria-label={`${label ?? "Khoảng"} - cận trên`}
        />
      </div>
      <div className="flex justify-between text-xs text-fog">
        <span>{format(lo)}</span>
        <span>{format(hi)}</span>
      </div>
    </div>
  );
}
