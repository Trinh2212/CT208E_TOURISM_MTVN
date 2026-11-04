"""
Ràng buộc cấu trúc dữ liệu cho collection places (Địa điểm du lịch).
- Tọa độ GeoJSON Point: [kinh_độ, vĩ_độ] (không đảo ngược).
- Mảng ảnh nhúng (`images`): dùng IMAGE_SCHEMA cho từng phần tử.
- Mảng đoạn mô tả (`description_parts`): dùng DESCRIPTION_PART_SCHEMA cho từng phần tử.
"""

from backend.schemas.description_parts import DESCRIPTION_PART_SCHEMA
from backend.schemas.images import IMAGE_SCHEMA

PLACES_SCHEMA = {
    "bsonType": "object",
    "required": [
        "_id", "name", "other_names", "province_former_id", "address",
        "location", "tourism_type_ids", "cover_image_id", "description_parts", "images",
    ],
    "additionalProperties": False,
    "properties": {
        "_id": {"bsonType": "string", "minLength": 1},
        "name": {"bsonType": "string", "minLength": 1},
        "other_names": {
            "bsonType": "array",
            "items": {"bsonType": "string", "minLength": 1},
        },
        "province_former_id": {"bsonType": "string", "minLength": 1},
        "address": {
            "bsonType": "object",
            "required": ["former", "current"],
            "additionalProperties": False,
            "properties": {
                "former": {"bsonType": "string"},
                "current": {"bsonType": "string"},
            },
        },
        "location": {
            "bsonType": "object",
            "required": ["type", "coordinates"],
            "additionalProperties": False,
            "properties": {
                "type": {"enum": ["Point"]},
                "coordinates": {
                    "bsonType": "array",
                    "minItems": 2,
                    "maxItems": 2,
                    "items": [
                        {"bsonType": ["double", "int", "long", "decimal"], "minimum": -180, "maximum": 180},
                        {"bsonType": ["double", "int", "long", "decimal"], "minimum": -90, "maximum": 90},
                    ],
                    "additionalItems": False,
                    "description": "GeoJSON Point: [lng, lat], không phải [lat, lng].",
                },
            },
        },
        "tourism_type_ids": {
            "bsonType": "array",
            "uniqueItems": True,
            "items": {"bsonType": "string", "minLength": 1},
        },
        "cover_image_id": {"bsonType": ["string", "null"], "minLength": 1},
        "images": {"bsonType": "array", "items": IMAGE_SCHEMA},
        "description_parts": {"bsonType": "array", "items": DESCRIPTION_PART_SCHEMA},
    },
}
