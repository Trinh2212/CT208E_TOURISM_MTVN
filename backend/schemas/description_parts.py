"""Schema của một đoạn mô tả nhúng trong places.description_parts (không phải collection)."""

DESCRIPTION_PART_SCHEMA = {
    "bsonType": "object",
    "required": ["id", "text", "order"],
    "additionalProperties": False,
    "properties": {
        "id": {"bsonType": "string", "minLength": 1},
        "text": {"bsonType": "string", "minLength": 1},
        "order": {"bsonType": ["int", "long"], "minimum": 0},
    },
}
