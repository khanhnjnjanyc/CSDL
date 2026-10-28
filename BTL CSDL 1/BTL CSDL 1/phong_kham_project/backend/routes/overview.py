from flask import Blueprint, request, jsonify
from sqlalchemy import text
from backend.config import Config
from backend.database import engine, get_month_bounds, rows_to_dicts
from backend.seed_sqlite import init_sqlite_db

overview_bp = Blueprint("overview", __name__)

@overview_bp.route("/api/overview", methods=["GET"])
def api_overview():
    month = request.args.get("month", "2026-10")
    d_start, d_end, dt_start, dt_end = get_month_bounds(month)
    today = request.args.get("today", "2026-10-22")

    with engine.connect() as conn:
        visits_today = conn.execute(
            text("SELECT COUNT(*) FROM LAN_KHAM WHERE thoi_diem_vao >= :t1 AND thoi_diem_vao < :t2"),
            {"t1": f"{today} 00:00:00", "t2": f"{today} 23:59:59"}
        ).scalar() or 0

        visits_month = conn.execute(
            text("SELECT COUNT(*) FROM LAN_KHAM WHERE thoi_diem_vao >= :dt1 AND thoi_diem_vao < :dt2"),
            {"dt1": dt_start, "dt2": dt_end}
        ).scalar() or 0

        open_episodes = conn.execute(
            text("SELECT COUNT(*) FROM DOT_DIEU_TRI WHERE trang_thai = 'DANG_DIEU_TRI'")
        ).scalar() or 0

        active_patients = conn.execute(
            text("SELECT COUNT(DISTINCT ma_benh_nhan) FROM DOT_DIEU_TRI WHERE trang_thai = 'DANG_DIEU_TRI'")
        ).scalar() or 0

        rev_row = conn.execute(text("""
            SELECT kham.doanh_thu_kham_chua, thuoc.doanh_thu_thuoc,
                   kham.doanh_thu_kham_chua + thuoc.doanh_thu_thuoc AS tong_doanh_thu
            FROM (
              SELECT COALESCE(SUM(cd.phi_kham_chua),0) AS doanh_thu_kham_chua
              FROM CHI_TIET_CHAN_DOAN cd JOIN LAN_KHAM lk ON lk.ma_lan_kham=cd.ma_lan_kham
              WHERE lk.thoi_diem_vao >= :dt1 AND lk.thoi_diem_vao < :dt2
            ) kham
            CROSS JOIN (
              SELECT COALESCE(SUM(ct.so_luong*ct.don_gia_tai_thoi_diem),0) AS doanh_thu_thuoc
              FROM CT_DON_THUOC ct JOIN DON_THUOC d ON d.ma_don=ct.ma_don
              WHERE d.trang_thai = 'DA_CAP'
                AND d.thoi_diem_cap >= :dt1 AND d.thoi_diem_cap < :dt2
            ) thuoc
        """), {"dt1": dt_start, "dt2": dt_end}).mappings().first()

        counts = rows_to_dicts(conn.execute(text("""
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
        """)))

    return jsonify({
        "db_type": Config.DB_TYPE.upper(),
        "visits_today": visits_today,
        "visits_month": visits_month,
        "open_episodes": open_episodes,
        "active_patients": active_patients,
        "revenue": dict(rev_row) if rev_row else {"doanh_thu_kham_chua": 0, "doanh_thu_thuoc": 0, "tong_doanh_thu": 0},
        "table_counts": counts
    })

@overview_bp.route("/api/reset-sqlite", methods=["POST"])
def api_reset_sqlite():
    if Config.DB_TYPE != "sqlite":
        return jsonify({"error": "Chức năng reset nhanh chỉ dùng cho SQLite!"}), 400
    init_sqlite_db(force_reset=True)
    return jsonify({"message": "Đã khôi phục toàn bộ dữ liệu mẫu tháng 10/2026 trên SQLite!"})