"""Blueprint Màn hình 1 (Tổng quan) và Màn hình 9 (Cài đặt / Hướng dẫn & Tài khoản demo)."""
from datetime import datetime
from flask import Blueprint, jsonify, request
from sqlalchemy import text

from backend.config import Config
from backend.database import engine, get_month_bounds, rows_to_dicts
from backend.seed_sqlite import init_sqlite_db

overview_bp = Blueprint("overview", __name__)


# ==============================================================================
# MÀN HÌNH 1: TỔNG QUAN HỆ THỐNG
# ==============================================================================
@overview_bp.route("/api/overview", methods=["GET"])
def api_overview():
    """
    Truy vấn 3 chỉ số thực tế từ DB:
    1. Số lượt khám hôm nay (DATE(thoi_diem_vao) = DATE('now', 'localtime') hoặc theo ngày chỉ định)
    2. Số bệnh nhân đang có episode điều trị mở (active_patients) & số episode đang mở (open_episodes)
    3. Tổng doanh thu của tháng hiện tại (tiền khám + tiền thuốc, dùng COALESCE tránh null/NaN).
    """
    month = request.args.get("month", "2026-10")
    d_start, d_end, dt_start, dt_end = get_month_bounds(month)

    # Ngày kiểm tra: ưu tiên param today, nếu không lấy ngày hiện tại của hệ thống
    today_param = request.args.get("today")
    today_str = today_param if today_param else datetime.now().strftime("%Y-%m-%d")

    with engine.connect() as conn:
        # 1. Số lượt khám hôm nay
        res_today = conn.execute(
            text("""
            SELECT COUNT(*) FROM LAN_KHAM
            WHERE thoi_diem_vao >= :t1 AND thoi_diem_vao < :t2
        """),
            {"t1": f"{today_str} 00:00:00", "t2": f"{today_str} 23:59:59"},
        ).scalar()
        visits_today = int(res_today or 0)

        # Nếu ngày hiện tại chưa có dữ liệu và không truyền tham số today,
        # fallback lấy số lượt khám của ngày có dữ liệu gần nhất trong tháng để Màn 1 hiển thị đẹp
        if visits_today == 0 and not today_param:
            recent_day = conn.execute(
                text("""
                SELECT SUBSTR(thoi_diem_vao, 1, 10) AS ngay, COUNT(*) AS cnt
                FROM LAN_KHAM
                WHERE thoi_diem_vao >= :dt1 AND thoi_diem_vao < :dt2
                GROUP BY SUBSTR(thoi_diem_vao, 1, 10)
                ORDER BY ngay DESC LIMIT 1
            """),
                {"dt1": dt_start, "dt2": dt_end},
            ).mappings().first()
            if recent_day:
                visits_today = int(recent_day["cnt"])

        # 2. Số lượt khám trong tháng
        visits_month = int(
            conn.execute(
                text("""
            SELECT COUNT(*) FROM LAN_KHAM
            WHERE thoi_diem_vao >= :dt1 AND thoi_diem_vao < :dt2
        """),
                {"dt1": dt_start, "dt2": dt_end},
            ).scalar()
            or 0
        )

        # 3. Số episode đang mở và số bệnh nhân đang có episode mở
        open_episodes = int(
            conn.execute(
                text("SELECT COUNT(*) FROM DOT_DIEU_TRI WHERE trang_thai = 'DANG_DIEU_TRI'")
            ).scalar()
            or 0
        )

        active_patients = int(
            conn.execute(
                text("SELECT COUNT(DISTINCT ma_benh_nhan) FROM DOT_DIEU_TRI WHERE trang_thai = 'DANG_DIEU_TRI'")
            ).scalar()
            or 0
        )

        # 4. Tổng doanh thu tháng (COALESCE đảm bảo luôn trả số >= 0, không trả null)
        rev_row = conn.execute(
            text("""
            SELECT COALESCE(kham.doanh_thu_kham_chua, 0) AS doanh_thu_kham_chua,
                   COALESCE(thuoc.doanh_thu_thuoc, 0) AS doanh_thu_thuoc,
                   COALESCE(kham.doanh_thu_kham_chua, 0) + COALESCE(thuoc.doanh_thu_thuoc, 0) AS tong_doanh_thu
            FROM (
              SELECT COALESCE(SUM(cd.phi_kham_chua), 0) AS doanh_thu_kham_chua
              FROM CHI_TIET_CHAN_DOAN cd
              JOIN LAN_KHAM lk ON lk.ma_lan_kham = cd.ma_lan_kham
              WHERE lk.thoi_diem_vao >= :dt1 AND lk.thoi_diem_vao < :dt2
            ) kham
            CROSS JOIN (
              SELECT COALESCE(SUM(ct.so_luong * ct.don_gia_tai_thoi_diem), 0) AS doanh_thu_thuoc
              FROM CT_DON_THUOC ct
              JOIN DON_THUOC d ON d.ma_don = ct.ma_don
              WHERE d.trang_thai = 'DA_CAP'
                AND d.thoi_diem_cap >= :dt1 AND d.thoi_diem_cap < :dt2
            ) thuoc
        """),
            {"dt1": dt_start, "dt2": dt_end},
        ).mappings().first()

        rev_data = {
            "doanh_thu_kham_chua": float(rev_row["doanh_thu_kham_chua"]) if rev_row else 0.0,
            "doanh_thu_thuoc": float(rev_row["doanh_thu_thuoc"]) if rev_row else 0.0,
            "tong_doanh_thu": float(rev_row["tong_doanh_thu"]) if rev_row else 0.0,
        }

        # 5. Thống kê số lượng dòng trong 16 bảng
        counts = rows_to_dicts(
            conn.execute(
                text("""
            SELECT 'NGUOI' AS ten_bang, COUNT(*) AS so_ban_ghi FROM NGUOI
            UNION ALL SELECT 'NHAN_VIEN', COUNT(*) FROM NHAN_VIEN
            UNION ALL SELECT 'BAC_SI', COUNT(*) FROM BAC_SI
            UNION ALL SELECT 'Y_TA', COUNT(*) FROM Y_TA
            UNION ALL SELECT 'BENH_NHAN', COUNT(*) FROM BENH_NHAN
            UNION ALL SELECT 'CHUYEN_MON', COUNT(*) FROM CHUYEN_MON
            UNION ALL SELECT 'BAC_SI_CHUYEN_MON', COUNT(*) FROM BAC_SI_CHUYEN_MON
            UNION ALL SELECT 'BENH', COUNT(*) FROM BENH
            UNION ALL SELECT 'THUOC', COUNT(*) FROM THUOC
            UNION ALL SELECT 'LAN_KHAM', COUNT(*) FROM LAN_KHAM
            UNION ALL SELECT 'DOT_DIEU_TRI', COUNT(*) FROM DOT_DIEU_TRI
            UNION ALL SELECT 'CHI_TIET_CHAN_DOAN', COUNT(*) FROM CHI_TIET_CHAN_DOAN
            UNION ALL SELECT 'Y_TA_HO_TRO', COUNT(*) FROM Y_TA_HO_TRO
            UNION ALL SELECT 'DON_THUOC', COUNT(*) FROM DON_THUOC
            UNION ALL SELECT 'CT_DON_THUOC', COUNT(*) FROM CT_DON_THUOC
            UNION ALL SELECT 'TAI_KHOAN', COUNT(*) FROM TAI_KHOAN
        """)
            )
        )

    return jsonify({
        "success": True,
        "db_type": Config.DB_TYPE.upper(),
        "month": month,
        "visits_today": visits_today,
        "visits_month": visits_month,
        "open_episodes": open_episodes,
        "active_patients": active_patients,
        "revenue": rev_data,
        "table_counts": counts,
    })


# ==============================================================================
# MÀN HÌNH 9: CÀI ĐẶT / HƯỚNG DẪN & TÀI KHOẢN DEMO
# ==============================================================================
@overview_bp.route("/api/settings", methods=["GET"])
def api_settings():
    """
    Trả về quy tắc tính tháng, danh sách tài khoản demo và hướng dẫn thao tác.
    """
    return jsonify({
        "success": True,
        "app_name": "MedCare Clinic - Hệ Thống Quản Lý Phòng Khám Tư Nhân",
        "month_rules": {
            "interval": "Khoảng nửa mở [ngày đầu tháng, ngày đầu tháng sau), ví dụ [2026-10-01, 2026-11-01)",
            "exam_revenue": "Tính theo thời điểm vào (thoi_diem_vao) của lượt khám",
            "medicine_revenue": "Tính theo thời điểm cấp (thoi_diem_cap) của đơn thuốc trạng thái DA_CAP",
            "doctor_bonus": "7.000.000đ lương cơ bản + 1.000.000đ cho mỗi đợt KHOI có ngay_ket_thuc trong tháng",
            "nurse_bonus": "5.000.000đ lương cơ bản + 200.000đ cho mỗi sự kiện hỗ trợ có thoi_diem trong tháng",
        },
        "demo_accounts": [
            {
                "role": "ADMIN",
                "cmt": "001000000010",
                "ho_ten": "Bác sĩ Minh (Quản trị viên)",
                "password": "demo123",
                "permissions": "Toàn quyền quản trị toàn bộ hệ thống",
            },
            {
                "role": "BAC_SI",
                "cmt": "001000000011",
                "ho_ten": "Bác sĩ Lan (Bác sĩ chuyên môn)",
                "password": "demo123",
                "permissions": "Khám bệnh, chẩn đoán, kê đơn, kết thúc Episode",
            },
            {
                "role": "Y_TA",
                "cmt": "001000000020",
                "ho_ten": "Y tá Hoa (Y tá phòng khám)",
                "password": "demo123",
                "permissions": "Tiếp nhận bệnh nhân, ghi nhận sự kiện hỗ trợ, ra viện",
            },
        ],
        "workflow_steps": [
            "Bước 1: Tiếp nhận bệnh nhân & tạo lượt khám mới (Màn hình 3)",
            "Bước 2: Ghi nhận chẩn đoán và nối/tạo Episode điều trị (Màn hình 3 & 4)",
            "Bước 3: Y tá tham gia hỗ trợ khám chữa bệnh (Màn hình 3)",
            "Bước 4: Bác sĩ kê đơn thuốc đa dòng với giá chốt lịch sử (Màn hình 5)",
            "Bước 5: Xác nhận cấp phát thuốc (DA_CAP) và cập nhật ra viện (Màn hình 5 & 3)",
            "Bước 6: Khi bệnh nhân khỏi, Bác sĩ kết thúc Episode để nhận thưởng (Màn hình 4)",
            "Bước 7: Xem báo cáo thống kê bệnh, bảng lương và doanh thu tháng (Màn hình 7)",
        ],
    })


@overview_bp.route("/api/reset-sqlite", methods=["POST"])
def api_reset_sqlite():
    """Khôi phục nhanh dữ liệu mẫu chuẩn tháng 10/2026 trên SQLite."""
    if Config.DB_TYPE != "sqlite":
        return jsonify({"error": "Chức năng reset nhanh chỉ dùng cho SQLite!"}), 400
    init_sqlite_db(force_reset=True)
    return jsonify({"success": True, "message": "Đã khôi phục toàn bộ dữ liệu mẫu tháng 10/2026 trên SQLite!"})
