"""
Nạp file backend/.env theo đường dẫn tương đối với file này không phụ thuộc thư mục làm việc.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
ENV_FILE = BACKEND_DIR / ".env"


class ConfigurationError(ValueError):
    """Lỗi cấu hình; thông báo không bao giờ được chứa MongoDB URI."""


@dataclass(frozen=True)
class Settings:
    """Cấu hình bất biến cho toàn bộ backend (API và script CLI).
    ``mongodb_uri`` bị ẩn khỏi ``repr()`` để không vô tình in credential.
    Đường dẫn ``dataset_path`` và ``data_root`` có giá trị mặc định tương đối
    với thư mục gốc dự án.
    """
    mongodb_uri: str = field(repr=False)
    mongodb_database: str
    mongodb_timeout_ms: int
    dataset_path: Path = PROJECT_ROOT / "dataset" / "raw" / "raw_dataset.json"
    data_root: Path = PROJECT_ROOT / "dataset" / "raw"


def load_settings() -> Settings:
    """Đọc cấu hình từ biến môi trường và file backend/.env, validate, trả về Settings.
    Biến môi trường hệ thống có ưu tiên cao hơn file .env (``override=False``).
    Đường dẫn tương đối được tự động resolve từ thư mục gốc dự án.
    """
    # Biến môi trường hệ thống ưu tiên hơn file .env cục bộ.
    load_dotenv(dotenv_path=ENV_FILE, override=False, encoding="utf-8-sig")
    uri = os.getenv("MONGODB_URI", "mongodb://127.0.0.1:27017").strip()
    name = os.getenv("MONGODB_DATABASE", "tourism_search").strip()
    if not uri:
        raise ConfigurationError("MONGODB_URI không được để trống trong backend/.env.")
    if not name or any(char in name for char in '/\\. "$*<>:|?\x00'):
        raise ConfigurationError("MONGODB_DATABASE phải là tên database hợp lệ, không rỗng.")
    try:
        timeout = int(os.getenv("MONGODB_TIMEOUT_MS", "5000"))
        if timeout <= 0:
            raise ValueError
    except ValueError:
        raise ConfigurationError("MONGODB_TIMEOUT_MS phải là số nguyên dương.") from None
    def configured_path(key: str, default: str) -> Path:
        value = os.getenv(key, default).strip()
        if not value:
            raise ConfigurationError(f"{key} không được để trống.")
        path = Path(value).expanduser()
        return (path if path.is_absolute() else PROJECT_ROOT / path).resolve()

    return Settings(
        uri, name, timeout,
        configured_path("DATASET_PATH", "dataset/raw/raw_dataset.json"),
        configured_path("DATA_ROOT", "dataset/raw"),
    )
