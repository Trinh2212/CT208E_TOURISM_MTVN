import { useState } from "react";
import { ChevronRight, Info, MapPin } from "lucide-react";
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
  const [showSnippet, setShowSnippet] = useState(false);
  const hasScore = typeof place.score === "number";
  const snippet = place.matchedEvidence?.snippet;
  const thumbnail = place.matchedEvidence?.image ?? place.coverImage;
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
        <PlaceImage image={thumbnail} loading="lazy" />
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
        <div className="card-bottom">
          {hasScore ? (
            <span className="score-group">
              <span className="match-score">Score: {place.score.toFixed(4)}</span>
              {snippet && (
                <button
                  type="button"
                  className={`snippet-toggle${showSnippet ? " active" : ""}`}
                  aria-label="Xem đoạn mô tả khớp nhất"
                  aria-expanded={showSnippet}
                  title="Xem đoạn mô tả khớp nhất"
                  onClick={(event) => {
                    event.stopPropagation();
                    setShowSnippet((value) => !value);
                  }}
                >
                  <Info aria-hidden="true" />
                </button>
              )}
            </span>
          ) : (
            <span className="explore-label">Địa điểm du lịch</span>
          )}
          <Link
            to={`/places/${encodeURIComponent(place.place_id)}`}
            onClick={(event) => event.stopPropagation()}
          >
            Xem chi tiết <ChevronRight aria-hidden="true" />
          </Link>
        </div>
        {hasScore && snippet && showSnippet && (
          <p
            className="matched-snippet"
            onClick={(event) => event.stopPropagation()}
          >
            {snippet}
          </p>
        )}
      </div>
    </article>
  );
}
