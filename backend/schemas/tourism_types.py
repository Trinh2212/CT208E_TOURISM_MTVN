"""ràng buộc ctdl cho collection tourism_types"""

TOURISM_TYPES_SCHEMA = {
    "bsonType": "object",
    "required": ["_id", "name"],
    "additionalProperties": False,
    "properties": {
        "_id": {"bsonType": "string", "minLength": 1},
        "name": {"bsonType": "string", "minLength": 1},
    },
}
