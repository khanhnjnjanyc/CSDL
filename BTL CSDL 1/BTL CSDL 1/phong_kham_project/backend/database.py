"""Kết nối CSDL và các hàm tiện ích dùng chung cho các route."""
import logging
import re
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import create_engine, event

from backend.config import Config

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """Lỗi nghiệp vụ có chủ đích; handler toàn cục trả JSON {"error": ...} với mã status."""
    status = 400

    def __init__(self, message, status=None):
        super().__init__(message)
        if status is not None:
            self.status = status


class InvalidInputError(ApiError, ValueError):
    """Dữ liệu đầu vào sai/thiếu (400)."""


class NotFoundError(ApiError):
    """Không tìm thấy đối tượng tham chiếu (404)."""
    status = 404


class ConflictError(ApiError):
    """Xung đột trạng thái/nghiệp vụ, ví dụ không đủ tồn kho (409)."""
    status = 409


def _build_engine():
    options = {"pool_pre_ping": True, "future": True}
    if Config.DB_TYPE == "mysql":
        options["pool_recycle"] = 280  # tránh bị MySQL/Cloud ngắt kết nối nhàn rỗi

    eng = create_engine(Config.DATABASE_URI, **options)

    if Config.DB_TYPE == "sqlite":
        @event.listens_for(eng, "connect")
        def _set_sqlite_pragmas(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")   # bật kiểm tra khóa ngoại
            cursor.execute("PRAGMA journal_mode=WAL")  # đọc/ghi đồng thời tốt hơn
            cursor.execute("PRAGMA busy_timeout=5000")  # chờ 5s thay vì 'database is locked'
            cursor.close()
    return eng


engine = _build_engine()


def _json_safe(value):
    """
    Thống nhất kiểu dữ liệu giữa SQLite (trả int/chuỗi) và MySQL (trả Decimal/date/datetime),
    nếu không Flask sẽ xuất ngày MySQL dạng 'Sat, 14 Feb 1998 00:00:00 GMT'.
    """
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, datetime):  # phải kiểm tra trước date vì datetime là lớp con của date
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    return value


def rows_to_dicts(result):
    """Chuyển kết quả SQLAlchemy sang danh sách dict để trả về JSON."""
    return [{k: _json_safe(v) for k, v in row._mapping.items()} for row in result]


def get_month_bounds(ym_str):
    """
    Khoảng nửa mở [đầu tháng, đầu tháng sau) cho chuỗi 'YYYY-MM'.
    Trả về (ngày_bd, ngày_kt, datetime_bd, datetime_kt).
    Ném InvalidInputError (là ValueError) nếu sai định dạng -> HTTP 400.
    """
    try:
        first = datetime.strptime(ym_str, "%Y-%m").date()
    except (TypeError, ValueError):
        raise InvalidInputError("Tháng phải có dạng YYYY-MM, ví dụ 2026-10") from None

    nxt = date(first.year + (first.month == 12), first.month % 12 + 1, 1)
    start, end = first.isoformat(), nxt.isoformat()
    return start, end, f"{start} 00:00:00", f"{end} 00:00:00"


def normalize_datetime(value, field="Thời gian", default=None):
    """
    Chuẩn hóa 'YYYY-MM-DDTHH:MM[:SS]' hoặc 'YYYY-MM-DD HH:MM[:SS]' về 'YYYY-MM-DD HH:MM:SS'.
    Bắt buộc thống nhất định dạng vì SQLite so sánh DATETIME dạng chuỗi
    (ký tự 'T' đứng sau dấu cách sẽ làm sai lọc theo tháng).
    """
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
# Dịch lỗi CSDL -> (HTTP status, thông báo tiếng Việt). Khớp theo thứ tự.
# Quy tắc cụ thể phải đứng trước quy tắc chung.
# --------------------------------------------------------------------------
_ERROR_RULES = [(re.compile(p, re.I), status, msg) for p, status, msg in (
    (r"uq_dot_mo|dot_dieu_tri\.dot_dang_mo", 409,
     "Lỗi R3: Bệnh nhân này đang có đợt điều trị mở cho bệnh này. Hãy chọn nối vào đợt đang mở!"),
    (r"(unique|duplicate).*chi_tiet_chan_doan", 409,
     "Lượt khám này đã có chẩn đoán cho đợt điều trị đó!"),
    (r"(unique|duplicate).*ct_don_thuoc", 409, "Thuốc này đã có trong đơn!"),
    (r"(unique|duplicate).*bac_si_chuyen_mon", 409,
     "Bác sĩ đã có chuyên môn này!"),
    (r"(unique|duplicate).*\bcmt\b", 409,
     "Lỗi R1: Số CMT/CCCD đã tồn tại trong hệ thống!"),
    (r"(unique|duplicate).*\bma_benh_nhan\b", 409, "Lỗi R1: Mã bệnh nhân đã tồn tại!"),
    (r"(unique|duplicate).*\bma_nhan_vien\b", 409, "Lỗi R1: Mã nhân viên đã tồn tại!"),
    (r"(unique|duplicate).*\bma_bac_si\b", 409, "Lỗi R1: Mã bác sĩ đã tồn tại!"),
    (r"ck_lk_time", 400, "Lỗi R2: Thời điểm ra viện không được nhỏ hơn thời điểm vào khám!"),
    (r"ck_dot_dates", 400, "Lỗi R2: Ngày kết thúc đợt không được nhỏ hơn ngày bắt đầu!"),
    (r"ck_dot_state", 400,
     "Trạng thái đợt điều trị không khớp với ngày kết thúc / lượt khám kết thúc!"),
    (r"lan kham va dot dieu tri phai cung benh nhan", 400,
     "Lỗi R5: Lượt khám và đợt điều trị phải thuộc cùng một bệnh nhân!"),
    (r"khong the (them|chuyen) chan doan vao dot da dong", 409,
     "Lỗi R6: Đợt điều trị này đã KHỎI (đã đóng), không thể thêm chẩn đoán vào đợt đã đóng!"),
    (r"dot da khoi khong duoc mo lai", 409,
     "Lỗi R6: Đợt đã khỏi không được mở lại. Nếu bệnh nhân tái phát, hãy tạo đợt điều trị mới!"),
    (r"luot kham ket thuc phai thuoc dot dieu tri nay|fk_dot_lan_ket_thuc", 400,
     "Lỗi R7: Lượt khám kết thúc phải nằm trong các chẩn đoán thuộc đợt điều trị này!"),
    (r"ck_thuoc_ton", 409, "Không đủ tồn kho thuốc để thực hiện thao tác này!"),
    (r"foreign key constraint failed|cannot add or update a child row"
     r"|cannot delete or update a parent row", 409,
     "Dữ liệu tham chiếu không tồn tại hoặc đang được sử dụng ở nơi khác!"),
    (r"not null constraint failed|cannot be null|doesn't have a default value", 400,
     "Thiếu dữ liệu bắt buộc!"),
)]

_GENERIC_ERROR = "Lỗi dữ liệu không xác định. Vui lòng thử lại hoặc liên hệ quản trị viên."


def describe_db_error(e):
    """Trả về (http_status, thông báo). Không để lộ lỗi gốc của CSDL ra client."""
    raw = str(getattr(e, "orig", None) or e)
    for pattern, status, message in _ERROR_RULES:
        if pattern.search(raw):
            return status, message
    logger.error("Lỗi CSDL chưa được ánh xạ: %s", raw)
    return 500, _GENERIC_ERROR


def translate_db_error(e):
    """Giữ tương thích với code cũ: chỉ trả về thông báo."""
    return describe_db_error(e)[1]