import { useEffect } from "react";
import { MapContainer, TileLayer, Marker, useMap, useMapEvents } from "react-leaflet";
import L from "leaflet";
import { DEFAULT_MAP_CENTER, DEFAULT_MAP_ZOOM } from "@/shared/config";
import type { LatLng } from "@/shared/types";

const pinIcon = L.divIcon({
  className: "",
  html: `<div class="ntr-dot" style="background:var(--color-cobalt);width:18px;height:18px"></div>`,
  iconSize: [0, 0],
  iconAnchor: [0, 0],
});

interface Props {
  value: LatLng | null;
  onChange: (p: LatLng) => void;
}

/** Mini map: click or drag the marker to set the listing's exact coordinates. */
export function LocationPicker({ value, onChange }: Props) {
  return (
    <div className="h-64 overflow-hidden rounded-[8.8px] border border-line">
      <MapContainer
        center={value ? [value.lat, value.lng] : DEFAULT_MAP_CENTER}
        zoom={value ? 16 : DEFAULT_MAP_ZOOM}
        className="size-full"
      >
        <TileLayer
          attribution='&copy; OpenStreetMap'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <ClickHandler onChange={onChange} />
        {value && (
          <Marker
            position={[value.lat, value.lng]}
            icon={pinIcon}
            draggable
            eventHandlers={{
              dragend: (e) => {
                const m = e.target as L.Marker;
                const p = m.getLatLng();
                onChange({ lat: p.lat, lng: p.lng });
              },
            }}
          />
        )}
        {value && <Recenter target={value} />}
      </MapContainer>
    </div>
  );
}

function ClickHandler({ onChange }: { onChange: (p: LatLng) => void }) {
  useMapEvents({
    click: (e) => onChange({ lat: e.latlng.lat, lng: e.latlng.lng }),
  });
  return null;
}

function Recenter({ target }: { target: LatLng }) {
  const map = useMap();
  useEffect(() => {
    map.setView([target.lat, target.lng]);
  }, [map, target.lat, target.lng]);
  return null;
}
