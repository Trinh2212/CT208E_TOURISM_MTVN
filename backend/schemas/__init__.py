"""
Đăng ký schema cho 3 collection: provinces, tourism_types, places.
Schema ảnh (images.py) và đoạn mô tả (description_parts.py) được nhúng trong places.
Dùng cho script khởi tạo MongoDB (init_db) và kiểm tra tính toàn vẹn (dataset/validate).
"""

from backend.schemas.places import PLACES_SCHEMA
from backend.schemas.provinces import PROVINCES_SCHEMA
from backend.schemas.tourism_types import TOURISM_TYPES_SCHEMA

COLLECTION_SCHEMAS = {
    "provinces": PROVINCES_SCHEMA,
    "tourism_types": TOURISM_TYPES_SCHEMA,
    "places": PLACES_SCHEMA,
}
