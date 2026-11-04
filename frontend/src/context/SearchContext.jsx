import { createContext, useContext, useEffect, useRef, useState } from "react";
import * as service from "../services/placesService";
const SearchContext = createContext(null);
const defaultFilters = { boundaryMode: "after", province: "", type: "" };
export function SearchProvider({ children }) {
  const [text, setText] = useState("");
  const [image, setImage] = useState(null);
  const [filters, setFilters] = useState(defaultFilters);
  const [results, setResults] = useState([]);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [filterOptions, setFilterOptions] = useState({ provinces: [], types: [] });
  const [optionsBoundary, setOptionsBoundary] = useState(null);
  const [filtersStatus, setFiltersStatus] = useState("loading");
  const [filtersError, setFiltersError] = useState("");
  const [filtersCollapsed, setFiltersCollapsed] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileView, setMobileView] = useState("list");
  const viewport = useRef(null);
  const listScroll = useRef(0);
  const [retry, setRetry] = useState(0);
  const [filtersRetry, setFiltersRetry] = useState(0);
  useEffect(() => {
    const url = image?.url;
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [image]);
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setFiltersStatus("loading");
    setFiltersError("");
    setFilterOptions({ provinces: [], types: [] });
    service.getFilters({ boundaryMode: filters.boundaryMode, signal: controller.signal })
      .then((options) => {
        if (!active) return;
        setFilterOptions(options);
        setOptionsBoundary(filters.boundaryMode);
        setFiltersStatus("ready");
      })
      .catch((err) => {
        if (!active || err.name === "AbortError") return;
        setFiltersError(err.message);
        setFiltersStatus("error");
      });
    return () => { active = false; controller.abort(); };
  }, [filters.boundaryMode, filtersRetry]);
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setStatus("loading");
    setError("");
    setResults([]);
    service.listPlaces(filters, { signal: controller.signal })
      .then((items) => {
        if (!active) return;
        setResults(items);
        setSelectedId((id) => items.some((item) => item.place_id === id) ? id : null);
        setStatus("ready");
      })
      .catch((err) => {
        if (!active || err.name === "AbortError") return;
        setResults([]);
        setError(err.message);
        setStatus("error");
      });
    return () => { active = false; controller.abort(); };
  }, [filters, retry]);
  const updateFilter = (name, value) => {
    listScroll.current = 0;
    setFilters((current) => ({
      ...current, [name]: value,
      ...(name === "boundaryMode" ? { province: "" } : {}),
    }));
  };
  const clearFilters = () => {
    listScroll.current = 0;
    setFilters(defaultFilters);
  };
  return (
    <SearchContext.Provider value={{
      text, setText, image, setImage, filters, updateFilter, clearFilters,
      results, status, error, selectedId, setSelectedId, viewport, listScroll,
      filterOptions,
      filtersStatus: optionsBoundary !== filters.boundaryMode && filtersStatus !== "error" ? "loading" : filtersStatus,
      filtersError, retryFilters: () => setFiltersRetry((n) => n + 1),
      filtersCollapsed, setFiltersCollapsed, mobileView, setMobileView,
      sidebarCollapsed, setSidebarCollapsed,
      retry: () => setRetry((n) => n + 1),
    }}>{children}</SearchContext.Provider>
  );
}
export const useSearch = () => useContext(SearchContext);
