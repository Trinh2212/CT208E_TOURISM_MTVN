"""
Phục vụ file ảnh gốc (raster) từ thư mục DATA_ROOT/images:
- Tra cứu đường dẫn ảnh qua mảng `images` nhúng trong collection `places`.
- Kiểm tra bảo mật đường dẫn: chặn Path Traversal, chỉ cho phép file nằm trong DATA_ROOT/images.
- Xác định MIME type thực tế bằng Pillow (không tin phần mở rộng tên file).
"""
from pathlib import PurePosixPath, PureWindowsPath

from PIL import Image
from werkzeug.exceptions import NotFound


def get_image_file(database, data_root, image_id):
    """
    Tìm và trả về đường dẫn tuyệt đối cùng MIME type của file ảnh theo image_id.
    Ném NotFound nếu ảnh không tồn tại trong DB hoặc file trên ổ đĩa không hợp lệ.
    """
    document = database.places.find_one(
        {"images._id": image_id}, {"images": {"$elemMatch": {"_id": image_id}}},
    )
    if document is None:
        raise NotFound("Không tìm thấy ảnh.")
    try:
        stored_path = document["images"][0]["path"]
        if not isinstance(stored_path, str) or not stored_path:
            raise ValueError
        relative = PurePosixPath(stored_path.replace("\\", "/"))
        if (relative.is_absolute() or PureWindowsPath(stored_path).drive or ":" in stored_path
                or ".." in relative.parts or len(relative.parts) < 2 or relative.parts[0] != "images"):
            raise ValueError
        root = data_root.resolve(strict=True)
        images_root = (root / "images").resolve(strict=True)
        path = (root / relative).resolve(strict=True)
        if not images_root.is_relative_to(root) or not path.is_relative_to(images_root) or not path.is_file():
            raise ValueError
        with Image.open(path) as image:
            mimetype = Image.MIME.get(image.format)
        if mimetype is None or not mimetype.startswith("image/"):
            raise ValueError
        return path, mimetype
    except (KeyError, IndexError, TypeError, OSError, ValueError, RuntimeError, Image.DecompressionBombError):
        # Đường dẫn file hệ thống và thông báo lỗi OS tuyệt đối không được lộ ra response.
        raise NotFound("Không tìm thấy tệp ảnh hợp lệ.") from None
