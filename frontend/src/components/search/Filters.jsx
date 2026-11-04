import { ChevronUp, ListFilter } from "lucide-react";
import { useSearch } from "../../context/SearchContext";
export default function Filters() {
  const {
    filters,
    updateFilter,
    clearFilters,
    filterOptions,
    filtersCollapsed,
    setFiltersCollapsed,
    filtersStatus,
    filtersError,
    retryFilters,
  } = useSearch();
  return (
    <section className="filters">
      <button
        type="button"
        className="filter-heading"
        aria-expanded={!filtersCollapsed}
        aria-controls="filter-fields"
        onClick={() => setFiltersCollapsed((value) => !value)}
      >
        <span>
          <ListFilter />
          Bộ lọc
        </span>
        <ChevronUp className={filtersCollapsed ? "rotated" : ""} />
      </button>
      {!filtersCollapsed && (
        <div id="filter-fields">
          <div className="filter-grid">
            <div className="filter-field">
              <label htmlFor="boundary-mode">Địa giới</label>
              <select
                id="boundary-mode"
                value={filters.boundaryMode}
                onChange={(event) =>
                  updateFilter("boundaryMode", event.target.value)
                }
              >
                <option value="before">Trước sáp nhập</option>
                <option value="after">Sau sáp nhập</option>
              </select>
            </div>
            <div className="filter-field">
              <label htmlFor="province">Tỉnh/Thành phố</label>
              <select
                id="province"
                disabled={filtersStatus !== "ready"}
                value={filters.province}
                onChange={(event) =>
                  updateFilter("province", event.target.value)
                }
              >
                <option value="">Tất cả</option>
                {filterOptions.provinces.map((item) => (
                  <option key={item.id} value={item.id}>{item.name}</option>
                ))}
              </select>
            </div>
            <div className="filter-field">
              <label htmlFor="place-type">Loại hình</label>
              <select
                id="place-type"
                disabled={filtersStatus !== "ready"}
                value={filters.type}
                onChange={(event) => updateFilter("type", event.target.value)}
              >
                <option value="">Tất cả</option>
                {filterOptions.types.map((item) => (
                  <option key={item.id} value={item.id}>{item.name}</option>
                ))}
              </select>
            </div>
          </div>
          {filtersStatus === "loading" && <p className="muted" role="status">Đang tải danh mục…</p>}
          {filtersStatus === "error" && (
            <div className="form-error" role="alert">
              <p>Không tải được bộ lọc. {filtersError}</p>
              <button type="button" className="text-button" onClick={retryFilters}>Thử lại bộ lọc</button>
            </div>
          )}
          <button
            type="button"
            className="text-button reset-filters"
            onClick={clearFilters}
          >
            Xóa bộ lọc
          </button>
        </div>
      )}
    </section>
  );
}
