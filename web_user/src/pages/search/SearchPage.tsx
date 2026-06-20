import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { List, MapIcon, Sparkles, X } from "lucide-react";
import {
  Button,
  Tabs,
  EmptyState,
  type TabItem,
} from "@/shared/ui";
import { cn } from "@/shared/lib/cn";
import { RADIUS_OPTIONS } from "@/shared/lib";
import { ListingCard, ListingCardSkeleton, type Listing, type ListingPin } from "@/entities/listing";
import {
  FilterBar,
  parseFilters,
  filtersToParams,
  useSearchListings,
  useMapListings,
} from "@/features/search-listings";
import {
  MidpointPanel,
  type MidpointResult,
  type MidpointPoint,
} from "@/features/midpoint-search";
import { useToggleWishlist } from "@/features/wishlist";
import type { LatLng } from "@/shared/types";
import { SearchMap, type MidpointOverlay } from "./map/SearchMap";

const TABS: TabItem[] = [
  { value: "RENTAL", label: "Cho thuê" },
  { value: "ROOMMATE", label: "Ở ghép" },
];

export function SearchPage() {
  const [params, setParams] = useSearchParams();
  const filters = useMemo(() => parseFilters(params), [params]);

  const [center, setCenter] = useState<LatLng | null>(null);
  const [radiusKm, setRadiusKm] = useState<number>(2);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [mobileView, setMobileView] = useState<"list" | "map">("list");
  const [midpointOpen, setMidpointOpen] = useState(false);
  const [midpoint, setMidpoint] = useState<{
    overlay: MidpointOverlay;
    listings: Listing[];
  } | null>(null);

  const toggleFav = useToggleWishlist();

  const list = useSearchListings(filters);
  const mapQuery = center
    ? { lat: center.lat, lng: center.lng, radius: radiusKm * 1000, type: filters.type }
    : null;
  const mapData = useMapListings(midpoint ? null : mapQuery);

  const applyFilters = (next: typeof filters) =>
    setParams(filtersToParams(next), { replace: true });

  const setType = (type: string) =>
    applyFilters({ ...filters, type: type as Listing["type"], page: 0 });

  const onMidpointResult = (res: MidpointResult, points: MidpointPoint[]) => {
    setMidpoint({
      overlay: { midpoint: res.midpoint, origins: points },
      listings: res.listings,
    });
    setMidpointOpen(false);
  };

  // What the left list + map markers show.
  const listings: Listing[] = midpoint ? midpoint.listings : list.data?.content ?? [];
  const pins: ListingPin[] = midpoint
    ? midpoint.listings
    : (mapData.data ?? []);
  const count = midpoint ? midpoint.listings.length : list.data?.totalElements ?? listings.length;
  const loading = midpoint ? false : list.isLoading;

  return (
    <div className="flex h-full flex-col">
      {/* Filter bar */}
      <div className="border-b border-line bg-paper px-3 py-3 sm:px-4">
        <FilterBar value={filters} onApply={applyFilters} />
      </div>

      {/* Mobile view toggle */}
      <div className="flex items-center justify-center gap-1 border-b border-line bg-paper p-2 lg:hidden">
        <Button
          size="sm"
          variant={mobileView === "list" ? "primary" : "ghost"}
          onClick={() => setMobileView("list")}
        >
          <List className="size-4" /> Danh sách
        </Button>
        <Button
          size="sm"
          variant={mobileView === "map" ? "primary" : "ghost"}
          onClick={() => setMobileView("map")}
        >
          <MapIcon className="size-4" /> Bản đồ
        </Button>
      </div>

      <div className="grid min-h-0 flex-1 lg:grid-cols-[minmax(360px,42%)_1fr]">
        {/* LEFT: results list */}
        <section
          className={cn(
            "flex min-h-0 flex-col border-r border-line",
            mobileView === "map" && "hidden lg:flex",
          )}
        >
          <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
            <p className="text-sm text-fog">
              <span className="font-semibold text-ink">{count}</span> kết quả
            </p>
            <Tabs items={TABS} value={filters.type ?? "RENTAL"} onChange={setType} />
          </div>

          <div className="scroll-area min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
            {loading ? (
              Array.from({ length: 5 }).map((_, i) => <ListingCardSkeleton key={i} layout="list" />)
            ) : listings.length === 0 ? (
              <EmptyState
                title="Không tìm thấy phòng trọ nào khớp với yêu cầu của bạn"
                description="Thử nới lỏng bộ lọc hoặc mở rộng khoảng cách quét bản đồ xem sao nhé!"
                action={
                  <Button variant="ghost" onClick={() => applyFilters({ type: filters.type, page: 0 })}>
                    Đặt lại bộ lọc
                  </Button>
                }
              />
            ) : (
              listings.map((l) => (
                <ListingCard
                  key={l.id}
                  listing={l}
                  layout="list"
                  active={activeId === l.id}
                  onMouseEnter={() => setActiveId(l.id)}
                  onMouseLeave={() => setActiveId(null)}
                  onToggleFavorite={(id) => toggleFav.mutate(id)}
                />
              ))
            )}
          </div>
        </section>

        {/* RIGHT: map */}
        <section
          className={cn(
            "relative min-h-0",
            mobileView === "list" && "hidden lg:block",
          )}
        >
          <SearchMap
            pins={pins}
            radius={radiusKm * 1000}
            activeId={activeId}
            onActiveChange={setActiveId}
            onMove={setCenter}
            midpoint={midpoint?.overlay}
          />

          {/* Radius selector + scan */}
          {!midpoint && (
            <div className="panel-float absolute right-3 top-3 z-[500] flex items-center gap-1 rounded-full p-1">
              {RADIUS_OPTIONS.map((km) => (
                <button
                  key={km}
                  type="button"
                  onClick={() => setRadiusKm(km)}
                  className={cn(
                    "rounded-full px-3 py-1 text-xs font-medium transition-colors",
                    radiusKm === km ? "bg-cobalt text-white" : "text-graphite hover:bg-paper",
                  )}
                >
                  {km} km
                </button>
              ))}
            </div>
          )}

          {/* Midpoint toggle / panel */}
          {midpointOpen ? (
            <MidpointPanel onResult={onMidpointResult} onClose={() => setMidpointOpen(false)} />
          ) : (
            <button
              type="button"
              onClick={() => setMidpointOpen(true)}
              className="panel-float absolute left-3 top-3 z-[500] inline-flex items-center gap-1.5 rounded-full px-3.5 py-2 text-sm font-medium text-cobalt"
            >
              <Sparkles className="size-4" /> Tìm phòng điểm giữa
            </button>
          )}

          {/* Clear midpoint */}
          {midpoint && !midpointOpen && (
            <button
              type="button"
              onClick={() => setMidpoint(null)}
              className="panel-float absolute left-3 top-3 z-[500] inline-flex items-center gap-1.5 rounded-full px-3.5 py-2 text-sm font-medium text-ink"
            >
              <X className="size-4" /> Thoát điểm giữa
            </button>
          )}
        </section>
      </div>
    </div>
  );
}
