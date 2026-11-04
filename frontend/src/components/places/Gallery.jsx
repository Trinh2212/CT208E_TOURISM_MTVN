import { useEffect, useRef } from "react";
import { ArrowRight, ChevronLeft, ChevronRight, X, Images } from "lucide-react";
import PlaceImage from "./PlaceImage";
export function Lightbox({ images, index, onChange, onClose }) {
  const dialog = useRef(null);
  const closeButton = useRef(null);
  const thumbnails = useRef(null);
  const callbacks = useRef({ onChange, onClose, index });
  callbacks.current = { onChange, onClose, index };
  useEffect(() => {
    const strip = thumbnails.current;
    const thumbnail = strip?.children[index];
    if (!strip || !thumbnail) return;
    let frame = 0;
    const cancel = () => cancelAnimationFrame(frame);
    function keepThumbnailVisible() {
      cancel();
      const left = thumbnail.offsetLeft;
      const right = left + thumbnail.offsetWidth;
      const padding = 12;
      const start = strip.scrollLeft;
      let target = start;
      if (left < start + padding) target = left - padding;
      else if (right > start + strip.clientWidth - padding)
        target = right - strip.clientWidth + padding;
      target = Math.max(0, Math.min(target, strip.scrollWidth - strip.clientWidth));
      const distance = target - start;
      if (Math.abs(distance) < 1) return;
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        strip.scrollLeft = target;
        return;
      }

      const duration = Math.min(1100, Math.max(500, Math.abs(distance) * 0.7));
      const startedAt = performance.now();
      function animate(time) {
        const progress = Math.min(1, (time - startedAt) / duration);
        const eased = progress < 0.5
          ? 2 * progress * progress
          : 1 - Math.pow(-2 * progress + 2, 2) / 2;
        strip.scrollLeft = start + distance * eased;
        if (progress < 1) frame = requestAnimationFrame(animate);
      }
      frame = requestAnimationFrame(animate);
    }
    const observer = new ResizeObserver(keepThumbnailVisible);
    observer.observe(strip);
    observer.observe(thumbnail);
    keepThumbnailVisible();
    // Hủy hiệu ứng cuộn tự động ngay khi người dùng chủ động cuộn hoặc kéo thanh cuộn.
    strip.addEventListener("pointerdown", cancel, { passive: true });
    strip.addEventListener("wheel", cancel, { passive: true });
    return () => {
      observer.disconnect();
      cancel();
      strip.removeEventListener("pointerdown", cancel);
      strip.removeEventListener("wheel", cancel);
    };
  }, [index, images.length]);
  useEffect(() => {
    const previous = document.activeElement;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButton.current?.focus();
    function keyboard(event) {
      const { onClose, onChange, index } = callbacks.current;
      if (event.key === "Escape") onClose();
      if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
        event.preventDefault();
        onChange((index + (event.key === "ArrowRight" ? 1 : -1) + images.length) % images.length);
      }
      if (event.key === "Tab") {
        const buttons = Array.from(dialog.current.querySelectorAll("button"));
        const first = buttons[0],
          last = buttons.at(-1);
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    }
    document.addEventListener("keydown", keyboard);
    return () => {
      document.body.style.overflow = overflow;
      document.removeEventListener("keydown", keyboard);
      previous?.focus();
    };
  }, [images.length]);
  return (
    <div
      className="lightbox"
      role="dialog"
      aria-modal="true"
      aria-label="Thư viện hình ảnh địa điểm"
      ref={dialog}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="lightbox-top">
        <span>
          Hình ảnh địa điểm{" "}
          <small>
            {index + 1} / {images.length}
          </small>
        </span>
        <button
          className="icon-button"
          ref={closeButton}
          aria-label="Đóng thư viện ảnh"
          onClick={onClose}
        >
          <X />
        </button>
      </div>
      <button
        className="lightbox-prev icon-button"
        aria-label="Ảnh trước"
        onClick={() => onChange((index - 1 + images.length) % images.length)}
      >
        <ChevronLeft />
      </button>
      <figure>
        <PlaceImage image={images[index]} />
        <figcaption>{images[index].caption}</figcaption>
      </figure>
      <button
        className="lightbox-next icon-button"
        aria-label="Ảnh tiếp theo"
        onClick={() => onChange((index + 1) % images.length)}
      >
        <ChevronRight />
      </button>
      <div className="lightbox-thumbnails" ref={thumbnails}>
        {images.map((image, i) => (
          <button
            key={image.src}
            className={i === index ? "active" : ""}
            aria-label={`Xem ảnh ${i + 1}`}
            onClick={() => onChange(i)}
          >
            <PlaceImage image={image} />
          </button>
        ))}
      </div>
    </div>
  );
}
export default function Gallery({ images, openImage }) {
  return (
    <div className={`gallery gallery-count-${Math.min(images.length, 3)}`}>
      {images.slice(0, 3).map((image, index) => (
        <button
          className={`gallery-image gallery-image-${index}`}
          key={image.src}
          aria-label={`Mở ảnh ${index + 1}`}
          onClick={() => openImage(index)}
        >
          <PlaceImage image={image} />
        </button>
      ))}
      <button className="gallery-all" disabled={!images.length} onClick={() => openImage(0)}>
        <Images />
        Xem tất cả {images.length} ảnh <ArrowRight />
      </button>
    </div>
  );
}
