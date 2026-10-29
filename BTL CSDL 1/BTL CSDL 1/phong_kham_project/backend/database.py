"""Kết nối CSDL, Transaction và dịch lỗi nghiệp vụ R1–R8 dùng chung cho toàn bộ Backend."""
import logging
import re
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import create_engine, event

from backend.config import Config

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Kết nối cơ sở dữ liệu (SQLite và MySQL)
# --------------------------------------------------------------------------
def get_db_connection():
    """
    Mở kết nối CSDL theo DB_TYPE.
    SQLite: bắt buộc bật foreign keys và đặt row_factory = sqlite3.Row.
    MySQL: dùng pymysql với DictCursor.
    """
    if Config.DB_TYPE == "sqlite":
        conn = sqlite3.connect(Config.SQLITE_PATH)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.row_factory = sqlite3.Row
        return conn
    elif Config.DB_TYPE == "mysql":
        import pymysql
        import pymysql.cursors

        conn = pymysql.connect(
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DATABASE,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )
        return conn
    else:
        raise ValueError(f"DB_TYPE không được hỗ trợ: {Config.DB_TYPE}")


def _adapt_sql(sql: str) -> str:
    """
    Tự động chuyển đổi placeholder tham số '?' sang '%s' khi DB_TYPE == 'mysql',
    giúp giữ nguyên câu truy vấn dùng chung cho cả SQLite và MySQL.
    """
    if Config.DB_TYPE == "mysql":
        return sql.replace("?", "%s")
    return sql


@contextmanager
def transaction(conn=None):
    """
    Context manager quản lý giao dịch:
    - conn.commit() khi khối lệnh thực thi thành công.
    - conn.rollback() và ném ngoại lệ khi có lỗi.
    - Tự động đóng kết nối nếu conn được tạo mới bên trong hàm.
    """
    need_close = False
    if conn is None:
        conn = get_db_connection()
        need_close = True
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if need_close:
            conn.close()


# --------------------------------------------------------------------------
# SQLAlchemy Engine (Duy trì tính tương thích với code hiện tại)
# --------------------------------------------------------------------------
def _build_engine():
    options = {"pool_pre_ping": True, "future": True}
    if Config.DB_TYPE == "mysql":
        options["pool_recycle"] = 280

    eng = create_engine(Config.DATABASE_URI, **options)

    if Config.DB_TYPE == "sqlite":
        @event.listens_for(eng, "connect")
        def _set_sqlite_pragmas(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()
    return eng


engine = _build_engine()


# --------------------------------------------------------------------------
# Tiện ích chuyển đổi kiểu dữ liệu & JSON serialization
# --------------------------------------------------------------------------
def _json_safe(value):
    """Thống nhất kiểu dữ liệu an toàn cho JSON (Decimal, datetime, date)."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    return value


def row_to_dict(row):
    """Chuyển đổi một dòng kết quả (sqlite3.Row, SQLAlchemy Row, dict) sang dict an toàn cho JSON."""
    if row is None:
        return None
    if isinstance(row, sqlite3.Row):
        d = dict(row)
    elif hasattr(row, "_mapping"):
        d = dict(row._mapping)
    elif isinstance(row, dict):
        d = row
    else:
        try:
            d = dict(row)
        except Exception:
            return row
    return {k: _json_safe(v) for k, v in d.items()}


def rows_to_dicts(result):
    """Chuyển danh sách dòng kết quả truy vấn sang list[dict] an toàn cho JSON."""
    if result is None:
        return []
    return [row_to_dict(r) for r in result]


def execute_query(sql, params=(), conn=None, fetch_one=False):
    """
    Thực thi câu lệnh SELECT có hỗ trợ _adapt_sql và trả về kết quả dạng dict / list[dict].
    """
    need_close = False
    if conn is None:
        conn = get_db_connection()
        need_close = True
    try:
        sql_adapted = _adapt_sql(sql)
        cur = conn.cursor()
        cur.execute(sql_adapted, params)
        if fetch_one:
            row = cur.fetchone()
            return row_to_dict(row)
        rows = cur.fetchall()
        return rows_to_dicts(rows)
    finally:
        if need_close:
            conn.close()


def get_month_bounds(ym_str):
    """Khoảng nửa mở [đầu tháng, đầu tháng sau) cho chuỗi 'YYYY-MM'."""
    try:
        first = datetime.strptime(ym_str, "%Y-%m").date()
    except (TypeError, ValueError):
        raise InvalidInputError("Tháng phải có dạng YYYY-MM, ví dụ 2026-10") from None

    nxt = date(first.year + (first.month == 12), first.month % 12 + 1, 1)
    start, end = first.isoformat(), nxt.isoformat()
    return start, end, f"{start} 00:00:00", f"{end} 00:00:00"


def normalize_datetime(value, field="Thời gian", default=None):
    """Chuẩn hóa DATETIME sang 'YYYY-MM-DD HH:MM:SS'."""
    if value is None or str(value).strip() == "":
        if default is not None:
            return default
        raise InvalidInputError(f"Thiếu {field}!")
    raw = str(value).strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    raise InvalidInputError(f"{field} không hợp lệ, cần dạng YYYY-MM-DD HH:MM[:SS]!")


# --------------------------------------------------------------------------
# Quản lý lỗi nghiệp vụ & Dịch lỗi Trigger/Constraint R1–R8 sang tiếng Việt
# --------------------------------------------------------------------------
class ApiError(Exception):
    status = 400

    def __init__(self, message, status=None):
        super().__init__(message)
        if status is not None:
            self.status = status


class InvalidInputError(ApiError, ValueError):
    pass


class NotFoundError(ApiError):
    status = 404


class ConflictError(ApiError):
    status = 409


_ERROR_RULES = [(re.compile(p, re.I), status, msg) for p, status, msg in (
    # R3: Đợt điều trị mở duy nhất
    (r"uq_dot_mo|dot_dieu_tri\.dot_dang_mo", 409,
     "Lỗi R3: Bệnh nhân này đang có đợt điều trị mở cho bệnh này. Hãy chọn nối vào đợt đang mở!"),
    # R1: Ràng buộc trùng lặp nghiệp vụ
    (r"(unique|duplicate).*chi_tiet_chan_doan", 409,
     "Lượt khám này đã có chẩn đoán cho đợt điều trị đó!"),
    (r"(unique|duplicate).*ct_don_thuoc", 409, "Thuốc này đã có trong đơn!"),
    (r"(unique|duplicate).*bac_si_chuyen_mon", 409, "Bác sĩ đã có chuyên môn này!"),
    (r"(unique|duplicate).*\bcmt\b", 409, "Lỗi R1: Số CMT/CCCD đã tồn tại trong hệ thống!"),
    (r"(unique|duplicate).*\bma_benh_nhan\b", 409, "Lỗi R1: Mã bệnh nhân đã tồn tại!"),
    (r"(unique|duplicate).*\bma_nhan_vien\b", 409, "Lỗi R1: Mã nhân viên đã tồn tại!"),
    (r"(unique|duplicate).*\bma_bac_si\b", 409, "Lỗi R1: Mã bác sĩ đã tồn tại!"),
    (r"(unique|duplicate).*\bten_benh\b", 409, "Lỗi R1: Tên bệnh đã tồn tại trong danh mục!"),
    (r"(unique|duplicate).*\bten_thuoc\b", 409, "Lỗi R1: Tên thuốc đã tồn tại trong danh mục!"),
    # R2: Thời gian và ngày tháng
    (r"ck_lk_time", 400, "Lỗi R2: Thời điểm ra viện không được nhỏ hơn thời điểm vào khám!"),
    (r"ck_dot_dates", 400, "Lỗi R2: Ngày kết thúc đợt không được nhỏ hơn ngày bắt đầu!"),
    # R4: Trạng thái đợt điều trị
    (r"ck_dot_state", 400,
     "Lỗi R4: Trạng thái đợt điều trị không khớp với ngày kết thúc / lượt khám kết thúc!"),
    # R5: Cùng bệnh nhân
    (r"lan kham va dot dieu tri phai cung benh nhan", 400,
     "Lỗi R5: Lượt khám và đợt điều trị phải thuộc cùng một bệnh nhân!"),
    # R6: Đợt đóng không thêm chẩn đoán & không mở lại
    (r"khong the (them|chuyen) chan doan vao dot da dong", 409,
     "Lỗi R6: Đợt điều trị này đã KHỎI (đã đóng), không thể thêm chẩn đoán vào đợt đã đóng!"),
    (r"dot da khoi khong duoc mo lai", 409,
     "Lỗi R6: Đợt đã khỏi không được mở lại. Nếu bệnh nhân tái phát, hãy tạo đợt điều trị mới!"),
    # R7: Lượt khám kết thúc
    (r"luot kham ket thuc phai thuoc dot dieu tri nay|fk_dot_lan_ket_thuc", 400,
     "Lỗi R7: Lượt khám kết thúc phải nằm trong các chẩn đoán thuộc đợt điều trị này!"),
    # R8: Cấp đơn thuốc
    (r"ck_don_cap", 400,
     "Lỗi R8: Đơn thuốc đã cấp (DA_CAP) phải có thời điểm cấp sau hoặc bằng ngày kê!"),
    # R1: Số lượng và đơn giá
    (r"ck_ctdt_qty|so luong thuoc phai lon hon 0", 400,
     "Lỗi R1: Số lượng thuốc trong đơn phải lớn hơn 0!"),
    (r"ck_thuoc_gia|gia_hien_hanh > 0|don_gia_hien_tai > 0", 400,
     "Lỗi R1: Đơn giá hiện hành của thuốc phải lớn hơn 0!"),
    (r"ck_thuoc_ton", 409, "Không đủ tồn kho thuốc để thực hiện thao tác này!"),
    (r"ck_phi", 400, "Lỗi R1: Phí khám chữa bệnh không được âm!"),
    # Khóa ngoại và ràng buộc dữ liệu
    (r"foreign key constraint failed|cannot add or update a child row|cannot delete or update a parent row", 409,
     "Mã đã tồn tại hoặc danh mục đang được sử dụng ở nơi khác, không thể xóa/sửa!"),
    (r"unique constraint failed|duplicate entry", 409,
     "Mã hoặc thông tin này đã tồn tại trong hệ thống!"),
    (r"not null constraint failed|cannot be null|doesn't have a default value", 400,
     "Thiếu dữ liệu bắt buộc!"),
)]

_GENERIC_ERROR = "Lỗi thao tác dữ liệu. Vui lòng kiểm tra lại ràng buộc dữ liệu hoặc liên hệ quản trị viên."


def describe_db_error(e):
    """Trả về tuple (http_status, thông báo tiếng Việt)."""
    raw = str(getattr(e, "orig", None) or e)
    for pattern, status, message in _ERROR_RULES:
        if pattern.search(raw):
            return status, message
    logger.error("Lỗi CSDL chưa được ánh xạ: %s", raw)
    return 400, _GENERIC_ERROR


def translate_db_error(e):
    """Trả về thông báo lỗi tiếng Việt dễ hiểu từ ngoại lệ CSDL."""
    return describe_db_error(e)[1]
