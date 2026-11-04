"""
Tầng nghiệp vụ (Service Layer) xử lý dữ liệu du lịch:
đọc danh mục tỉnh/thành, loại hình du lịch và địa điểm từ MongoDB,
ghép các tham chiếu chéo và chuyển đổi sang định dạng JSON cho API response.
Chỉ đọc, không chỉnh sửa dữ liệu đã lưu.
"""
from urllib.parse import quote

from bson.decimal128 import Decimal128
from werkzeug.exceptions import NotFound

PLACE_FIELDS = {
    "name": 1, "province_former_id": 1, "address": 1, "location": 1,
    "tourism_type_ids": 1, "cover_image_id": 1, "images._id": 1,
}


class DataIntegrityError(RuntimeError):
    pass


def image_url(identifier):
    """Tạo URL tương đối tới API trả ảnh: /api/images/<image_id>."""
    return f"/api/images/{quote(identifier, safe='')}"


def identity(document):
    """Trích xuất cặp {id, name} từ một document MongoDB."""
    return {"id": document["_id"], "name": document["name"]}


def number(value):
    """Chuyển giá trị Decimal128 hoặc số MongoDB sang float Python."""
    return float(value.to_decimal() if isinstance(value, Decimal128) else value)


class TourismService:
    """Dịch vụ truy vấn và chuyển đổi dữ liệu du lịch từ MongoDB sang JSON API."""
    def __init__(self, database):
        self.database = database

    def list_provinces(self, scheme=None):
        """Lấy danh sách tỉnh/thành, có thể lọc theo scheme ('former' hoặc 'current')."""
        query = {"scheme": scheme} if scheme is not None else {}
        items = []
        for row in self.database.provinces.find(query).sort("_id", 1):
            item = {**identity(row), "scheme": row["scheme"]}
            if row["scheme"] == "current":
                item["former_province_ids"] = row["former_province_ids"]
            items.append(item)
        return {"items": items, "total": len(items)}

    def list_tourism_types(self):
        """Lấy danh sách 8 loại hình du lịch đặc trưng Tây Nam Bộ."""
        items = [identity(row) for row in self.database.tourism_types.find({}).sort("_id", 1)]
        return {"items": items, "total": len(items)}

    def _catalogs(self):
        """Nạp toàn bộ danh mục tỉnh và loại hình, xây dựng bản đồ ánh xạ tỉnh cũ → tỉnh hiện tại."""
        provinces = {row["_id"]: row for row in self.database.provinces.find({})}
        types = {row["_id"]: row for row in self.database.tourism_types.find({})}
        current_by_former = {}
        for province in provinces.values():
            if province["scheme"] == "current":
                for former_id in province["former_province_ids"]:
                    if former_id in current_by_former:
                        raise DataIntegrityError("Ambiguous current province mapping")
                    current_by_former[former_id] = province
        return provinces, types, current_by_former

    def _place_item(self, place, catalogs):
        """Chuyển đổi một document địa điểm từ MongoDB sang định dạng JSON chuẩn cho API."""
        provinces, types, current_by_former = catalogs
        try:
            former = provinces[place["province_former_id"]]
            current = current_by_former[former["_id"]]
            if former["scheme"] != "former":
                raise KeyError("former scheme")
            cover_id = place["cover_image_id"]
            cover = None
            if cover_id is not None:
                matches = [image for image in place["images"] if image["_id"] == cover_id]
                if len(matches) != 1:
                    raise KeyError("cover missing or duplicated")
                cover = {"id": cover_id, "url": image_url(cover_id)}
            lng, lat = place["location"]["coordinates"]
            return {
                "id": place["_id"], "name": place["name"],
                "province_former": identity(former), "province_current": identity(current),
                "address": {"former": place["address"]["former"], "current": place["address"]["current"]},
                "location": {"lat": number(lat), "lng": number(lng)},
                "tourism_types": [identity(types[identifier]) for identifier in place["tourism_type_ids"]],
                "cover_image": cover,
            }
        except (KeyError, TypeError, ValueError) as error:
            raise DataIntegrityError("Invalid place reference or structure") from error

    def list_places(self, province_id=None, tourism_type_id=None):
        """Lấy danh sách địa điểm, hỗ trợ lọc theo tỉnh và/hoặc loại hình du lịch."""
        catalogs = self._catalogs()
        provinces, types, _ = catalogs
        query = {}
        if province_id is not None:
            province = provinces.get(province_id)
            if province is None:
                raise NotFound("Không tìm thấy tỉnh/thành.")
            query["province_former_id"] = (
                {"$in": province["former_province_ids"]} if province["scheme"] == "current" else province_id
            )
        if tourism_type_id is not None:
            if tourism_type_id not in types:
                raise NotFound("Không tìm thấy loại hình du lịch.")
            query["tourism_type_ids"] = tourism_type_id
        places = list(self.database.places.find(query, PLACE_FIELDS).sort("_id", 1))
        items = [self._place_item(place, catalogs) for place in places]
        return {"items": items, "total": len(items)}

    def place_detail(self, place_id):
        """Lấy thông tin chi tiết một địa điểm: gallery ảnh, mô tả, tọa độ, địa chỉ."""
        place = self.database.places.find_one({"_id": place_id}, {"images.path": 0})
        if place is None:
            raise NotFound("Không tìm thấy địa điểm.")
        gallery = sorted(place["images"], key=lambda image: (image["order"], image["_id"]))
        item = self._place_item(place, self._catalogs())
        item["other_names"] = place["other_names"]
        item["description_parts"] = sorted(place["description_parts"], key=lambda part: (part["order"], part["id"]))
        item["images"] = [{"id": image["_id"], "url": image_url(image["_id"]),
                           "caption": image["caption"], "order": image["order"]} for image in gallery]
        return item
