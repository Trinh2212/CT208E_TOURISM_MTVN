"""Application Factory tạo Flask app. Chạy: python -m flask --app backend.app run."""

import atexit

from flask import Flask, jsonify
from pymongo.errors import PyMongoError
from werkzeug.exceptions import HTTPException

from backend.config import load_settings
from backend.database import DatabaseConnectionError, MongoConnection
from backend.routes.api import api
from backend.services.tourism import DataIntegrityError


def create_app(settings=None, *, database=None):
    """Tạo và cấu hình Flask app.

    Nạp cấu hình, khởi tạo kết nối MongoDB lazy, đăng ký blueprint API
    và các error handler trả JSON thống nhất. Tham số ``settings`` và
    ``database`` cho phép test truyền mock thay vì kết nối thật.
    """
    app = Flask(__name__, static_folder=None)
    app.json.ensure_ascii = False
    app.config["SETTINGS"] = settings if settings is not None else load_settings()
    connection = MongoConnection(app.config["SETTINGS"], database=database)
    app.extensions["mongodb"] = connection
    atexit.register(connection.close)
    app.register_blueprint(api)

    @app.errorhandler(DatabaseConnectionError)
    @app.errorhandler(PyMongoError)
    def mongo_unavailable(error):
        return jsonify({"error": {"code": "database_unavailable", "message": "MongoDB hiện không khả dụng. Vui lòng thử lại sau."}}), 503

    @app.errorhandler(HTTPException)
    def http_error(error):
        response = error.get_response()
        codes = {400: "bad_request", 404: "not_found", 405: "method_not_allowed"}
        response.set_data(app.json.dumps({"error": {"code": codes.get(error.code, "http_error"), "message": error.description}}))
        response.content_type = "application/json"
        return response

    @app.errorhandler(DataIntegrityError)
    @app.errorhandler(Exception)
    def internal_error(error):
        # Không ghi URI/exception driver vào log, không lộ đường dẫn nội bộ cho client.
        app.logger.error("API failed (%s)", type(error).__name__)
        return jsonify({"error": {"code": "internal_error", "message": "Không thể xử lý dữ liệu lúc này."}}), 500

    return app
