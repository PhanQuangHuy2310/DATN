import type { ListingFilters } from "./types";
import type { ListingType, AlleyType, AlleyWidth, AlleyDepth } from "@/entities/listing";

/** Serialise filters into URLSearchParams (for the API and the browser URL). */
export function filtersToParams(f: ListingFilters): URLSearchParams {
  const p = new URLSearchParams();
  if (f.q) p.set("q", f.q);
  if (f.type) p.set("type", f.type);
  if (f.priceMin != null) p.set("priceMin", String(f.priceMin));
  if (f.priceMax != null) p.set("priceMax", String(f.priceMax));
  if (f.areaMin != null) p.set("areaMin", String(f.areaMin));
  if (f.areaMax != null) p.set("areaMax", String(f.areaMax));
  if (f.alleyType) p.set("alleyType", f.alleyType);
  if (f.alleyWidth) p.set("alleyWidth", f.alleyWidth);
  if (f.alleyDepth) p.set("alleyDepth", f.alleyDepth);
  if (f.maxMotorbikes != null) p.set("maxMotorbikes", String(f.maxMotorbikes));
  if (f.district) p.set("district", f.district);
  if (f.amenityIds?.length) p.set("amenityIds", f.amenityIds.join(","));
  if (f.page) p.set("page", String(f.page));
  return p;
}

export function parseFilters(p: URLSearchParams): ListingFilters {
  const num = (k: string) => (p.has(k) ? Number(p.get(k)) : undefined);
  return {
    q: p.get("q") ?? undefined,
    type: (p.get("type") as ListingType) ?? "RENTAL",
    priceMin: num("priceMin"),
    priceMax: num("priceMax"),
    areaMin: num("areaMin"),
    areaMax: num("areaMax"),
    alleyType: (p.get("alleyType") as AlleyType) ?? undefined,
    alleyWidth: (p.get("alleyWidth") as AlleyWidth) ?? undefined,
    alleyDepth: (p.get("alleyDepth") as AlleyDepth) ?? undefined,
    maxMotorbikes: num("maxMotorbikes"),
    district: p.get("district") ?? undefined,
    amenityIds: p.get("amenityIds")?.split(",").filter(Boolean),
    page: num("page") ?? 0,
  };
}
