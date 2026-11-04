import { Image, Map, MapPin, Signpost, Info, ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import mekong from "../assets/about-mekong.jpg";
export default function AboutPage() {
  return (
    <main className="about-page">
      <section className="about-hero" aria-labelledby="about-title">
        <div className="about-hero-copy">
          <h1 id="about-title">
            Khám phá miền Tây theo<br />
            trải nghiệm của riêng bạn
          </h1>
          <p className="about-intro">
            Bản Đồ Du Lịch Tây Nam Bộ giúp bạn tìm kiếm và khám phá các điểm đến
            thông qua văn bản, hình ảnh và bản đồ tương tác. Từ cảnh quan sông nước,
            miệt vườn đến các công trình kiến trúc và không gian văn hóa, lịch sử,
            mỗi địa điểm mang đến một góc nhìn riêng về vùng đất và con người miền Tây.
          </p>
        </div>
        <figure className="about-hero-image">
          <img
            src={mekong}
            alt="Minh họa sông nước miền Tây với ghe, hàng dừa và những ngôi nhà ven sông"
          />
        </figure>
      </section>
      <div className="about-grid">
        <article>
          <div className="about-feature-heading">
            <span className="about-feature-icon" aria-hidden="true">
              <Image />
            </span>
            <h2>Tìm kiếm địa điểm bằng văn bản và hình ảnh</h2>
          </div>
          <p>
            Mô tả địa điểm bạn muốn tìm, lựa chọn một hình ảnh gợi ý hoặc kết hợp cả hai.
            Sử dụng bộ lọc theo tỉnh thành và loại hình du lịch
          </p>
        </article>
        <article>
          <div className="about-feature-heading">
            <span className="about-feature-icon" aria-hidden="true">
              <Map />
            </span>
            <h2>Khám phá các điểm đến trên bản đồ</h2>
          </div>
          <p>
            Danh sách địa điểm được kết nối với bản đồ tương tác, giúp bạn dễ dàng
            xem vị trí và lựa chọn điểm đến quan tâm. Tại trang chi tiết, bạn có thể
            xem thư viện hình ảnh và tìm hiểu thêm về địa điểm.
          </p>
        </article>
        <article>
          <div className="about-feature-heading">
            <span className="about-feature-icon" aria-hidden="true">
              <MapPin />
            </span>
            <h2>Tra cứu địa chỉ trước và sau sáp nhập</h2>
          </div>
          <p>
            Hệ thống hỗ trợ tra cứu địa điểm theo địa giới hành chính trước và sau sáp nhập.
            Thông tin địa chỉ ở cả hai giai đoạn được hiển thị cùng nhau, giúp bạn dễ dàng
            tìm kiếm, nhận biết và đối chiếu vị trí của các điểm đến.
          </p>
        </article>
      </div>
      <section className="about-cta" aria-labelledby="about-cta-title">
        <div className="about-cta-icon" aria-hidden="true">
          <Signpost />
        </div>
        <div className="about-cta-copy">
          <h2 id="about-cta-title">Bắt đầu hành trình khám phá</h2>
          <p>
            Khám phá các địa điểm du lịch qua bản đồ và tìm kiếm theo văn bản hoặc hình ảnh.
          </p>
        </div>
        <Link className="button primary about-map-link" to="/">
          <Map aria-hidden="true" />
          Khám phá bản đồ
          <ArrowRight aria-hidden="true" />
        </Link>
      </section>
      <section className="about-data-note" aria-labelledby="about-data-title">
        <h2 id="about-data-title">
          <Info aria-hidden="true" />
          Thông tin về dữ liệu
        </h2>
        <p>
          Dữ liệu địa điểm được biên soạn trong phạm vi nghiên cứu. Thông tin và
          hình ảnh được cung cấp trong phạm vi dữ liệu hiện có, không đại diện cho
          toàn bộ địa điểm du lịch Tây Nam Bộ.
        </p>
      </section>
    </main>
  );
}
