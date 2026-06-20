import { Bus, ShoppingCart, GraduationCap, Store, MapPin, Hospital } from "lucide-react";
import { Spinner } from "@/shared/ui";
import { formatDistance } from "@/shared/lib";
import type { Poi } from "./hooks";

const CATEGORY_ICON: Record<string, React.ReactNode> = {
  bus: <Bus className="size-4" />,
  bus_station: <Bus className="size-4" />,
  supermarket: <ShoppingCart className="size-4" />,
  school: <GraduationCap className="size-4" />,
  university: <GraduationCap className="size-4" />,
  market: <Store className="size-4" />,
  hospital: <Hospital className="size-4" />,
};

const CATEGORY_LABEL: Record<string, string> = {
  bus: "Trạm xe buýt",
  bus_station: "Trạm xe buýt",
  supermarket: "Siêu thị",
  school: "Trường học",
  university: "Trường đại học",
  market: "Chợ",
  hospital: "Bệnh viện",
};

export function PoiRadar({ pois, loading }: { pois: Poi[]; loading: boolean }) {
  if (loading) {
    return (
      <div className="flex justify-center py-6">
        <Spinner />
      </div>
    );
  }
  if (pois.length === 0) {
    return <p className="text-sm text-fog">Chưa quét được tiện ích công cộng quanh khu vực này.</p>;
  }

  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {pois.map((p) => (
        <div key={p.id} className="flex items-center gap-3 rounded-[8.8px] border border-line bg-white px-3 py-2.5">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-[8.8px] bg-cobalt-soft text-cobalt">
            {CATEGORY_ICON[p.category] ?? <MapPin className="size-4" />}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-ink">{p.name}</p>
            <p className="text-xs text-fog">{CATEGORY_LABEL[p.category] ?? p.category}</p>
          </div>
          <span className="shrink-0 text-sm font-medium text-cobalt">{formatDistance(p.distance)}</span>
        </div>
      ))}
    </div>
  );
}
