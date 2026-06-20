import type { LatLng } from "@/shared/types";

const EARTH_RADIUS_M = 6_371_000;

/** Haversine great-circle distance in metres. */
export function haversine(a: LatLng, b: LatLng): number {
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.sqrt(h));
}

/** Simple arithmetic midpoint — backend recomputes the authoritative one. */
export function midpointOf(points: LatLng[]): LatLng {
  const n = points.length || 1;
  const sum = points.reduce(
    (acc, p) => ({ lat: acc.lat + p.lat, lng: acc.lng + p.lng }),
    { lat: 0, lng: 0 },
  );
  return { lat: sum.lat / n, lng: sum.lng / n };
}

function toRad(deg: number): number {
  return (deg * Math.PI) / 180;
}

export interface GeocodeResult {
  displayName: string;
  lat: number;
  lng: number;
}

/** Forward geocode via OpenStreetMap Nominatim (public, rate-limited). */
export async function geocode(query: string): Promise<GeocodeResult[]> {
  if (!query.trim()) return [];
  const url = new URL("https://nominatim.openstreetmap.org/search");
  url.searchParams.set("q", query);
  url.searchParams.set("format", "json");
  url.searchParams.set("limit", "5");
  url.searchParams.set("countrycodes", "vn");
  url.searchParams.set("accept-language", "vi");
  const res = await fetch(url.toString(), {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) return [];
  const data = (await res.json()) as Array<{
    display_name: string;
    lat: string;
    lon: string;
  }>;
  return data.map((d) => ({
    displayName: d.display_name,
    lat: Number(d.lat),
    lng: Number(d.lon),
  }));
}
