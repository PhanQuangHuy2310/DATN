import L from "leaflet";
import { formatCurrency } from "@/shared/lib";

/** Cobalt price pill marker for a listing. */
export function priceIcon(price: number, active = false): L.DivIcon {
  return L.divIcon({
    className: "",
    html: `<div class="ntr-pin ${active ? "ntr-pin--active" : ""}">${formatCurrency(price)}</div>`,
    iconSize: [0, 0],
    iconAnchor: [0, 0],
  });
}

/** Amber star marker for the computed midpoint. */
export function midpointIcon(): L.DivIcon {
  return L.divIcon({
    className: "",
    html: `<div class="ntr-pin--star"><svg width="16" height="16" viewBox="0 0 24 24" fill="#fff"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg></div>`,
    iconSize: [0, 0],
    iconAnchor: [0, 0],
  });
}

/** Red origin dot for a midpoint input location. */
export function originIcon(): L.DivIcon {
  return L.divIcon({
    className: "",
    html: `<div class="ntr-dot"></div>`,
    iconSize: [0, 0],
    iconAnchor: [0, 0],
  });
}
