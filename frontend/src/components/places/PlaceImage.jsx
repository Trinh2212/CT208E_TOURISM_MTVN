import { useState } from "react";
import { ImageOff } from "lucide-react";
export default function PlaceImage({ image, className = "", ...props }) {
  const [failedSrc, setFailedSrc] = useState(null);
  if (failedSrc === image?.src || !image)
    return (
      <div
        className={`image-fallback ${className}`}
        role="img"
        aria-label="Ảnh chưa tải được"
      >
        <ImageOff />
        <span>Ảnh chưa tải được</span>
      </div>
    );
  return (
    <img
      {...props}
      className={className}
      src={image.src}
      alt={image.alt}
      onError={() => setFailedSrc(image.src)}
    />
  );
}
