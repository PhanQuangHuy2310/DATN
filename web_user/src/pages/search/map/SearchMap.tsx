import { useEffect } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  Circle,
  Polyline,
  useMap,
  useMapEvents,
} from "react-leaflet";
import { Link } from "react-router-dom";
import { formatCurrency, formatArea, useDebouncedCallback } from "@/shared/lib";
import { DEFAULT_MAP_CENTER, DEFAULT_MAP_ZOOM } from "@/shared/config";
import type { LatLng } from "@/shared/types";
import type { ListingPin } from "@/entities/listing";
import { priceIcon, midpointIcon, originIcon } from "./icons";

export interface MidpointOverlay {
  midpoint: LatLng;
  origins: (LatLng & { label: string })[];
}

interface Props {
  pins: ListingPin[];
  radius: number;
  activeId?: number | null;
  onActiveChange?: (id: number | null) => void;
  onMove?: (center: LatLng) => void;
  midpoint?: MidpointOverlay | null;
}

export function SearchMap({ pins, radius, activeId, onActiveChange, onMove, midpoint }: Props) {
  return (
    <MapContainer
      center={DEFAULT_MAP_CENTER}
      zoom={DEFAULT_MAP_ZOOM}
      className="size-full"
      zoomControl={false}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {onMove && <MoveWatcher onMove={onMove} />}

      {/* Radius scan circle around the current centre */}
      {!midpoint && <CenterCircle radius={radius} />}

      {pins.map((p) => (
        <Marker
          key={p.id}
          position={[p.lat, p.lng]}
          icon={priceIcon(p.price, activeId === p.id)}
          eventHandlers={{
            click: () => onActiveChange?.(p.id),
          }}
        >
          <Popup>
            <PinPopup pin={p} />
          </Popup>
        </Marker>
      ))}

      {/* Midpoint visualisation */}
      {midpoint && (
        <>
          <FlyTo target={midpoint.midpoint} />
          <Marker position={[midpoint.midpoint.lat, midpoint.midpoint.lng]} icon={midpointIcon()} />
          {midpoint.origins.map((o) => (
            <Marker key={`${o.lat},${o.lng}`} position={[o.lat, o.lng]} icon={originIcon()}>
              <Popup>{o.label}</Popup>
            </Marker>
          ))}
          {midpoint.origins.map((o) => (
            <Polyline
              key={`line-${o.lat},${o.lng}`}
              positions={[
                [midpoint.midpoint.lat, midpoint.midpoint.lng],
                [o.lat, o.lng],
              ]}
              pathOptions={{ color: "#b4690e", weight: 2, dashArray: "6 8" }}
            />
          ))}
        </>
      )}
    </MapContainer>
  );
}

function MoveWatcher({ onMove }: { onMove: (c: LatLng) => void }) {
  const debounced = useDebouncedCallback(onMove, 500);
  const map = useMapEvents({
    moveend: () => {
      const c = map.getCenter();
      debounced({ lat: c.lat, lng: c.lng });
    },
  });
  // Fire once on mount so the first query has a centre.
  useEffect(() => {
    const c = map.getCenter();
    onMove({ lat: c.lat, lng: c.lng });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return null;
}

function CenterCircle({ radius }: { radius: number }) {
  const map = useMap();
  const c = map.getCenter();
  return (
    <Circle
      center={[c.lat, c.lng]}
      radius={radius}
      pathOptions={{ color: "#165dfb", weight: 1, fillColor: "#165dfb", fillOpacity: 0.06 }}
    />
  );
}

function FlyTo({ target }: { target: LatLng }) {
  const map = useMap();
  useEffect(() => {
    map.flyTo([target.lat, target.lng], 14, { duration: 0.8 });
  }, [map, target.lat, target.lng]);
  return null;
}

function PinPopup({ pin }: { pin: ListingPin }) {
  return (
    <div className="w-44">
      {pin.mediaUrls?.[0] && (
        <img src={pin.mediaUrls[0]} alt={pin.title} className="mb-1.5 h-24 w-full rounded object-cover" />
      )}
      <Link to={`/listings/${pin.id}`} className="block text-sm font-medium leading-snug text-ink hover:text-cobalt">
        {pin.title}
      </Link>
      <p className="mt-0.5 text-sm font-semibold text-cobalt">{formatCurrency(pin.price)}/tháng</p>
      {pin.area != null && <p className="text-xs text-fog">{formatArea(pin.area)}</p>}
    </div>
  );
}
