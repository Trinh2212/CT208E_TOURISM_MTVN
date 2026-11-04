import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import { SearchProvider } from "./context/SearchContext";
import Header from "./components/layout/Header";
import SearchPage from "./pages/SearchPage";
import PlaceDetailPage from "./pages/PlaceDetailPage";
import AboutPage from "./pages/AboutPage";
export default function App() {
  return (
    <BrowserRouter>
      <SearchProvider>
        <a className="skip-link" href="#main-content">
          Bỏ qua điều hướng
        </a>
        <Header />
        <div id="main-content">
          <Routes>
            <Route path="/" element={<SearchPage />} />
            <Route path="/places/:placeId" element={<PlaceDetailPage />} />
            <Route path="/about" element={<AboutPage />} />
            <Route
              path="*"
              element={
                <main className="page-state">
                  <h1>Không tìm thấy trang</h1>
                  <Link className="button primary" to="/">
                    Về trang khám phá
                  </Link>
                </main>
              }
            />
          </Routes>
        </div>
      </SearchProvider>
    </BrowserRouter>
  );
}
