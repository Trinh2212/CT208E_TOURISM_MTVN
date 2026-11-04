export const MAX_IMAGE_SIZE = 10 * 1024 * 1024;
export function validateImageFiles(files) {
  if (files.length !== 1) return "Mỗi truy vấn chỉ được dùng một ảnh.";
  if (
    !["image/jpeg", "image/png", "image/webp", "image/gif"].includes(
      files[0].type,
    )
  )
    return "Hãy chọn ảnh JPG, PNG, WebP hoặc GIF hợp lệ.";
  if (files[0].size === 0) return "Tệp ảnh đang trống. Hãy chọn ảnh khác.";
  if (files[0].size > MAX_IMAGE_SIZE)
    return "Ảnh quá lớn. Vui lòng chọn ảnh tối đa 10 MB.";
  return null;
}
export async function decodeImage(file) {
  const url = URL.createObjectURL(file);
  try {
    await new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = resolve;
      image.onerror = reject;
      image.src = url;
    });
    return url;
  } catch {
    URL.revokeObjectURL(url);
    throw new Error(
      "Không đọc được nội dung ảnh. Hãy chọn một tệp ảnh hợp lệ.",
    );
  }
}
