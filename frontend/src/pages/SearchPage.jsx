import { useLayoutEffect, useRef, useState } from "react";
import {
  SearchX,
  Map,
  List,
  RotateCcw,
  LoaderCircle,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { useSearch } from "../context/SearchContext";
import SearchBar from "../components/search/SearchBar";
import Filters from "../components/search/Filters";
import PlaceCard from "../components/places/PlaceCard";
import PlacesMap from "../components/map/PlacesMap";
export default function SearchPage() {
  const state = useSearch();
  const list = useRef(null);
  const cardRefs = useRef({});
  const [selectionVersion, setSelectionVersion] = useState(0);
  const sidebarToggleLabel = state.sidebarCollapsed
    ? "Mở danh sách địa điểm"
    : "Thu gọn danh sách địa điểm";
  useLayoutEffect(() => {
    if (list.current?.clientHeight)
      list.current.scrollTop = state.listScroll.current;
  }, [state.listScroll, state.filters, state.sidebarCollapsed]);
  const select = (id, source) => {
    state.setSelectedId(id);
    if (source === "marker")
      cardRefs.current[id]?.scrollIntoView({
        block: "nearest",
        behavior: "smooth",
      });
    else setSelectionVersion((value) => value + 1);
  };
  return (
    <main className="search-page">
      <SearchBar />
      <div className="mobile-switch" role="group" aria-label="Chế độ xem">
        <button
          className={state.mobileView === "list" ? "active" : ""}
          onClick={() => state.setMobileView("list")}
        >
          <List />
          Danh sách
        </button>
        <button
          className={state.mobileView === "map" ? "active" : ""}
          onClick={() => state.setMobileView("map")}
        >
          <Map />
          Bản đồ
        </button>
      </div>
      <div className={`explore-workspace show-${state.mobileView}${state.sidebarCollapsed ? " results-collapsed" : ""}`}>
        <aside
          id="search-results-panel"
          className="results-panel"
          aria-label="Bộ lọc và danh sách địa điểm"
        >
          <Filters />
          <div className="results-heading">
            <h1>
              Địa điểm{" "}
              <span>
                {state.status === "loading" ? "…" : state.results.length}
              </span>
            </h1>
          </div>
          <div
            className="results-list"
            ref={list}
            onScroll={(event) => {
              if (event.currentTarget.clientHeight)
                state.listScroll.current = event.currentTarget.scrollTop;
            }}
            aria-busy={state.status === "loading"}
          >
            {state.status === "loading" ? (
              <div className="loading-state" role="status">
                <LoaderCircle className="spin" />
                <p>Đang tải địa điểm…</p>
                {[1, 2].map((n) => (
                  <div className="skeleton-card" key={n} />
                ))}
              </div>
            ) : state.status === "error" ? (
              <div className="empty-state" role="alert">
                <SearchX />
                <h2>Chưa thể tải địa điểm</h2>
                <p>{state.error}</p>
                <button className="button primary" onClick={state.retry}>
                  <RotateCcw />
                  Thử lại
                </button>
              </div>
            ) : !state.results.length ? (
              <div className="empty-state">
                <SearchX />
                <h2>Chưa tìm thấy địa điểm</h2>
                <p>Thay đổi hoặc xóa bộ lọc để khám phá thêm.</p>
                <button
                  className="button primary"
                  onClick={() => {
                    state.clearFilters();
                  }}
                >
                  Khám phá tất cả
                </button>
              </div>
            ) : (
              state.results.map((place, index) => (
                <PlaceCard
                  key={place.place_id}
                  place={place}
                  rank={index + 1}
                  selected={state.selectedId === place.place_id}
                  onSelect={() => select(place.place_id, "card")}
                  cardRef={(element) => {
                    cardRefs.current[place.place_id] = element;
                  }}
                />
              ))
            )}
          </div>
        </aside>
        <button
          type="button"
          className="sidebar-toggle"
          aria-label={sidebarToggleLabel}
          title={sidebarToggleLabel}
          aria-expanded={!state.sidebarCollapsed}
          aria-controls="search-results-panel"
          onClick={() => state.setSidebarCollapsed((collapsed) => !collapsed)}
        >
          {state.sidebarCollapsed
            ? <ChevronRight aria-hidden="true" />
            : <ChevronLeft aria-hidden="true" />}
        </button>
        <section className="main-map" aria-label="Bản đồ các địa điểm">
          <PlacesMap
            places={state.status === "ready" ? state.results : []}
            selectedId={state.selectedId}
            onSelect={select}
            viewport={state.viewport}
            selectionVersion={selectionVersion}
          />
          <span className="map-discovery-label">
            <span className="live-dot" />
            Khám phá Tây Nam Bộ
          </span>
        </section>
      </div>
    </main>
  );
}
