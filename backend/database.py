"""Tạo và kiểm tra (ping) PyMongo client mà không lộ credential trong thông báo lỗi."""

from threading import Lock

from pymongo import MongoClient
from pymongo.errors import (
    ConfigurationError as PyMongoConfigurationError,
    ConnectionFailure,
    InvalidName,
    OperationFailure,
    PyMongoError,
)

from backend.config import Settings


class DatabaseConnectionError(RuntimeError):
    """Lỗi kết nối MongoDB - message đã được viết lại an toàn, không chứa URI."""
    pass


def describe_mongo_error(error: PyMongoError) -> str:
    """Phân loại lỗi PyMongo và trả về thông báo tiếng Việt an toàn.
    Không bao giờ chuyển đổi exception gốc thành chuỗi vì driver message
    có thể chứa MongoDB URI (bao gồm mật khẩu).
    """
    # Không stringify exception gốc: message driver có thể chứa URI.
    if isinstance(error, ConnectionFailure):
        return (
            "Không kết nối được MongoDB trong thời gian chờ. Kiểm tra dịch vụ mongod, "
            "host/port trong backend/.env, mạng và cấu hình TLS."
        )
    if isinstance(error, (PyMongoConfigurationError, InvalidName)):
        return "Cấu hình MongoDB không hợp lệ. Kiểm tra URI, tên database và DNS trong backend/.env."
    if isinstance(error, OperationFailure):
        if error.code == 18:
            return "Xác thực MongoDB thất bại. Kiểm tra tài khoản, mật khẩu và authSource trong backend/.env."
        if error.code == 13:
            return "Tài khoản MongoDB thiếu quyền đọc metadata hoặc tạo collection/index trên database đã cấu hình."
        return f"MongoDB từ chối thao tác (mã {error.code}); không tự sửa hoặc xóa dữ liệu hiện có."
    return "Thao tác MongoDB thất bại; kiểm tra dịch vụ và cấu hình backend/.env."


def connect_database(settings: Settings):
    """Tạo MongoClient, ping server và trả về ``(client, database)``.

    Nếu kết nối thất bại, đóng client (nếu đã tạo) rồi raise
    ``DatabaseConnectionError`` với message an toàn. Caller phải tự close client.
    """
    client = None
    try:
        client = MongoClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=settings.mongodb_timeout_ms,
            connectTimeoutMS=settings.mongodb_timeout_ms,
            socketTimeoutMS=settings.mongodb_timeout_ms,
            timeoutMS=settings.mongodb_timeout_ms,
            appname="tourism-search-backend",
        )
        database = client[settings.mongodb_database]
        client.admin.command("ping")
        return client, database
    except (PyMongoError, ValueError) as error:
        if client is not None:
            client.close()
        message = describe_mongo_error(error) if isinstance(error, PyMongoError) else "Cấu hình kết nối MongoDB không hợp lệ."
        raise DatabaseConnectionError(message) from None


class MongoConnection:
    """Connection pool lazy cho Flask app, giữ kết nối xuyên suốt các request.
    Sử dụng double-checked locking đảm bảo thread-safe: nhiều request
    đồng thời chỉ tạo đúng một kết nối duy nhất.
    """

    def __init__(self, settings: Settings, database=None):
        self.settings = settings
        self._client = None
        self._database = database
        self._lock = Lock()

    def get_database(self):
        """Trả về đối tượng database, tạo kết nối lần đầu nếu chưa có."""
        if self._database is None:
            with self._lock:
                if self._database is None:
                    self._client, self._database = connect_database(self.settings)
        return self._database

    def close(self):
        """Đóng client và giải phóng kết nối (thread-safe)."""
        with self._lock:
            if self._client is not None:
                self._client.close()
                self._client = None
                self._database = None
