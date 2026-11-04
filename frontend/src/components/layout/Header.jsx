import { NavLink, Link } from "react-router-dom";
import { Compass, Info } from "lucide-react";
import logo from "../../assets/logo.png";
export default function Header() {
  return (
    <header className="site-header">
      <Link
        className="brand"
        to="/"
        aria-label="Du lịch Tây Nam Bộ - Trang khám phá"
      >
        <img src={logo} alt="" />
        <span>
          <strong>Bản Đồ Du Lịch Tây Nam Bộ</strong>
          <span>Tìm kiếm địa điểm du lịch bằng văn bản và hình ảnh</span>
        </span>
      </Link>
      <nav aria-label="Điều hướng chính">
        <NavLink
          to="/"
          end
        >
          <Compass />
          <span>Bản đồ</span>
        </NavLink>
        <NavLink to="/about">
          <Info />
          <span>Giới thiệu</span>
        </NavLink>
      </nav>
    </header>
  );
}
