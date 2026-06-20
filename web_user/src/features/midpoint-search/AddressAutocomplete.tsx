import { useEffect, useState } from "react";
import { MapPin, Loader2 } from "lucide-react";
import { Input } from "@/shared/ui";
import { geocode, type GeocodeResult, useDebouncedValue } from "@/shared/lib";
import type { LatLng } from "@/shared/types";

interface Props {
  index: number;
  onPick: (point: LatLng & { label: string }) => void;
}

/** Address input with debounced (300ms) Nominatim suggestions. */
export function AddressAutocomplete({ index, onPick }: Props) {
  const [text, setText] = useState("");
  const [results, setResults] = useState<GeocodeResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const debounced = useDebouncedValue(text, 350);

  useEffect(() => {
    let active = true;
    if (debounced.trim().length < 3) {
      setResults([]);
      return;
    }
    setLoading(true);
    geocode(debounced)
      .then((r) => active && setResults(r))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [debounced]);

  return (
    <div className="relative">
      <Input
        name={`midpoint-${index}`}
        placeholder={`Địa điểm ${index + 1} (vd: ĐH Bách Khoa)`}
        leftIcon={<MapPin className="size-4" />}
        rightIcon={loading ? <Loader2 className="size-4 animate-spin" /> : undefined}
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
      />
      {open && results.length > 0 && (
        <div className="panel-float absolute z-20 mt-1 max-h-56 w-full overflow-y-auto rounded-[8.8px] p-1">
          {results.map((r) => (
            <button
              key={`${r.lat},${r.lng}-${r.displayName}`}
              type="button"
              onClick={() => {
                setText(r.displayName);
                setOpen(false);
                onPick({ lat: r.lat, lng: r.lng, label: r.displayName });
              }}
              className="block w-full truncate rounded-[6px] px-2.5 py-2 text-left text-sm text-graphite transition-colors hover:bg-paper"
            >
              {r.displayName}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
