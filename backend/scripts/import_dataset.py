"""
kiểm tra và nạp dữ liệu từ raw_dataset vào db
    1. Kiểm tra tính hợp lệ của file JSON thô và giải mã thử từng file ảnh bằng Pillow.
    2. Pre-flight check: Kiểm tra DB (cảnh báo nếu còn collection images cũ, kiểm tra schema).
    3. Gộp ảnh thông minh: Giữ nguyên thứ tự gallery (`order`) và ảnh bìa (`cover_image_id`).
    4. Upsert an toàn bằng MongoDB Pipeline, có thể chạy lại nhiều lần mà không mất dữ liệu.
"""

import argparse
import sys

from pymongo.errors import PyMongoError

from backend.config import ConfigurationError, load_settings
from backend.database import DatabaseConnectionError, connect_database, describe_mongo_error
from backend.dataset import (
    DatasetError, configure_output, image_reference_errors, prepare_dataset, print_counts, schema_errors,
)
from backend.schemas import COLLECTION_SCHEMAS
from backend.scripts.init_db import validator_matches

INSERT_ONLY_FIELDS = {"places": {"cover_image_id"}}


def merged_images(incoming, existing):
    """
    Hợp nhất danh sách ảnh nguồn (incoming) với ảnh đang có trong DB (existing):
    giữ nguyên thứ tự sắp xếp (`order`) của các ảnh đã có và bổ sung các ảnh mới.
    Dùng để mô phỏng và kiểm tra schema ở bước preflight.
    """
    previous = {image["_id"]: image for image in existing}
    ids = {image["_id"] for image in incoming}
    return [dict(image, order=previous.get(image["_id"], image)["order"]) for image in incoming] + [
        image for image in existing if image["_id"] not in ids
    ]

def preflight_database(database, prepared):
    """
    Kiểm tra chỉ đọc (Read-only) trạng thái MongoDB trước khi nạp:
    - Đảm bảo các collection đích đã tồn tại và đúng chuẩn JSON Schema từ init_db.
    - Kiểm tra ID danh mục provinces/tourism_types không bị dính mã cũ.
    - Xác thực tính hợp lệ của ảnh bìa (`cover_image_id`) và mảng ảnh nhúng trong `places`.
    """
    errors = []
    for name, schema in COLLECTION_SCHEMAS.items():
        metadata = next(database.list_collections(filter={"name": name}), None)
        if metadata is None or metadata.get("type") != "collection":
            errors.append(f"{name}: chưa có collection thông thường; chạy python -m backend.scripts.init_db trước")
        elif not validator_matches(metadata.get("options", {}), schema):
            errors.append(f"{name}: validator khác schema hiện tại; giữ nguyên, không bắt đầu import")
    if errors:
        raise DatasetError(errors)
    for name in ("provinces", "tourism_types"):
        allowed_ids = [document["_id"] for document in prepared.documents[name]]
        unexpected = [document["_id"] for document in database[name].find({"_id": {"$nin": allowed_ids}}, {"_id": 1})]
        if unexpected:
            errors.append(f"{name}: phát hiện ID danh mục không khớp với dữ liệu chuẩn {unexpected!r}")
    if errors:
        raise DatasetError(errors)
    existing = list(database.places.find({}))
    for place in existing:
        errors.extend(schema_errors("places", place))
    errors.extend(image_reference_errors(existing))
    if errors:
        raise DatasetError(errors)
    by_id = {place["_id"]: place for place in existing}
    prospective = dict(by_id)
    for place in prepared.documents["places"]:
        previous = by_id.get(place["_id"])
        merged = dict(place)
        if previous is not None:
            merged["cover_image_id"] = previous["cover_image_id"]
            merged["images"] = merged_images(place["images"], previous["images"])
        prospective[place["_id"]] = merged
        errors.extend(schema_errors("places", merged))
    errors.extend(image_reference_errors(prospective.values()))
    if errors:
        raise DatasetError(errors)


def upsert_update(collection, document):
    """
    Xây dựng câu lệnh cập nhật an toàn (Upsert Pipeline) cho MongoDB:
    - Với `places`: Dùng Aggregation Update Pipeline để gộp mảng `images` trực tiếp
      trên MongoDB server, bảo toàn số thứ tự `order` và `cover_image_id` đã có.
    - Với các bảng khác: Dùng `$set` và `$setOnInsert` thông thường.
    """
    if collection == "places":
        incoming = document["images"]
        incoming_ids = [image["_id"] for image in incoming]
        images = {"$let": {
            "vars": {"existing": {"$ifNull": ["$images", []]}},
            "in": {"$concatArrays": [
                {"$map": {
                    "input": {"$literal": incoming}, "as": "image",
                    "in": {"$let": {
                        "vars": {"old": {"$arrayElemAt": [{"$filter": {
                            "input": "$$existing", "as": "old",
                            "cond": {"$eq": ["$$old._id", "$$image._id"]},
                        }}, 0]}},
                        "in": {"$mergeObjects": ["$$image", {
                            "order": {"$ifNull": ["$$old.order", "$$image.order"]},
                        }]},
                    }},
                }},
                {"$filter": {
                    "input": "$$existing", "as": "old",
                    "cond": {"$not": [{"$in": ["$$old._id", {"$literal": incoming_ids}]}]},
                }},
            ]},
        }}
        fields = {key: {"$literal": value} for key, value in document.items()
                  if key not in ("_id", "images", "cover_image_id")}
        fields["images"] = images
        fields["cover_image_id"] = {"$cond": [
            {"$eq": [{"$type": "$cover_image_id"}, "missing"]},
            {"$literal": document["cover_image_id"]}, "$cover_image_id",
        ]}
        return [{"$set": fields}]
    insert_only = INSERT_ONLY_FIELDS.get(collection, set())
    update = {"$set": {key: value for key, value in document.items() if key != "_id" and key not in insert_only}}
    if insert_only:
        update["$setOnInsert"] = {key: document[key] for key in insert_only}
    return update


def import_documents(database, prepared):
    """
    Thực hiện nạp từng document theo lô (Atomic Upsert):
    ghi nhận số lượng document mới, khớp và thay đổi. Nếu bị ngắt kết nối giữa chừng,
    chỉ cần chạy lại cùng câu lệnh để tiếp tục mà không lo trùng lặp hay mất dữ liệu.
    """
    reports = {}
    for name, documents in prepared.documents.items():
        stats = {"inserted": 0, "matched": 0, "modified": 0}
        reports[name] = stats
        for document in documents:
            try:
                result = database[name].update_one({"_id": document["_id"]}, upsert_update(name, document), upsert=True)
            except PyMongoError as error:
                print(f"Dừng tại {name} ID={document['_id']!r}, path={document.get('path')!r}: {describe_mongo_error(error)}", file=sys.stderr)
                print("Một phần dữ liệu có thể đã ghi, kể cả thao tác vừa lỗi nếu mất kết nối. Không rollback/xóa dữ liệu; chạy lại cùng lệnh để tiếp tục an toàn.", file=sys.stderr)
                print_reports(reports)
                return False
            stats["inserted"] += int(result.upserted_id is not None)
            stats["matched"] += result.matched_count
            stats["modified"] += result.modified_count
        print(f"Đã xử lý {name}: {len(documents)} document.")
    print_reports(reports)
    return True


def print_reports(reports):
    """In bảng tổng kết số document mới, khớp và thay đổi cho từng collection."""
    for name, stats in reports.items():
        print(f"  {name}: mới={stats['inserted']}, khớp={stats['matched']}, thay đổi={stats['modified']}")


def main(argv=None):
    """
    Điểm khởi chạy từ dòng lệnh:
    hỗ trợ cờ `--dry-run` để kiểm tra toàn diện dataset offline,
    hoặc kết nối MongoDB để thực hiện nạp dữ liệu hoàn chỉnh.
    """
    configure_output()
    parser = argparse.ArgumentParser(description="Kiểm tra dataset và upsert MongoDB; giữ nguyên gallery order/cover đã có.")
    parser.add_argument("--dry-run", action="store_true", help="Kiểm tra toàn bộ dataset/ảnh, không kết nối hoặc ghi DB")
    args = parser.parse_args(argv)
    client = None
    try:
        settings = load_settings()
        print(f"Đọc dataset: {settings.dataset_path}")
        print(f"DATA_ROOT: {settings.data_root}")
        prepared = prepare_dataset(settings)
        print_counts(prepared)
        print("Dataset hợp lệ: schema, ID, danh mục, nhóm tỉnh, tọa độ, ảnh bìa và giải mã toàn bộ ảnh.")
        if args.dry_run:
            print("DRY-RUN hoàn tất; không kết nối và không ghi DB.")
            return 0
        client, database = connect_database(settings)
        print(f"MongoDB ping thành công; database: {settings.mongodb_database}")
        preflight_database(database, prepared)
        if not import_documents(database, prepared):
            return 1
        print("Import hoàn tất. Tiếp tục chạy python -m backend.scripts.validate_data để kiểm tra dữ liệu trong DB.")
        return 0
    except DatasetError as error:
        print(str(error), file=sys.stderr)
        for message in error.errors:
            print(f"  Lỗi: {message}", file=sys.stderr)
        return 1
    except (ConfigurationError, DatabaseConnectionError) as error:
        print(f"Lỗi: {error}; chưa bắt đầu ghi dữ liệu.", file=sys.stderr)
        return 1
    except PyMongoError as error:
        print(f"Lỗi kiểm tra DB: {describe_mongo_error(error)}; chưa bắt đầu ghi dữ liệu.", file=sys.stderr)
        return 1
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
