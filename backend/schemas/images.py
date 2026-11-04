"""Schema của một ảnh nhúng trong places.images (không phải collection)."""

IMAGE_SCHEMA = {
    "bsonType": "object", # kiểu dữ liệu
    "required": ["_id", "path", "caption", "order"],
    "additionalProperties": False, # không cho phép các trường khác
    "properties": {
        "_id": {"bsonType": "string", "minLength": 1},
        "path": {"bsonType": "string", "minLength": 1},
        "caption": {"bsonType": "string"},
        "order": {"bsonType": ["int", "long"], "minimum": 0},
    },
}
