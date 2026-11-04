"""Chuyển đổi dataset offline, kiểm tra schema và kiểm tra ảnh cục bộ.
Đọc file JSON thô (raw_dataset.json) cùng danh mục (provinces, tourism_types),
validate toàn bộ, chuyển đổi sang dạng document MongoDB và kiểm tra file ảnh
thực tế trên ổ đĩa. Dùng chung cho import_dataset.py và validate_data.py.
"""

import copy
import json
import math
import sys
import warnings
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

from bson import BSON
from bson.decimal128 import Decimal128
from bson.errors import InvalidDocument
from jsonschema import Draft4Validator, ValidationError, validators
from PIL import Image

from backend.config import BACKEND_DIR, Settings
from backend.schemas import COLLECTION_SCHEMAS

CATALOG_DIR = BACKEND_DIR / "data"
GROUP_CURRENT_IDS = {
    "Can_Tho": "C_CT", "Vinh_Long": "C_VL",
    "Dong_Thap": "C_DT", "Ca_Mau": "C_CM",
    "An_Giang": "C_AG",
}

def normalize_type_name(value):
    """Chuẩn hóa tên loại hình du lịch: cắt khoảng trắng đầu/cuối và đưa về chữ thường."""
    return value.strip().casefold()

def configure_output():
    """Cấu hình stdout/stderr xuất UTF-8 trên Windows để in tiếng Việt không lỗi."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")

class DatasetError(ValueError):
    """Lỗi dataset - chứa danh sách tất cả lỗi tìm được, dừng import nếu có."""
    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__(f"Dữ liệu có {len(self.errors)} lỗi; không bắt đầu ghi DB.")

def read_json(path: Path):
    """Đọc file JSON an toàn: chặn số không hữu hạn (NaN/Infinity) và khóa trùng."""
    def reject_constant(value):
        raise ValueError(f"JSON chứa số không hữu hạn: {value}")

    def reject_duplicate_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"JSON có khóa trùng: {key!r}")
            result[key] = value
        return result

    try:
        return json.loads(path.read_text(encoding="utf-8-sig"), parse_constant=reject_constant, object_pairs_hook=reject_duplicate_keys)
    except (OSError, ValueError) as error:
        raise DatasetError([f"File {path}: {error}"]) from None

def _bson_type(validator, expected, value, schema):
    """Hàm mở rộng cho jsonschema để kiểm tra từ khóa bsonType ngay ở chế độ offline."""
    # Mở rộng JSON Schema draft 4 với các kiểu BSON được dùng trong bộ schema hiện có.
    # Không viết lại hoặc nhân bản schema của các collection khi kiểm tra offline.
    checks = {
        "object": lambda v: isinstance(v, dict),
        "array": lambda v: isinstance(v, list),
        "string": lambda v: isinstance(v, str),
        "null": lambda v: v is None,
        "int": lambda v: isinstance(v, int) and not isinstance(v, bool) and -(2**31) <= v < 2**31,
        "long": lambda v: isinstance(v, int) and not isinstance(v, bool) and -(2**63) <= v < 2**63,
        "double": lambda v: isinstance(v, float) and math.isfinite(v),
        "decimal": lambda v: isinstance(v, Decimal128) and v.to_decimal().is_finite(),
    }
    types = [expected] if isinstance(expected, str) else expected
    if not any(checks.get(kind, lambda v: False)(value) for kind in types):
        yield ValidationError(f"kiểu BSON không hợp lệ, cần {types}")
    elif isinstance(value, Decimal128):
        # Giới hạn số học mặc định của jsonschema không tự nhận diện được kiểu BSON Decimal128.
        number = value.to_decimal()
        if "minimum" in schema and number < schema["minimum"]:
            yield ValidationError("số BSON decimal nhỏ hơn minimum")
        if "maximum" in schema and number > schema["maximum"]:
            yield ValidationError("số BSON decimal lớn hơn maximum")


BsonValidator = validators.extend(Draft4Validator, {"bsonType": _bson_type})
SCHEMA_VALIDATORS = {name: BsonValidator(schema) for name, schema in COLLECTION_SCHEMAS.items()}


def schema_errors(collection, document):
    """Validate document theo schema collection, kèm kiểm tra kích thước BSON < 16 MiB."""
    for error in SCHEMA_VALIDATORS[collection].iter_errors(document):
        field = ".".join(str(part) for part in error.absolute_path) or "<document>"
        yield f"{collection} ID={document.get('_id')!r} trường {field}: {error.message}"
    if collection == "places":
        try:
            if len(BSON.encode(document)) >= 16 * 1024 * 1024:
                yield f"places ID={document.get('_id')!r}: document phải nhỏ hơn 16 MiB"
        except (InvalidDocument, OverflowError):
            yield f"places ID={document.get('_id')!r}: không thể mã hóa BSON"

def image_reference_errors(places, *, require_cover=False):
    """ID ảnh phải duy nhất cả trong một place và trên toàn bộ places."""
    owners = {}
    for place in places:
        pid = place.get("_id")
        images = place.get("images")
        if not isinstance(images, list):
            continue  # Lỗi sai cấu trúc đã được báo ở hàm schema_errors.
        local_ids = set()
        for image in images:
            if not isinstance(image, dict):
                continue
            iid = image.get("_id")
            if isinstance(iid, str):
                if iid in owners:
                    yield f"place ID={pid!r}: image ID trùng {iid!r}, đã gặp trong place {owners[iid]!r}"
                owners[iid] = pid
                local_ids.add(iid)
            try:
                image_path(image.get("path"))
            except ValueError as error:
                yield f"place ID={pid!r}, image ID={iid!r}: {error}"
        cover = place.get("cover_image_id")
        if cover is None and not require_cover:
            continue
        if not isinstance(cover, str) or cover not in local_ids:
            yield f"place ID={pid!r}: cover_image_id={cover!r} không thuộc images của địa điểm"

def image_path(value):
    """Chuẩn hóa đường dẫn ảnh tương đối dạng images/...; chặn tên ổ đĩa, '..' và URL."""
    if not isinstance(value, str) or not value:
        raise ValueError("đường dẫn ảnh phải là chuỗi không rỗng")
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if (path.is_absolute() or PureWindowsPath(value).drive or ".." in path.parts
            or ":" in normalized or not path.parts or path.parts[0] != "images"):
        raise ValueError("đường dẫn phải nằm trong images/, tương đối với DATA_ROOT")
    return path.as_posix()

def check_image(root, path):
    """Kiểm tra file ảnh tồn tại, nằm trong DATA_ROOT và giải mã pixel thành công."""
    resolved_root = root.resolve()
    resolved = (resolved_root / path).resolve()
    if not resolved.is_relative_to(resolved_root):
        raise ValueError("đường dẫn ảnh thoát khỏi DATA_ROOT (kể cả symlink)")
    if not resolved.is_file():
        raise ValueError(f"không tìm thấy file ảnh tại {resolved}")
    # verify kiểm tra cấu trúc; mở lại và load buộc giải mã pixel thực sự.
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(resolved) as image:
            image.verify()
        with Image.open(resolved) as image:
            for frame in range(getattr(image, "n_frames", 1)):
                image.seek(frame)
                image.load()

@dataclass
class PreparedDataset:
    """Lưu trữ bộ dữ liệu đã chuyển đổi (documents) và thống kê theo nhóm tỉnh (groups)."""
    documents: dict
    groups: dict

    @property
    def counts(self):
        """Tính tổng số bản ghi của từng bảng, tổng số ảnh nhúng và tổng số đoạn mô tả."""
        result = {name: len(rows) for name, rows in self.documents.items()}
        result["images"] = sum(len(p["images"]) for p in self.documents["places"])
        result["description_parts"] = sum(len(p["description_parts"]) for p in self.documents["places"])
        return result

def print_counts(prepared):
    """In thống kê số lượng bản ghi từ file và số địa điểm theo từng nhóm tỉnh."""
    print("Số lượng từ file:")
    for name, count in prepared.counts.items():
        print(f"  {name}: {count}")
    print("Đối chiếu nhóm tỉnh:")
    for group, counts in prepared.groups.items():
        print(f"  {group}: {dict(counts)}")

def prepare_dataset(settings: Settings, *, verify_images=True):
    """
    Đọc danh mục và raw_dataset.json, kiểm tra toàn vẹn, giải mã thử toàn bộ file ảnh
    và chuyển đổi sang cấu trúc document chuẩn của MongoDB.
    """
    errors = []
    documents = {"provinces": read_json(CATALOG_DIR / "provinces.json"),
                 "tourism_types": read_json(CATALOG_DIR / "tourism_types.json"),
                 "places": []}
    for name in ("provinces", "tourism_types"):
        if not isinstance(documents[name], list) or not all(isinstance(row, dict) for row in documents[name]):
            raise DatasetError([f"Danh mục {name} phải là mảng document."])
        for document in documents[name]:
            errors.extend(schema_errors(name, document))
    if errors:
        raise DatasetError(errors)
    provinces = {p["name"]: p for p in documents["provinces"] if p["scheme"] == "former"}
    current = {p["_id"]: p for p in documents["provinces"] if p["scheme"] == "current"}
    types = {normalize_type_name(t["name"]): t["_id"] for t in documents["tourism_types"]}
    former_ids = {p["_id"] for p in provinces.values()}
    mapped_ids = [pid for province in current.values() for pid in province["former_province_ids"]]
    if (len(provinces) != 12 or len(current) != 5 or len(types) != 8
            or len(documents["provinces"]) != 17 or len(documents["tourism_types"]) != 8):
        errors.append("Danh mục phải có 12 tên tỉnh former, 5 tỉnh current và 8 tên loại hình khác nhau.")
    if set(current) != set(GROUP_CURRENT_IDS.values()) or Counter(mapped_ids) != Counter(former_ids):
        errors.append("Ánh xạ tỉnh current phải bao phủ mỗi ID tỉnh former đúng một lần.")
    raw = read_json(settings.dataset_path)
    if not isinstance(raw, dict):
        raise DatasetError(["Dataset phải là object gồm 5 nhóm tỉnh."])
    if set(raw) != set(GROUP_CURRENT_IDS):
        errors.append(f"Nhóm tỉnh không khớp: thiếu {set(GROUP_CURRENT_IDS) - set(raw)}, dư {set(raw) - set(GROUP_CURRENT_IDS)}")
    groups = {}
    checked_paths = {}
    part_ids = []
    for group, rows in raw.items():
        groups[group] = Counter()
        if not isinstance(rows, list):
            errors.append(f"Nhóm {group}: cần mảng địa điểm")
            continue
        for position, row in enumerate(rows, 1):
            label = f"nhóm {group}, vị trí {position}"
            if not isinstance(row, dict):
                errors.append(f"{label}: địa điểm phải là object")
                continue
            pid = row.get("id")
            label = f"place ID={pid!r}, {label}"
            try:
                province_name = row["province"]
                if not isinstance(province_name, str) or province_name not in provinces:
                    raise ValueError(f"tỉnh không có trong danh mục: {province_name!r}")
                province = provinces[province_name]
                groups[group][province_name] += 1
                group_current = current.get(GROUP_CURRENT_IDS.get(group))
                if not group_current or province["_id"] not in group_current["former_province_ids"]:
                    raise ValueError(f"tỉnh {province_name!r} không thuộc nhóm {group}")
                raw_types = row["type"]
                if not isinstance(raw_types, list) or any(not isinstance(t, str) or normalize_type_name(t) not in types for t in raw_types):
                    raise ValueError(f"loại hình không khớp danh mục: {raw_types!r}")
                coordinates = row["coordinates"]
                if not isinstance(coordinates, dict) or set(coordinates) != {"lng", "lat"}:
                    raise ValueError("coordinates phải có đúng lng và lat")
                gallery = row["image_texts"]
                if not isinstance(gallery, list):
                    raise ValueError("image_texts phải là mảng")
                cover_path = image_path(row["cover_image"])
                images = []
                for order, image in enumerate(gallery, 1):
                    if not isinstance(image, dict):
                        errors.append(f"{label}, ảnh vị trí {order}: cần object")
                        continue
                    iid, source_path = image.get("id"), image.get("image")
                    try:
                        path = image_path(source_path)
                        converted = {"_id": iid, "path": path,
                                     "caption": image["text"], "order": order}
                        images.append(converted)
                        if verify_images:
                            if path not in checked_paths:
                                try:
                                    check_image(settings.data_root, path)
                                    checked_paths[path] = None
                                except (OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
                                    checked_paths[path] = str(error)
                            if checked_paths[path]:
                                raise ValueError(checked_paths[path])
                    except (KeyError, ValueError) as error:
                        errors.append(f"{label}, image ID={iid!r}, path={source_path!r}: {error}")
                cover_matches = [image for image in images if image["path"] == cover_path]
                if len(cover_matches) != 1:
                    errors.append(f"{label}, cover path={cover_path!r}: cần đúng một ảnh khớp trong image_texts, thực tế {len(cover_matches)}")
                place = {"_id": pid, "name": row["name"], "other_names": copy.deepcopy(row["other_names"]),
                         "province_former_id": province["_id"],
                         "address": {"former": row["address"], "current": row["address_after"]},
                         "location": {"type": "Point", "coordinates": [coordinates["lng"], coordinates["lat"]]},
                         "tourism_type_ids": [types[normalize_type_name(t)] for t in raw_types],
                         "cover_image_id": cover_matches[0]["_id"] if len(cover_matches) == 1 else None,
                         "description_parts": copy.deepcopy(row["description_parts"]), "images": images}
                documents["places"].append(place)
            except (KeyError, TypeError, ValueError) as error:
                errors.append(f"{label}: {error}")
    for name, rows in documents.items():
        seen = set()
        for document in rows:
            errors.extend(schema_errors(name, document))
            identifier = document.get("_id")
            if isinstance(identifier, str):
                if identifier in seen:
                    errors.append(f"{name}: ID trùng {identifier!r}")
                seen.add(identifier)
            if name == "places" and isinstance(document.get("description_parts"), list):
                orders = []
                for part in document["description_parts"]:
                    if isinstance(part, dict):
                        if isinstance(part.get("id"), str):
                            part_ids.append(part["id"])
                        if isinstance(part.get("order"), int):
                            orders.append(part["order"])
                if len(orders) != len(set(orders)):
                    errors.append(f"places ID={identifier!r}: description_parts có order trùng")
    errors.extend(image_reference_errors(documents["places"], require_cover=True))
    for identifier, count in Counter(part_ids).items():
        if count > 1:
            errors.append(f"description_parts: ID trùng {identifier!r} ({count} lần)")
    if errors:
        raise DatasetError(errors)
    return PreparedDataset(documents, groups)