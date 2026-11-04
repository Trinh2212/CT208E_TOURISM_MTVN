"""
khởi tạo collections và đánh index
- kiểm tra kết nối tới mongodb
- khởi tạo 3 collections (ảnh nhúng trong places)
- gắn bộ quy tắc và kiểm tra json schema
- tạo các chỉ mục 
"""

import sys

from pymongo import ASCENDING
from pymongo.errors import CollectionInvalid, OperationFailure, PyMongoError

from backend.config import ConfigurationError, load_settings
from backend.database import DatabaseConnectionError, connect_database, describe_mongo_error
from backend.schemas import COLLECTION_SCHEMAS

INDEXES = {
    "places": [
        ("idx_places_province_former_id", [("province_former_id", ASCENDING)]),
        ("idx_places_tourism_type_ids", [("tourism_type_ids", ASCENDING)]),
        ("idx_places_images_id", [("images._id", ASCENDING)]),
    ],
}
INDEX_OPTIONS = {
    "idx_places_images_id": {
        "unique": True,
        "partialFilterExpression": {"images._id": {"$type": "string"}},
    },
}

def validator_matches(options, schema):
    """
    kiểm tra validator hiện có của collection trên mongodb 
    có khớp với Json Schema được định nghĩa không
    """
    return (
        options.get("validator", {}) == {"$jsonSchema": schema}
        and options.get("validationLevel", "strict") == "strict"
        and options.get("validationAction", "error") == "error"
    )


def index_matches(index, keys, options=None):
    """kiểm tra index hiện có trong mongo có khớp với cấu hình cần tạo không"""
    options = options or {}
    return (
        list(index["key"].items()) == keys
        and bool(index.get("unique", False)) == options.get("unique", False)
        and not any(index.get(option, False) for option in ("sparse", "hidden"))
        and index.get("partialFilterExpression") == options.get("partialFilterExpression")
        and "expireAfterSeconds" not in index
        and index.get("collation", {}).get("locale", "simple") == "simple"
    )


def ensure_indexes(collection, reports):
    """
    đảm bảo các index cần thiết của collection được tạo an toàn:
    bỏ qua nếu đã có, cảnh báo nếu xung đột, tạo mới và xác mình lại từ metadata
    """
    successful = True
    existing = list(collection.list_indexes())
    for name, keys in INDEXES.get(collection.name, []):
        options = INDEX_OPTIONS.get(name, {"unique": False})
        matching = next((index for index in existing if index_matches(index, keys, options)), None)
        if matching:
            reports[name] = f"đã tồn tại ({matching['name']})"
            continue
        conflicting = next((index for index in existing if index["name"] == name or list(index["key"].items()) == keys), None)
        if conflicting:
            reports[name] = "xung đột key/options; giữ nguyên index hiện có"
            successful = False
            continue
        try:
            collection.create_index(keys, name=name, **options)
            # Đọc lại metadata để xác nhận thay vì tin rằng lệnh tạo đã thành công.
            existing = list(collection.list_indexes())
            if any(index["name"] == name and index_matches(index, keys, options) for index in existing):
                reports[name] = "vừa tạo, đã kiểm tra"
            else:
                reports[name] = "không xác nhận được index sau khi tạo"
                successful = False
        except PyMongoError as error:
            reports[name] = describe_mongo_error(error)
            successful = False
    return successful


def initialize(database, collections, indexes):
    """
    Điều phối toàn bộ quy trình khởi tạo: duyệt qua 3 collection,
    tạo kèm validator strict/error và gọi ensure_indexes để đánh index tương ứng.
    """
    successful = True
    for name, schema in COLLECTION_SCHEMAS.items():
        try:
            metadata = next(database.list_collections(filter={"name": name}), None)
            created = False
            if metadata is None:
                try:
                    database.create_collection(
                        name,
                        validator={"$jsonSchema": schema},
                        validationLevel="strict",
                        validationAction="error",
                    )
                    created = True
                    collections[name] = "vừa tạo; chưa xác minh metadata"
                except (CollectionInvalid, OperationFailure) as error:
                    # Một tiến trình khác có thể đã tạo collection sau lần đọc đầu tiên.
                    if isinstance(error, OperationFailure) and error.code != 48:
                        raise
                metadata = next(database.list_collections(filter={"name": name}), None)
            state = "vừa tạo" if created else "đã tồn tại"
            if metadata is None:
                collections[name] = f"{state}; không đọc lại được metadata"
                successful = False
                continue
            if metadata.get("type") != "collection":
                collections[name] = f"{state}; không phải collection thông thường, giữ nguyên"
                successful = False
                continue
            if not validator_matches(metadata.get("options", {}), schema):
                collections[name] = f"{state}; validator/validationLevel/validationAction khác thiết kế, giữ nguyên"
                successful = False
                continue
            collections[name] = f"{state}; validator strict/error khớp thiết kế"
            if not ensure_indexes(database[name], indexes):
                successful = False
        except PyMongoError as error:
            collections[name] = f"{collections[name]}; {describe_mongo_error(error)}"
            successful = False
    return successful


def main() -> int:
    """
    Điểm khởi chạy từ dòng lệnh: cấu hình console UTF-8,
    đọc .env, kết nối MongoDB, chạy khởi tạo và in báo cáo trạng thái.
    """
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    collections = {name: "chưa kiểm tra/tạo được" for name in COLLECTION_SCHEMAS}
    indexes = {name: "chưa kiểm tra/tạo được" for specs in INDEXES.values() for name, _ in specs}
    client = None
    successful = False
    try:
        settings = load_settings()
        client, database = connect_database(settings)
        print("MongoDB ping: thành công.")
        successful = initialize(database, collections, indexes)
    except (ConfigurationError, DatabaseConnectionError) as error:
        print(f"Lỗi: {error}", file=sys.stderr)
    except PyMongoError as error:
        print(f"Lỗi: {describe_mongo_error(error)}", file=sys.stderr)
    finally:
        if client is not None:
            client.close()
        print("\nTrạng thái collection:")
        for name, state in collections.items():
            print(f"  {name}: {state}")
        print("Trạng thái index (ngoài _id_ mặc định):")
        for name, state in indexes.items():
            print(f"  {name}: {state}")
        print("Không import dữ liệu raw. Không kiểm tra tham chiếu giữa các document ở bước này.")
    if successful:
        print("Khởi tạo và kiểm tra metadata hoàn tất.")
    else:
        print("Chưa hoàn tất; xem trạng thái bên trên. Không tự ghi đè validator hoặc index.")
    return 0 if successful else 1


if __name__ == "__main__":
    raise SystemExit(main())
