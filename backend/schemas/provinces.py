"""ràng buộc ctdl cho collection provinces"""

PROVINCES_SCHEMA = {
    "bsonType": "object",
    "required": ["_id", "name", "scheme"],
    "additionalProperties": False,
    "properties": {
        "_id": {"bsonType": "string", "minLength": 1},
        "name": {"bsonType": "string", "minLength": 1},
        "scheme": {"enum": ["former", "current"]},
        "former_province_ids": {
            "bsonType": "array",
            "minItems": 1,
            "uniqueItems": True,
            "items": {"bsonType": "string", "minLength": 1},
        },
    },
    "oneOf": [
        {
            "properties": {"scheme": {"enum": ["former"]}},
            "not": {"required": ["former_province_ids"]},
        },
        {
            "properties": {"scheme": {"enum": ["current"]}},
            "required": ["former_province_ids"],
        },
    ],
}
