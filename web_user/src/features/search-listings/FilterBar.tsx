import { useRef, useState } from "react";
import { Search, SlidersHorizontal, RotateCcw } from "lucide-react";
import { Button, Input, Select, RangeSlider, Checkbox } from "@/shared/ui";
import {
  AMENITIES,
  ALLEY_TYPES,
  ALLEY_WIDTHS,
  ALLEY_DEPTHS,
  PRICE_RANGE,
  AREA_RANGE,
  formatCurrency,
} from "@/shared/lib";
import type { ListingFilters } from "./types";
import type { AlleyType, AlleyWidth, AlleyDepth } from "@/entities/listing";

interface FilterBarProps {
  value: ListingFilters;
  onApply: (filters: ListingFilters) => void;
}

export function FilterBar({ value, onApply }: FilterBarProps) {
  const [draft, setDraft] = useState<ListingFilters>(value);
  const [expanded, setExpanded] = useState(false);

  // Resync the editable draft when the applied filters change from outside
  // (tab switch, reset, back-navigation). `value` is memoized on the URL
  // params in the parent, so this only fires on real changes — local edits
  // while typing are preserved. This render-phase reset replaces a
  // prop-mirroring effect (React's "adjusting state when a prop changes").
  // The previous-value tracker is a ref since it is never rendered.
  const appliedRef = useRef(value);
  if (value !== appliedRef.current) {
    appliedRef.current = value;
    setDraft(value);
  }

  const set = <K extends keyof ListingFilters>(key: K, v: ListingFilters[K]) =>
    setDraft((d) => ({ ...d, [key]: v }));

  const toggleAmenity = (id: string) =>
    setDraft((d) => {
      const cur = d.amenityIds ?? [];
      return {
        ...d,
        amenityIds: cur.includes(id) ? cur.filter((a) => a !== id) : [...cur, id],
      };
    });

  const apply = () => onApply({ ...draft, page: 0 });
  const reset = () => {
    const cleared: ListingFilters = { type: draft.type, page: 0 };
    setDraft(cleared);
    onApply(cleared);
  };

  return (
    <div className="rounded-[8.8px] border border-line bg-white p-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <Input
          name="q"
          wrapperClassName="flex-1"
          placeholder="Tìm theo khu vực, đường, tên tin…"
          leftIcon={<Search className="size-4" />}
          value={draft.q ?? ""}
          onChange={(e) => set("q", e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && apply()}
        />
        <Button
          variant={expanded ? "primary" : "ghost"}
          onClick={() => setExpanded((v) => !v)}
        >
          <SlidersHorizontal className="size-4" /> Bộ lọc nâng cao
        </Button>
        <Button onClick={apply}>
          <Search className="size-4" /> Tìm
        </Button>
      </div>

      {expanded && (
        <div className="mt-4 grid gap-5 border-t border-line pt-4 lg:grid-cols-2">
          <RangeSlider
            label="Khoảng giá thuê (VND/tháng)"
            min={PRICE_RANGE.min}
            max={PRICE_RANGE.max}
            step={PRICE_RANGE.step}
            value={[draft.priceMin ?? PRICE_RANGE.min, draft.priceMax ?? PRICE_RANGE.max]}
            onChange={([lo, hi]) => setDraft((d) => ({ ...d, priceMin: lo, priceMax: hi }))}
            format={(v) => formatCurrency(v)}
          />
          <RangeSlider
            label="Diện tích (m²)"
            min={AREA_RANGE.min}
            max={AREA_RANGE.max}
            step={AREA_RANGE.step}
            value={[draft.areaMin ?? AREA_RANGE.min, draft.areaMax ?? AREA_RANGE.max]}
            onChange={([lo, hi]) => setDraft((d) => ({ ...d, areaMin: lo, areaMax: hi }))}
            format={(v) => `${v} m²`}
          />

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:col-span-2">
            <Select
              label="Loại ngõ"
              name="alleyType"
              placeholder="Tất cả"
              value={draft.alleyType ?? ""}
              onChange={(e) => set("alleyType", (e.target.value || undefined) as AlleyType)}
              options={ALLEY_TYPES.map((o) => ({ value: o.value, label: o.label }))}
            />
            <Select
              label="Độ rộng ngõ"
              name="alleyWidth"
              placeholder="Tất cả"
              value={draft.alleyWidth ?? ""}
              onChange={(e) => set("alleyWidth", (e.target.value || undefined) as AlleyWidth)}
              options={ALLEY_WIDTHS.map((o) => ({ value: o.value, label: o.label }))}
            />
            <Select
              label="Độ sâu ngõ"
              name="alleyDepth"
              placeholder="Tất cả"
              value={draft.alleyDepth ?? ""}
              onChange={(e) => set("alleyDepth", (e.target.value || undefined) as AlleyDepth)}
              options={ALLEY_DEPTHS.map((o) => ({ value: o.value, label: o.label }))}
            />
            <Input
              label="Số xe máy gửi tối đa"
              name="maxMotorbikes"
              type="number"
              min={0}
              placeholder="vd: 2"
              value={draft.maxMotorbikes ?? ""}
              onChange={(e) =>
                set("maxMotorbikes", e.target.value ? Number(e.target.value) : undefined)
              }
            />
          </div>

          <div className="lg:col-span-2">
            <p className="mb-2 text-[13px] font-medium text-graphite">Tiện ích</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
              {AMENITIES.map((a) => (
                <Checkbox
                  key={a.id}
                  name={`amenity-${a.id}`}
                  label={a.label}
                  checked={draft.amenityIds?.includes(a.id) ?? false}
                  onChange={() => toggleAmenity(a.id)}
                />
              ))}
            </div>
          </div>

          <div className="flex items-center justify-end gap-2 lg:col-span-2">
            <Button variant="ghost" onClick={reset}>
              <RotateCcw className="size-4" /> Đặt lại
            </Button>
            <Button onClick={apply}>Áp dụng bộ lọc</Button>
          </div>
        </div>
      )}
    </div>
  );
}
