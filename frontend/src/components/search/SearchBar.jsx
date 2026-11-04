import { useRef, useState } from "react";
import { ImagePlus, Search, X } from "lucide-react";
import { useSearch } from "../../context/SearchContext";
import {
  decodeImage,
  validateImageFiles,
} from "../../services/imageValidation";
export default function SearchBar() {
  const { text, setText, image, setImage } = useSearch();
  const input = useRef(null);
  const imagePreview = useRef(null);
  const [error, setError] = useState("");
  const [reading, setReading] = useState(false);
  async function selectImage(event) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (!files.length) return;
    const validation = validateImageFiles(files);
    if (validation) {
      setError(validation);
      return;
    }
    setReading(true);
    setError("");
    try {
      const url = await decodeImage(files[0]);
      setImage({ file: files[0], url });
    } catch (err) {
      setError(err.message);
    } finally {
      setReading(false);
    }
  }
  function handleSubmit(event) {
    event.preventDefault();
  }
  return (
    <section className="search-strip" aria-label="Tìm kiếm địa điểm">
      <form onSubmit={handleSubmit}>
        <div className="query-input">
          <Search aria-hidden="true" />
          <label className="sr-only" htmlFor="query">
            Mô tả địa điểm muốn tìm
          </label>
          <input
            id="query"
            ref={input}
            value={text}
            onChange={(event) => {
              setText(event.target.value);
              setError("");
            }}
            placeholder="Bạn muốn khám phá điều gì?"
            aria-describedby={error ? "search-error" : undefined}
          />
        </div>
        <div className={`image-query${image ? " has-image" : ""}`}>
          {image ? (
            <div className="image-selection">
              <button
                type="button"
                className="image-preview-button"
                aria-label={`Xem ảnh lớn: ${image.file.name}`}
                aria-haspopup="dialog"
                title="Xem ảnh lớn"
                onClick={() => imagePreview.current?.showModal()}
              >
                <img src={image.url} alt="Ảnh truy vấn đã chọn" />
              </button>
              <span title={image.file.name}>{image.file.name}</span>
              <button
                type="button"
                className="icon-button"
                aria-label="Xóa ảnh truy vấn"
                onClick={() => {
                  setImage(null);
                  setError("");
                }}
              >
                <X />
              </button>
            </div>
          ) : (
            <label className={`add-image ${reading ? "disabled" : ""}`}>
              <ImagePlus />
              <span>{reading ? "Đang đọc ảnh…" : "Thêm ảnh"}</span>
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp,image/gif"
                aria-label="Thêm một ảnh truy vấn"
                disabled={reading}
                onChange={selectImage}
              />
            </label>
          )}
        </div>
        <button
          className="button primary search-button"
          type="submit"
          disabled
        >
          <Search />
          <span>Tìm kiếm</span>
        </button>
        {error && (
          <p id="search-error" className="form-error" role="alert">
            {error}
          </p>
        )}
      </form>
      {image && (
        <dialog
          ref={imagePreview}
          className="query-image-preview"
          aria-label="Xem ảnh truy vấn"
          onClick={(event) => {
            if (event.target === event.currentTarget) event.currentTarget.close();
          }}
        >
          <button
            type="button"
            className="icon-button query-preview-close"
            aria-label="Đóng ảnh xem trước"
            onClick={() => imagePreview.current?.close()}
          >
            <X />
          </button>
          <figure>
            <img src={image.url} alt="Ảnh truy vấn đã chọn" />
            <figcaption>{image.file.name}</figcaption>
          </figure>
        </dialog>
      )}
    </section>
  );
}
