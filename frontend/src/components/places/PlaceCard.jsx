import { ChevronRight, MapPin } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import PlaceImage from "./PlaceImage";
export default function PlaceCard({
  place,
  rank,
  selected,
  onSelect,
  cardRef,
}) {
  const navigate = useNavigate();
  return (
    <article
      ref={cardRef}
      data-place-id={place.place_id}
      className={`place-card ${selected ? "selected" : ""}`}
      onClick={() => navigate(`/places/${encodeURIComponent(place.place_id)}`)}
    >
      <button
        className="card-select"
        onClick={(event) => {
          event.stopPropagation();
          onSelect();
        }}
        aria-label={`Chọn ${place.name} trên bản đồ`}
        aria-pressed={selected}
      >
        <PlaceImage image={place.coverImage} loading="lazy" />
        <span className="rank">{rank}</span>
      </button>
      <div className="card-body">
        <div className="card-heading">
          <h3>{place.name}</h3>
          <span className="type-badge">{place.type}</span>
        </div>
        <div className="place-province">
          <MapPin aria-hidden="true" />
          {place.province}
        </div>
        {/* sau này đổi thành score của tìm kiếm */}
        <div className="card-bottom">
          <span className="explore-label">Địa điểm du lịch</span>
          <Link
            to={`/places/${encodeURIComponent(place.place_id)}`}
            onClick={(event) => event.stopPropagation()}
          >
            Xem chi tiết <ChevronRight aria-hidden="true" />
          </Link>
        </div>
      </div>
    </article>
  );
}
