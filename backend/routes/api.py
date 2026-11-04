"""
Mô-đun định nghĩa các API Endpoints
1. tiếp nhận và điều phối các yêu cầu HTTP có tiền tố /api
2. xác thực dữ liệu đầu vào:
- kiểm tra tham số URL (query parameters), chặn tham số lạ, rỗng hoặc bị lặp
- kiểm tra định dạng của các ID qua Regex
3. chuyển tiếp tác vụ với tầng Service:
- TourismService: truy vấn dữ liệu từ mongoDB
- get_image_file: đọc và bảo mật file từ thư mục gốc
4. trả về phản hồi chuẩn hóa (Json hoặc binary image stream kèm HTTP cache)

/api/health: kiểm tra trạng thái hoạt động của be và kết nối mongoDB
/api/provinces : lấy danh mục tỉnh 
/api/tourism-types : lấy danh mục loại hình du lịch
/api/places: lấy danh sách địa điểm
/api/places/<place_id> : lấy chi tiết một địa điểm
/api/images/<image_id> : trả về file ảnh gốc thông qua send_file
"""
import re

from flask import Blueprint, current_app, jsonify, request, send_file
from werkzeug.exceptions import BadRequest, NotFound

from backend.services.images import get_image_file
from backend.services.tourism import TourismService

api = Blueprint("api", __name__, url_prefix="/api")


def database():
    """Lấy đối tượng database MongoDB từ extensions của Flask app đang chạy."""
    return current_app.extensions["mongodb"].get_database()


def query_parameters(allowed):
    """
    Kiểm tra và trích xuất các query parameters từ URL:
    - Chặn tham số không nằm trong danh sách `allowed`.
    - Chặn tham số bị lặp, rỗng hoặc có khoảng trắng đầu/cuối.
    """
    if set(request.args) - set(allowed):
        raise BadRequest("Có tham số không được hỗ trợ.")
    values = {}
    for key in request.args:
        options = request.args.getlist(key)
        if len(options) != 1 or not options[0] or options[0] != options[0].strip():
            raise BadRequest("Tham số không được rỗng, lặp hoặc có khoảng trắng đầu/cuối.")
        values[key] = options[0]
    return values


def valid_id(value, pattern=r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}"):
    """
    Kiểm tra định dạng ID qua Regex, chặn ký tự nguy hiểm (chống Path Traversal).
    Trả về giá trị nguyên bản nếu hợp lệ, ném BadRequest nếu không.
    """
    if re.fullmatch(pattern, value) is None:
        raise BadRequest("Định dạng ID không hợp lệ.")
    return value


@api.get("/health")
def health():
    query_parameters(())
    database().command("ping")
    return jsonify({"status": "ok", "database": "ok"})


@api.get("/provinces")
def provinces():
    values = query_parameters(("scheme",))
    if "scheme" in values and values["scheme"] not in ("former", "current"):
        raise BadRequest("scheme chỉ nhận former hoặc current.")
    return jsonify(TourismService(database()).list_provinces(values.get("scheme")))


@api.get("/tourism-types")
def tourism_types():
    query_parameters(())
    return jsonify(TourismService(database()).list_tourism_types())


@api.get("/places")
def places():
    values = query_parameters(("province_id", "tourism_type_id"))
    if "province_id" in values:
        valid_id(values["province_id"], r"[FC]_[A-Z]{2}")
    if "tourism_type_id" in values:
        valid_id(values["tourism_type_id"], r"TT_[A-Z]+(?:_[A-Z]+)*")
    return jsonify(TourismService(database()).list_places(**values))


@api.get("/places/<place_id>")
def place_detail(place_id):
    query_parameters(())
    valid_id(place_id)
    return jsonify(TourismService(database()).place_detail(place_id))


@api.get("/images/<image_id>")
def image_file(image_id):
    query_parameters(())
    valid_id(image_id)
    path, mimetype = get_image_file(database(), current_app.config["SETTINGS"].data_root, image_id)
    try:
        return send_file(path, mimetype=mimetype, conditional=True)
    except OSError:
        raise NotFound("Không tìm thấy tệp ảnh.") from None
