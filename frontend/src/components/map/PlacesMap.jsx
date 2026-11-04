import { useEffect, useMemo, useRef, useState } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  ScaleControl,
  ZoomControl,
  useMap,
  useMapEvents,
} from "react-leaflet";
import L from "leaflet";
import { LocateFixed } from "lucide-react";
import PlaceMapPopup from "./PlaceMapPopup";
const initialCenter = [10.22, 105.46];
function MapEvents({ viewport }) {
  const map = useMapEvents({
    moveend: () => {
      const container = map.getContainer();
      if (
        viewport &&
        container.isConnected &&
        container.clientWidth &&
        container.clientHeight
      )
        viewport.current = {
          center: [map.getCenter().lat, map.getCenter().lng],
          zoom: map.getZoom(),
        };
    },
  });
  useEffect(() => {
    const observer = new ResizeObserver(() => {
      const container = map.getContainer();
      // Bỏ qua khung chứa bị biến mất khi rời trang; giữ nguyên tâm bản đồ
      // khi kích thước pixel thực tế của khung bản đồ thay đổi.
      if (
        container.isConnected &&
        container.clientWidth &&
        container.clientHeight
      )
        map.invalidateSize({ pan: true, animate: false });
    });
    observer.observe(map.getContainer());
    return () => observer.disconnect();
  }, [map]);
  return null;
}
function MapController({ selectedId, places, markerRefs, selectionVersion }) {
  const map = useMap();
  const lastSelection = useRef(null);
  useEffect(() => {
    if (
      !selectionVersion ||
      !selectedId ||
      lastSelection.current === selectionVersion
    )
      return;
    lastSelection.current = selectionVersion;
    const place = places.find((item) => item.place_id === selectedId);
    if (place) {
      // Chỉ mở popup sau khi hiệu ứng bay (flyTo) kết thúc để tính năng auto-pan giữ trọn thẻ trong tầm nhìn.
      const openPopup = () => markerRefs.current[selectedId]?.openPopup();
      map.closePopup();
      map.once("moveend", openPopup);
      map.flyTo(place.coordinates, Math.max(map.getZoom(), 12), {
        duration: 0.6,
      });
      return () => map.off("moveend", openPopup);
    }
  }, [selectedId, selectionVersion, places, map, markerRefs]);
  return (
    <button
      type="button"
      className="map-fit icon-button"
      aria-label="Hiển thị tất cả địa điểm trên bản đồ"
      title="Hiển thị tất cả địa điểm"
      onClick={() => {
        if (places.length === 1) map.setView(places[0].coordinates, 13);
        else if (places.length)
          map.fitBounds(
            places.map((place) => place.coordinates),
            { padding: [55, 55], maxZoom: 13 },
          );
      }}
    >
      <LocateFixed />
    </button>
  );
}
export default function PlacesMap({
  places,
  selectedId,
  onSelect,
  viewport,
  selectionVersion = 0,
  detail = false,
}) {
  const markers = useRef({});
  const [tileError, setTileError] = useState(false);
  const icons = useMemo(
    () =>
      places.map((place, index) =>
        L.divIcon({
          className: "number-marker-wrapper",
          html: `<span class="number-marker ${place.place_id === selectedId ? "active" : ""}">${detail ? '<span class="marker-center" aria-hidden="true"></span>' : `<span>${index + 1}</span>`}</span>`,
          iconSize: [38, 48],
          iconAnchor: [19, 48],
          popupAnchor: [0, -44],
        }),
      ),
    [places, selectedId, detail],
  );
  const start = viewport?.current;
  return (
    <div className={`map-shell ${detail ? "detail-map" : ""}`}>
      <MapContainer
        center={
          start?.center ??
          (detail && places[0] ? places[0].coordinates : initialCenter)
        }
        zoom={start?.zoom ?? (detail ? 12 : 9)}
        zoomControl={false}
        scrollWheelZoom
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          eventHandlers={{
            tileerror: () => setTileError(true),
            loading: () => setTileError(false),
          }}
        />
        <ZoomControl position="topright" />
        <ScaleControl position="bottomleft" imperial={false} />
        <MapEvents viewport={viewport} />
        <MapController
          places={places}
          selectedId={selectedId}
          markerRefs={markers}
          selectionVersion={selectionVersion}
        />
        {places.map((place, index) => (
          <Marker
            key={place.place_id}
            position={place.coordinates}
            icon={icons[index]}
            title={detail ? place.name : undefined}
            ref={(marker) => {
              if (marker) markers.current[place.place_id] = marker;
              else delete markers.current[place.place_id];
            }}
            eventHandlers={{
              click: () => onSelect?.(place.place_id, "marker"),
            }}
          >
            {detail ? (
              <Popup className="coordinates-popup" minWidth={180} maxWidth={220} autoPanPadding={[16, 16]}>
                <div className="place-coordinates">
                  <strong>Tọa độ địa điểm</strong>
                  <span>Vĩ độ: {place.coordinates[0].toFixed(6)}°</span>
                  <span>Kinh độ: {place.coordinates[1].toFixed(6)}°</span>
                </div>
              </Popup>
            ) : (
              <PlaceMapPopup place={place} selected={place.place_id === selectedId} />
            )}
          </Marker>
        ))}
      </MapContainer>
      {tileError && (
        <span className="tile-error" role="status">
          Không tải được một số ô bản đồ. Kiểm tra kết nối mạng.
        </span>
      )}
    </div>
  );
}
