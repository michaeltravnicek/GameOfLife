import { useEffect, useMemo, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Circle, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';
import './EventLocationMap.css';

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

const BRNO = [49.1951, 16.6068];

function toNumber(value) {
  if (value === null || value === undefined || value === '') return null;
  const n = typeof value === 'number' ? value : parseFloat(value);
  return Number.isFinite(n) ? n : null;
}

function FlyTo({ position }) {
  const map = useMap();
  useEffect(() => {
    if (position) map.flyTo(position, Math.max(map.getZoom(), 13), { duration: 0.6 });
  }, [position, map]);
  return null;
}

function ClickHandler({ onChange }) {
  useMapEvents({
    click(e) {
      onChange({ latitude: e.latlng.lat, longitude: e.latlng.lng });
    },
  });
  return null;
}

export default function EventLocationMap({
  latitude,
  longitude,
  radius,
  interactive = false,
  onChange,
  popupLabel,
  defaultCenter = BRNO,
}) {
  const lat = toNumber(latitude);
  const lng = toNumber(longitude);
  const hasMarker = lat !== null && lng !== null;
  const position = useMemo(() => (hasMarker ? [lat, lng] : null), [hasMarker, lat, lng]);
  const center = position || defaultCenter;
  const initialZoom = hasMarker ? 14 : 12;
  const markerRef = useRef(null);

  const handleDragEnd = () => {
    const m = markerRef.current;
    if (!m || !onChange) return;
    const { lat: newLat, lng: newLng } = m.getLatLng();
    onChange({ latitude: newLat, longitude: newLng });
  };

  return (
    <div className={`event-location-map${interactive ? ' is-interactive' : ''}`}>
      <MapContainer
        center={center}
        zoom={initialZoom}
        scrollWheelZoom={interactive}
        className="elm-canvas"
        attributionControl
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          maxZoom={19}
        />
        {position && (
          <Marker
            position={position}
            draggable={interactive}
            eventHandlers={interactive ? { dragend: handleDragEnd } : undefined}
            ref={markerRef}
          >
            {popupLabel && <Popup>{popupLabel}</Popup>}
          </Marker>
        )}
        {interactive && position && radius > 0 && (
          <Circle center={position} radius={radius} pathOptions={{ color: '#e15463', weight: 1.5, fillOpacity: 0.08 }} />
        )}
        {interactive && onChange && <ClickHandler onChange={onChange} />}
        {position && <FlyTo position={position} />}
      </MapContainer>
      {interactive && !hasMarker && (
        <div className="u-mono elm-hint">Klikni na mapu pro výběr místa.</div>
      )}
    </div>
  );
}
