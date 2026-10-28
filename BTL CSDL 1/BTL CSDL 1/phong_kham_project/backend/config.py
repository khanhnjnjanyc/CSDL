"""Cấu hình ứng dụng, đọc từ biến môi trường (.env)."""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL, make_url

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent  # thư mục gốc dự án
INSECURE_SECRET_KEY = "dev-secret-key"


def _env(name, default=""):
    """Biến môi trường rỗng hoặc chỉ có khoảng trắng được coi như chưa đặt."""
    return os.getenv(name, "").strip() or default


def _csv(name):
    return [item.strip() for item in _env(name).split(",") if item.strip()]


def _build_database_uri():
    """Ưu tiên DATABASE_URL (Cloud) > DB_TYPE=mysql > SQLite mặc định."""
    cloud_url = _env("DATABASE_URL")
    if cloud_url:
        if cloud_url.startswith("mysql://"):
            cloud_url = cloud_url.replace("mysql://", "mysql+pymysql://", 1)
        return cloud_url

    if _env("DB_TYPE", "sqlite").lower() == "mysql":
        # URL.create tự mã hóa ký tự đặc biệt (@ : / ...) trong mật khẩu
        url = URL.create(
            "mysql+pymysql",
            username=_env("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD") or None,
            host=_env("MYSQL_HOST", "127.0.0.1"),
            port=int(_env("MYSQL_PORT", "3306")),
            database=_env("MYSQL_DATABASE", "phong_kham"),
            query={"charset": "utf8mb4"},
        )
        return url.render_as_string(hide_password=False)

    # Đường dẫn tuyệt đối để không phụ thuộc thư mục chạy (gunicorn, cron...)
    sqlite_path = Path(_env("SQLITE_PATH", "phong_kham.db"))
    if not sqlite_path.is_absolute():
        sqlite_path = BASE_DIR / sqlite_path
    url = URL.create("sqlite", database=str(sqlite_path))
    return url.render_as_string(hide_password=False)


_DATABASE_URI = _build_database_uri()
_DB_URL = make_url(_DATABASE_URI)


class Config:
    APP_ENV = _env("APP_ENV", "development").lower()
    IS_PRODUCTION = APP_ENV == "production"
    SECRET_KEY = _env("SECRET_KEY", INSECURE_SECRET_KEY)

    # Vận hành: mặc định an toàn (không debug, chỉ lắng nghe localhost, không mở CORS)
    DEBUG = _env("FLASK_DEBUG", "0") == "1" and not IS_PRODUCTION
    HOST = _env("HOST", "127.0.0.1")
    PORT = int(_env("PORT", "5000"))
    CORS_ORIGINS = _csv("CORS_ORIGINS")  # ví dụ: http://localhost:5173
    # Tự tạo SQLite khi khởi động: bật ở dev, tắt ở production (chạy seed một lần)
    AUTO_INIT_DB = _env("AUTO_INIT_DB", "0" if IS_PRODUCTION else "1") == "1"

    DATABASE_URI = _DATABASE_URI
    # Suy ra từ URI thực tế (sqlite / mysql), không phụ thuộc biến DB_TYPE,
    # để seed_sqlite không chạy nhầm lên MySQL khi chỉ đặt DATABASE_URL.
    DB_TYPE = _DB_URL.get_backend_name()
    SQLITE_PATH = _DB_URL.database if DB_TYPE == "sqlite" else None

    @classmethod
    def get_database_uri(cls):  # giữ để code cũ không bị vỡ
        return cls.DATABASE_URI

    @classmethod
    def validate(cls):
        if cls.IS_PRODUCTION and cls.SECRET_KEY == INSECURE_SECRET_KEY:
            raise RuntimeError("Thiếu SECRET_KEY an toàn cho môi trường production")


Config.validate()