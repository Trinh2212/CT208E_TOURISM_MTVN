import { useEffect, useRef, useState } from "react";
import { Popup, useMap } from "react-leaflet";
import { Link } from "react-router-dom";
import { ArrowRight, MapPin, MapPinned } from "lucide-react";
import PlaceImage from "../places/PlaceImage";
import { getPlaceDetail } from "../../services/placesService";

const descriptionLimit = 140;

function firstDescription(parts) {
  const first = [...parts].sort((a, b) => a.order - b.order)[0];
  const text = first?.text?.replace(/\s+/g, " ").trim() ?? "";
  return text.length > descriptionLimit
    ? `${text.slice(0, descriptionLimit - 3).trimEnd()}...`
    : text;
}

export default function PlaceMapPopup({ place, selected }) {
  const map = useMap();
  const popup = useRef(null);
  const [availableHeight, setAvailableHeight] = useState(
    () => Math.max(100, map.getSize().y - 74),
  );
  const [isOpen, setIsOpen] = useState(false);
  const [detail, setDetail] = useState(null);
  const [failed, setFailed] = useState(false);
  const [retry, setRetry] = useState(0);
  const hasDescription = place.descriptionParts.length > 0;

  useEffect(() => {
    // Trừ hao khoảng trống cho lề nội dung, mũi nhọn popup và vùng đệm auto-pan của bản đồ.
    const resize = () => setAvailableHeight(Math.max(100, map.getSize().y - 74));
    resize();
    map.on("resize", resize);
    return () => map.off("resize", resize);
  }, [map]);

  useEffect(() => {
    if ((!isOpen && !selected) || hasDescription || detail) return;
    const controller = new AbortController();
    setFailed(false);
    getPlaceDetail(place.place_id, { signal: controller.signal })
      .then((result) => {
        if (controller.signal.aborted) return;
        if (result) setDetail(result);
        else setFailed(true);
      })
      .catch((error) => {
        if (error.name !== "AbortError" && !controller.signal.aborted)
          setFailed(true);
      });
    return () => controller.abort();
  }, [isOpen, selected, hasDescription, detail, place.place_id, retry]);

  useEffect(() => {
    if (isOpen || selected) popup.current?.update();
  }, [isOpen, selected, detail, failed, availableHeight]);

  const description = firstDescription(
    hasDescription ? place.descriptionParts : detail?.descriptionParts ?? [],
  );

  return (
    <Popup
      ref={popup}
      className="place-details-popup"
      minWidth={240}
      maxWidth={300}
      autoPanPadding={[16, 16]}
      eventHandlers={{
        add: () => setIsOpen(true),
        remove: () => setIsOpen(false),
      }}
    >
      <article className="place-popup" style={{ maxHeight: availableHeight }}>
        <h3>{place.name}</h3>
        <div className="popup-body">
          <PlaceImage image={place.coverImage} />
          <div className="popup-addresses">
            <div className="popup-address">
              <MapPin size={22} aria-hidden="true" />
              <div>
                <strong>Địa chỉ (trước sáp nhập):</strong>
                <span>{place.address.former}</span>
              </div>
            </div>
            <div className="popup-address">
              <MapPinned size={22} aria-hidden="true" />
              <div>
                <strong>Địa chỉ (sau sáp nhập):</strong>
                <span>{place.address.current}</span>
              </div>
            </div>
          </div>
          <div className="popup-description" aria-live="polite">
            {description || (failed ? (
              <>
                Chưa tải được mô tả.{" "}
                <button type="button" onClick={() => setRetry((value) => value + 1)}>
                  Thử lại
                </button>
              </>
            ) : hasDescription || detail ? "Chưa có mô tả." : "Đang tải mô tả...")}
          </div>
        </div>
        <Link className="popup-detail-link" to={`/places/${encodeURIComponent(place.place_id)}`}>
          Xem chi tiết <ArrowRight size={16} aria-hidden="true" />
        </Link>
      </article>
    </Popup>
  );
}
