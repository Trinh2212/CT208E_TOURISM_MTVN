"""
kiểm tra tính toán vẹn dữ liệu
- chỉ đọc, không chỉnh sửa và xóa
- đối chiếu số lượng và nội dung trong raw_dataset và database mongodb
- kiểm tra tính toàn vẹn tham chiếu chéo
+ tỉnh sáp nhập --> tỉnh cũ (former)
+ địa điểm --> tỉnh cũ và danh mục loại hình
+ địa điểm --> ảnh bìa
+ kiểm tra ID ảnh nhúng duy nhất, ảnh bìa thuộc chính địa điểm
+ chống trùng lặp ID và thứ tự hiện hiện của description_part
"""

import sys

from pymongo.errors import PyMongoError

from backend.config import ConfigurationError, load_settings
from backend.database import DatabaseConnectionError, connect_database, describe_mongo_error
from backend.dataset import (
    DatasetError, configure_output, image_reference_errors, prepare_dataset, print_counts, schema_errors,
)
from backend.scripts.import_dataset import INSERT_ONLY_FIELDS


def validate_database(database, prepared):
    """
    Kiểm tra toàn diện tính toàn vẹn dữ liệu trong MongoDB so với dataset nguồn:
    - Đếm và đối chiếu số lượng document trong từng collection.
    - Kiểm tra schema từng document đã lưu.
    - So khớp từng trường dữ liệu (cho phép lệch cover_image_id và images.order).
    - Kiểm tra tham chiếu chéo: tỉnh sáp nhập, địa điểm, ảnh bìa, ảnh nhúng, description_parts.
    Trả về danh sách lỗi (list rỗng nếu hợp lệ hoàn toàn).
    """
    errors = []
    actual = {}
    all_extras = {}
    customizations = {"cover_image_id": 0, "images.order": 0}
    collection_names = set(database.list_collection_names())
    for name, expected_documents in prepared.documents.items():
        if name not in collection_names:
            errors.append(f"Collection {name} chưa tồn tại")
        rows = list(database[name].find({}))
        actual[name] = {row["_id"]: row for row in rows}
        expected = {row["_id"]: row for row in expected_documents}
        missing = set(expected) - set(actual[name])
        extras = set(actual[name]) - set(expected)
        all_extras[name] = extras
        if name in ("provinces", "tourism_types") and extras:
            errors.append(f"{name}: phát hiện ID danh mục lạ ngoài thiết kế {sorted(extras, key=str)!r}")
        print(f"  {name}: dataset={len(expected)}, DB={len(rows)}, khớp ID={len(set(expected) & set(actual[name]))}, thiếu={len(missing)}, dư={len(extras)}")
        for identifier in sorted(missing, key=str):
            errors.append(f"{name}: thiếu ID={identifier!r}")
        for row in rows:
            errors.extend(schema_errors(name, row))
        for identifier in set(expected) & set(actual[name]):
            source, target = expected[identifier], actual[name][identifier]
            for field, value in source.items():
                if name == "places" and field == "images":
                    target_images = target.get("images", [])
                    if not isinstance(target_images, list):
                        continue  # Sẽ được báo bởi schema_errors.
                    by_id = {image.get("_id"): image for image in target_images
                             if isinstance(image, dict) and isinstance(image.get("_id"), str)}
                    expected_ids = {image["_id"] for image in value}
                    extras = set(by_id) - expected_ids
                    if extras:
                        print(f"  place ID={identifier!r}: ảnh dư ngoài dataset {sorted(extras)!r}")
                    for image in value:
                        stored = by_id.get(image["_id"])
                        if stored is None:
                            errors.append(f"place ID={identifier!r}: thiếu image ID={image['_id']!r}")
                            continue
                        for key, expected_value in image.items():
                            if stored.get(key) != expected_value:
                                if key == "order":
                                    customizations["images.order"] += 1
                                else:
                                    errors.append(f"image ID={image['_id']!r}: trường {key} khác dataset")
                    continue
                if target.get(field) != value:
                    if field in INSERT_ONLY_FIELDS.get(name, set()):
                        customizations[field] += 1
                    else:
                        errors.append(f"{name} ID={identifier!r}: trường {field} khác dataset")
    print("Bản ghi dư ngoài dataset (chỉ báo cáo, không xóa):")
    for name, extras in all_extras.items():
        print(f"  {name}: {sorted(extras, key=str) if extras else 'không có'}")
    provinces, types, places = (actual[name] for name in ("provinces", "tourism_types", "places"))
    errors.extend(image_reference_errors(places.values(), require_cover=True))
    for province in provinces.values():
        if province.get("scheme") == "current":
            refs = province.get("former_province_ids", [])
            if isinstance(refs, list):
                for ref in refs:
                    target = provinces.get(ref) if isinstance(ref, str) else None
                    if target is None or target.get("scheme") != "former":
                        errors.append(f"province ID={province['_id']!r}: former_province_ids chứa tham chiếu sai {ref!r}")
    part_ids = set()
    dataset_part_count = 0
    total_part_count = 0
    expected_place_ids = {place["_id"] for place in prepared.documents["places"]}
    for place in places.values():
        identifier = place["_id"]
        ref = place.get("province_former_id")
        province = provinces.get(ref) if isinstance(ref, str) else None
        if province is None or province.get("scheme") != "former":
            errors.append(f"place ID={identifier!r}: province_former_id sai {ref!r}")
        refs = place.get("tourism_type_ids", [])
        if isinstance(refs, list):
            for ref in refs:
                if not isinstance(ref, str) or ref not in types:
                    errors.append(f"place ID={identifier!r}: tourism_type_id không tồn tại {ref!r}")
        parts = place.get("description_parts", [])
        if isinstance(parts, list):
            total_part_count += len(parts)
            if identifier in expected_place_ids:
                dataset_part_count += len(parts)
            orders = []
            for part in parts:
                if not isinstance(part, dict):
                    continue
                part_id = part.get("id")
                if isinstance(part_id, str):
                    if part_id in part_ids:
                        errors.append(f"place ID={identifier!r}: ID đoạn mô tả trùng {part_id!r}")
                    part_ids.add(part_id)
                if isinstance(part.get("order"), int):
                    orders.append(part["order"])
            if len(orders) != len(set(orders)):
                errors.append(f"place ID={identifier!r}: order đoạn mô tả bị trùng")
    total_images = sum(len(p["images"]) for p in places.values() if isinstance(p.get("images"), list))
    print(f"  images nhúng: dataset={prepared.counts['images']}, toàn DB={total_images}")
    expected_parts = prepared.counts["description_parts"]
    print(f"  description_parts: dataset={expected_parts}, DB trong địa điểm dataset={dataset_part_count}, toàn DB={total_part_count}")
    if dataset_part_count != expected_parts:
        errors.append("Số lượng description_parts trong địa điểm dataset không khớp")
    print(f"Khác biệt được phép so với raw: cover_image_id={customizations['cover_image_id']}, images.order={customizations['images.order']}")
    return errors


def main():
    """
    Điểm khởi chạy từ dòng lệnh: đọc dataset, kết nối MongoDB,
    chạy validate_database và in báo cáo kết quả ra console.
    """
    configure_output()
    client = None
    try:
        settings = load_settings()
        prepared = prepare_dataset(settings)
        print_counts(prepared)
        client, database = connect_database(settings)
        print(f"MongoDB ping thành công; database: {settings.mongodb_database}")
        errors = validate_database(database, prepared)
        if errors:
            print(f"Validation thất bại: {len(errors)} lỗi.", file=sys.stderr)
            for error in errors:
                print(f"  Lỗi: {error}", file=sys.stderr)
            return 1
        print("Validation thành công: số lượng trong phạm vi dataset, nội dung và mọi tham chiếu hợp lệ. Không ghi DB.")
        return 0
    except DatasetError as error:
        print(str(error), file=sys.stderr)
        for message in error.errors:
            print(f"  Lỗi: {message}", file=sys.stderr)
        return 1
    except (ConfigurationError, DatabaseConnectionError) as error:
        print(f"Lỗi: {error}; chưa hoàn tất validation.", file=sys.stderr)
        return 1
    except PyMongoError as error:
        print(f"Lỗi: {describe_mongo_error(error)}; chưa hoàn tất validation.", file=sys.stderr)
        return 1
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
