import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft,
  MapPin,
  FileText,
  Images,
  LoaderCircle,
  SearchX,
  Info,
  Tags,
  BookOpen,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { getPlaceDetail } from "../services/placesService";
import { useSearch } from "../context/SearchContext";
import Gallery, { Lightbox } from "../components/places/Gallery";
import PlaceImage from "../components/places/PlaceImage";
import PlacesMap from "../components/map/PlacesMap";
const tabs = [
  { id: "overview", name: "Tổng quan", Icon: FileText },
  { id: "images", name: "Hình ảnh", Icon: Images },
];
export default function PlaceDetailPage() {
  const { placeId } = useParams();
  const search = useSearch();
  const [place, setPlace] = useState(null);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState("");
  const [tab, setTab] = useState("overview");
  const [lightboxIndex, setLightboxIndex] = useState(null);
  const [retry, setRetry] = useState(0);
  const [coordinateVersion, setCoordinateVersion] = useState(0);
  const [overviewExpanded, setOverviewExpanded] = useState(false);
  const [overviewHeight, setOverviewHeight] = useState(0);
  const [canExpandOverview, setCanExpandOverview] = useState(false);
  const overviewRef = useRef(null);
  const descriptionHeadingRef = useRef(null);
  const descriptionTextRef = useRef(null);
  const locationRef = useRef(null);
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    window.scrollTo(0, 0);
    setStatus("loading");
    setPlace(null);
    setError("");
    setTab("overview");
    setLightboxIndex(null);
    setCoordinateVersion(0);
    setOverviewExpanded(false);
    getPlaceDetail(placeId, { signal: controller.signal })
      .then((data) => {
        if (active) {
          setPlace(data);
          setStatus(data ? "ready" : "missing");
        }
      })
      .catch((err) => {
        if (active && err.name !== "AbortError") {
          setError(err.message);
          setStatus("error");
        }
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [placeId, retry]);
  useLayoutEffect(() => {
    if (status !== "ready" || tab !== "overview") return;
    const panel = overviewRef.current;
    const location = locationRef.current;
    const heading = descriptionHeadingRef.current;
    const text = descriptionTextRef.current;
    if (!panel || !location || !heading || !text) return;

    const measure = () => {
      const height = location.getBoundingClientRect().height;
      const style = getComputedStyle(panel);
      const headingStyle = getComputedStyle(heading);
      const padding = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom)
        + parseFloat(style.borderTopWidth) + parseFloat(style.borderBottomWidth);
      const headingHeight = heading.getBoundingClientRect().height
        + parseFloat(headingStyle.marginBottom);
      setOverviewHeight(height);
      setCanExpandOverview(text.getBoundingClientRect().height > height - padding - headingHeight + 1);
    };
    const observer = new ResizeObserver(measure);
    observer.observe(location);
    observer.observe(heading);
    observer.observe(text);
    measure();
    return () => observer.disconnect();
  }, [status, tab, placeId]);
  const province =
    search.filters.boundaryMode === "before"
      ? place?.provinceBefore
      : place?.provinceAfter;
  const mapPlaces = useMemo(
    () => place ? [{ ...place, province }] : [],
    [place, province],
  );
  if (status !== "ready")
    return (
      <main className="detail-page">
        <Link className="back-link" to="/">
          <ArrowLeft />
          Quay lại danh sách địa điểm
        </Link>
        <div className="page-state">
          {status === "loading" ? (
            <>
              <LoaderCircle className="spin" />
              <h1>Đang tải địa điểm…</h1>
            </>
          ) : (
            <>
              <SearchX />
              <h1>
                {status === "missing"
                  ? "Không tìm thấy địa điểm"
                  : "Không thể tải địa điểm"}
              </h1>
              <p>
                {status === "missing"
                  ? "Địa điểm này không tồn tại trong bộ dữ liệu."
                  : error}
              </p>
              {status === "error" && (
                <button
                  className="button primary"
                  onClick={() => setRetry((n) => n + 1)}
                >
                  Thử lại
                </button>
              )}
              <Link className="button primary" to="/">
                Về trang khám phá
              </Link>
            </>
          )}
        </div>
      </main>
    );
  return (
    <main className="detail-page">
      <div className="detail-topbar">
        <Link className="back-link" to="/">
          <ArrowLeft />
          Quay lại danh sách địa điểm
        </Link>
      </div>
      <h1>{place.name}</h1>
      <div className="detail-meta">
        {place.tourismTypes.map((type) => (
          <span className="detail-type-badge" key={type.id}>{type.name}</span>
        ))}
      </div>
      {place.other_names.length > 0 && (
        <p className="detail-other-names">
          <Tags aria-hidden="true" />
          <strong>Tên gọi khác:</strong>
          <span>{place.other_names.join(", ")}</span>
        </p>
      )}
      <Gallery images={place.images} openImage={setLightboxIndex} />
      <div
        className="detail-tabs"
        role="tablist"
        aria-label="Thông tin địa điểm"
      >
        {tabs.map(({ id, name, Icon }) => (
          <button
            id={`tab-${id}`}
            key={id}
            role="tab"
            aria-selected={tab === id}
            aria-controls={`panel-${id}`}
            tabIndex={tab === id ? 0 : -1}
            onClick={() => setTab(id)}
            onKeyDown={(event) => {
              const index = tabs.findIndex((t) => t.id === id);
              if (
                ["ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key)
              ) {
                event.preventDefault();
                const next =
                  event.key === "Home"
                    ? 0
                    : event.key === "End"
                      ? tabs.length - 1
                      : (index +
                        (event.key === "ArrowRight" ? 1 : -1) +
                        tabs.length) % tabs.length;
                setTab(tabs[next].id);
                document.getElementById(`tab-${tabs[next].id}`)?.focus();
              }
            }}
          >
            <Icon />
            {name}
          </button>
        ))}
      </div>
      <div className="detail-columns">
        <section
          ref={overviewRef}
          className={`overview-panel${tab === "overview" ? " overview-summary" : ""}`}
          style={tab === "overview" && !overviewExpanded && overviewHeight
            ? { height: overviewHeight }
            : undefined}
        >
          <div
            className={`tab-content${tab === "overview" ? " overview-tab" : ""}`}
            role="tabpanel"
            id={`panel-${tab}`}
            aria-labelledby={`tab-${tab}`}
            tabIndex={0}
          >
            {tab === "overview" && (
              <>
                <h2 ref={descriptionHeadingRef} className="description-heading">
                  <BookOpen aria-hidden="true" />
                  Mô tả địa điểm
                </h2>
                <div
                  id="place-description"
                  className={`description-clip${!overviewExpanded && canExpandOverview ? " is-clipped" : ""}${overviewExpanded ? " is-expanded" : ""}`}
                >
                  <div ref={descriptionTextRef} className="description-text">
                    {place.descriptionParts.map((part) => (
                      <p key={part.id} data-description-id={part.id}>{part.text}</p>
                    ))}
                  </div>
                </div>
                {canExpandOverview && (
                  <button
                    type="button"
                    className="description-toggle"
                    aria-expanded={overviewExpanded}
                    aria-controls="place-description"
                    onClick={() => {
                      if (overviewExpanded)
                        overviewRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
                      setOverviewExpanded((expanded) => !expanded);
                    }}
                  >
                    {overviewExpanded ? "Thu gọn" : "Xem thêm"}
                    {overviewExpanded ? <ChevronUp aria-hidden="true" /> : <ChevronDown aria-hidden="true" />}
                  </button>
                )}
              </>
            )}
            {tab === "images" && (
              <>
                <h2>Hình ảnh {place.name}</h2>
                <p className="muted">
                  Hình ảnh của địa điểm trong bộ dữ liệu.
                </p>
                <div className="tab-gallery">
                  {place.images.map((image, i) => (
                    <button
                      key={image.src}
                      onClick={() => setLightboxIndex(i)}
                      aria-label={`Xem ảnh ${i + 1}`}
                    >
                      <PlaceImage image={image} />
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        </section>
        <aside className="location-panel" ref={locationRef}>
          <h2>
            <MapPin />
            Vị trí địa điểm
          </h2>
          <PlacesMap
            places={mapPlaces}
            selectedId={place.place_id}
            selectionVersion={coordinateVersion}
            detail
          />
          <div className="location-addresses">
            <div className="location-address">
              <BookOpen aria-hidden="true" />
              <div>
                <strong>Địa chỉ (trước sáp nhập):</strong>
                <span>{place.address.former}</span>
              </div>
            </div>
            <div className="location-address">
              <MapPin aria-hidden="true" />
              <div>
                <strong>Địa chỉ (sau sáp nhập):</strong>
                <span>{place.address.current}</span>
              </div>
            </div>
          </div>
          <button
            className="button location-map-button full-width"
            onClick={() => {
              const map = locationRef.current?.querySelector(".leaflet-container");
              map?.scrollIntoView({ behavior: "smooth", block: "center" });
              map?.focus({ preventScroll: true });
              setCoordinateVersion((version) => version + 1);
            }}
          >
            Xem tọa độ <MapPin aria-hidden="true" />
          </button>
        </aside>
      </div>
      <footer className="detail-footer">
        <Info />
        Thông tin, vị trí và hình ảnh từ bộ dữ liệu thu thập
      </footer>
      {lightboxIndex !== null && (
        <Lightbox
          images={place.images}
          index={lightboxIndex}
          onChange={setLightboxIndex}
          onClose={() => setLightboxIndex(null)}
        />
      )}
    </main>
  );
}
