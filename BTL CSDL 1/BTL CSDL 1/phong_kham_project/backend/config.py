"""Cấu hình ứng dụng, đọc từ biến môi trường (.env)."""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL, make_url

# ----------------------------------------------------------------------
# 1️⃣ Đặt đường dẫn gốc dự án và load .env (override=True để đảm bảo giá trị
#    trong .env luôn thắng các biến môi trường hệ thống khi khởi chạy)
# ----------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent  # thư mục gốc dự án
# Load .env ngay trong thư mục gốc – nếu đã có biến môi trường sẽ được
# ghi đè lại bởi giá trị trong .env (đặc biệt quan trọng cho MYSQL_PASSWORD)
load_dotenv(BASE_DIR / ".env", override=True)

# ----------------------------------------------------------------------
# 2️⃣ Hằng số an toàn (được dùng khi chưa thiết lập SECRET_KEY)
# ----------------------------------------------------------------------
INSECURE_SECRET_KEY = "dev-secret-key"

# ----------------------------------------------------------------------
# 3️⃣ Helper để lấy biến môi trường (bỏ qua chuỗi rỗng hoặc chỉ khoảng trắng)
# ----------------------------------------------------------------------
def _env(name: str, default: str = "") -> str:
    """Trả về giá trị biến môi trường, hoặc default nếu rỗng/whitespace."""
    return os.getenv(name, "").strip() or default


def _csv(name: str) -> list[str]:
    """Chuyển chuỗi CSV thành list, loại bỏ phần tử rỗng."""
    return [item.strip() for item in _env(name).split(",") if item.strip()]


# ----------------------------------------------------------------------
# 4️⃣ Xây dựng DATABASE_URI
# ----------------------------------------------------------------------
def _build_database_uri() -> str:
    """
    Thứ tự ưu tiên:
        1️⃣ DATABASE_URL (đối với Cloud, thường có dạng mysql://…)
        2️⃣ DB_TYPE=mysql → xây dựng URI từ các biến MYSQL_*
        3️⃣ Mặc định SQLite
    """
    # 1️⃣ DATABASE_URL (nếu có)
    cloud_url = _env("DATABASE_URL")
    if cloud_url:
        # Đảm bảo driver pymysql được dùng cho MySQL
        if cloud_url.startswith("mysql://"):
            cloud_url = cloud_url.replace("mysql://", "mysql+pymysql://", 1)
        return cloud_url

    # 2️⃣ MySQL thông qua các biến riêng
    if _env("DB_TYPE", "sqlite").lower() == "mysql":
        # URL.create sẽ tự mã hoá các ký tự đặc biệt trong password
        url = URL.create(
            drivername="mysql+pymysql",
            username=_env("MYSQL_USER", "root"),
            password=_env("MYSQL_PASSWORD", ""),      # dùng _env để strip
            host=_env("MYSQL_HOST", "127.0.0.1"),
            port=int(_env("MYSQL_PORT", "3306")),
            database=_env("MYSQL_DATABASE", "phong_kham"),
            query={"charset": "utf8mb4"},
        )
        # hide_password=False để dễ debug (không ảnh hưởng tới security)
        return url.render_as_string(hide_password=False)

    # 3️⃣ SQLite (fallback)
    sqlite_path = Path(_env("SQLITE_PATH", "medcare.db"))
    if not sqlite_path.is_absolute():
        sqlite_path = BASE_DIR / sqlite_path
    url = URL.create("sqlite", database=str(sqlite_path))
    return url.render_as_string(hide_password=False)


# ----------------------------------------------------------------------
# 5️⃣ Tạo các cấu hình tĩnh dùng cho toàn bộ ứng dụng
# ----------------------------------------------------------------------
_DATABASE_URI = _build_database_uri()
_DB_URL = make_url(_DATABASE_URI)


class Config:
    # ------------------- Ứng dụng chung -------------------
    APP_ENV: str = _env("APP_ENV", "development").lower()
    IS_PRODUCTION: bool = APP_ENV == "production"
    SECRET_KEY: str = _env("SECRET_KEY", INSECURE_SECRET_KEY)

    DEBUG: bool = _env(
        "FLASK_DEBUG", "1" if not IS_PRODUCTION else "0"
    ) == "1"
    HOST: str = _env("HOST", "127.0.0.1")
    PORT: int = int(_env("PORT", "5000"))
    CORS_ORIGINS: list[str] = _csv("CORS_ORIGINS")

    # ------------------- MySQL riêng -------------------------------------------------
    MYSQL_HOST: str = _env("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT: int = int(_env("MYSQL_PORT", "3306"))
    MYSQL_USER: str = _env("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = _env("MYSQL_PASSWORD", "")   # luôn qua _env
    MYSQL_DATABASE: str = _env("MYSQL_DATABASE", "phong_kham")

    # ------------------- SQLite (chỉ dùng khi DB_TYPE == "sqlite") -----------------------
    AUTO_INIT_DB: bool = _env(
        "AUTO_INIT_DB", "0" if IS_PRODUCTION else "1"
    ) == "1"

    # ------------------- Các thông tin đã tính toán ---------------------------------
    DATABASE_URI: str = _DATABASE_URI
    DB_TYPE: str = _DB_URL.get_backend_name()          # "mysql" hoặc "sqlite"
    SQLITE_PATH: str | None = _DB_URL.database if DB_TYPE == "sqlite" else None

    @classmethod
    def get_database_uri(cls) -> str:
        """Return the full SQLAlchemy URL (used by SQLAlchemy engine)."""
        return cls.DATABASE_URI

    @classmethod
    def validate(cls) -> None:
        """Kiểm tra các yêu cầu bảo mật trong môi trường production."""
        if cls.IS_PRODUCTION and cls.SECRET_KEY == INSECURE_SECRET_KEY:
            raise RuntimeError(
                "Thiếu SECRET_KEY an toàn cho môi trường production"
            )


# Kiểm tra ngay khi import module
Config.validate()