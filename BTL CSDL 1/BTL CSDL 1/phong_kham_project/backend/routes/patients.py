"""Blueprint quản lý Bệnh nhân và Hồ sơ bệnh án chi tiết (Truy vấn 3A, 3B, 3C, 3D)."""
from flask import Blueprint, jsonify, request
from sqlalchemy import text

from backend.database import (
    describe_db_error,
    engine,
    rows_to_dicts,
)

patients_bp = Blueprint("patients", __name__)


# ==============================================================================
# MÀN HÌNH 2 & TÍNH NĂNG PHỤ #1, #9: QUẢN LÝ BỆNH NHÂN (CRUD & TÌM KIẾM)
# ==============================================================================
@patients_bp.route("/api/patients", methods=["GET", "POST"])
def api_patients():
    """
    GET: Tìm kiếm & lọc hồ sơ bệnh nhân theo q (Mã BN, CMT/CCCD, Họ tên, SĐT)
         và status ('DANG_DIEU_TRI', 'KHONG_BENH', 'KHOI').
    POST: Thêm bệnh nhân mới (kiểm tra không trùng CMT/CCCD và Mã BN).
    """
    if request.method == "GET":
        q = request.args.get("q", "").strip()
        status_filter = request.args.get("status", "").strip().upper()

        sql = """
            SELECT bn.ma_nguoi, bn.ma_benh_nhan, n.cmt, n.ho_ten, n.ngay_sinh, n.gioi_tinh,
                   n.dia_chi, n.so_dien_thoai,
                   (SELECT COUNT(*) FROM DOT_DIEU_TRI d
                    WHERE d.ma_benh_nhan = bn.ma_nguoi AND d.trang_thai = 'DANG_DIEU_TRI') AS so_dot_dang_mo
            FROM BENH_NHAN bn
            JOIN NGUOI n ON n.ma_nguoi = bn.ma_nguoi
            WHERE 1=1
        """
        params = {}
        if q:
            sql += """
                AND (bn.ma_benh_nhan LIKE :q
                     OR n.cmt LIKE :q
                     OR n.ho_ten LIKE :q
                     OR n.so_dien_thoai LIKE :q)
            """
            params["q"] = f"%{q}%"

        if status_filter == "DANG_DIEU_TRI":
            sql += """
                AND EXISTS (
                    SELECT 1 FROM DOT_DIEU_TRI d
                    WHERE d.ma_benh_nhan = bn.ma_nguoi AND d.trang_thai = 'DANG_DIEU_TRI'
                )
            """
        elif status_filter in ("KHONG_BENH", "KHOI"):
            sql += """
                AND NOT EXISTS (
                    SELECT 1 FROM DOT_DIEU_TRI d
                    WHERE d.ma_benh_nhan = bn.ma_nguoi AND d.trang_thai = 'DANG_DIEU_TRI'
                )
            """

        sql += " ORDER BY bn.ma_benh_nhan"
        with engine.connect() as conn:
            return jsonify(rows_to_dicts(conn.execute(text(sql), params)))

    # POST: Thêm bệnh nhân mới
    data = request.json or {}
    ma_bn = str(data.get("ma_benh_nhan", "")).strip()
    cmt = str(data.get("cmt", "")).strip()
    ho_ten = str(data.get("ho_ten", "")).strip()
    ngay_sinh = str(data.get("ngay_sinh", "")).strip()
    gioi_tinh = str(data.get("gioi_tinh", "")).strip()

    if not ma_bn or not cmt or not ho_ten or not ngay_sinh or not gioi_tinh:
        return (
            jsonify({
                "success": False,
                "message": "Vui lòng nhập đầy đủ: Mã bệnh nhân, CMT/CCCD, Họ tên, Ngày sinh, Giới tính!",
                "error": "Thiếu dữ liệu bắt buộc!",
            }),
            400,
        )

    try:
        with engine.begin() as conn:
            # Kiểm tra trùng CMT
            dup_cmt = conn.execute(
                text("SELECT 1 FROM NGUOI WHERE cmt = :cmt LIMIT 1"), {"cmt": cmt}
            ).fetchone()
            if dup_cmt:
                return (
                    jsonify({
                        "success": False,
                        "message": "Lỗi R1: Số CMT/CCCD đã tồn tại trong hệ thống!",
                        "error": "Lỗi R1: Số CMT/CCCD đã tồn tại trong hệ thống!",
                    }),
                    409,
                )

            # Kiểm tra trùng Mã bệnh nhân
            dup_bn = conn.execute(
                text("SELECT 1 FROM BENH_NHAN WHERE ma_benh_nhan = :mbn LIMIT 1"),
                {"mbn": ma_bn},
            ).fetchone()
            if dup_bn:
                return (
                    jsonify({
                        "success": False,
                        "message": "Lỗi R1: Mã bệnh nhân đã tồn tại!",
                        "error": "Lỗi R1: Mã bệnh nhân đã tồn tại!",
                    }),
                    409,
                )

            res = conn.execute(
                text("""
                INSERT INTO NGUOI (cmt, ho_ten, ngay_sinh, gioi_tinh, dia_chi, so_dien_thoai)
                VALUES (:cmt, :ho_ten, :ngay_sinh, :gioi_tinh, :dia_chi, :so_dien_thoai)
            """),
                {
                    "cmt": cmt,
                    "ho_ten": ho_ten,
                    "ngay_sinh": ngay_sinh,
                    "gioi_tinh": gioi_tinh,
                    "dia_chi": data.get("dia_chi", ""),
                    "so_dien_thoai": data.get("so_dien_thoai", ""),
                },
            )
            ma_nguoi = res.lastrowid

            conn.execute(
                text("""
                INSERT INTO BENH_NHAN (ma_nguoi, ma_benh_nhan)
                VALUES (:ma_nguoi, :ma_benh_nhan)
            """),
                {"ma_nguoi": ma_nguoi, "ma_benh_nhan": ma_bn},
            )

        return jsonify({
            "success": True,
            "message": "Thêm hồ sơ bệnh nhân thành công!",
            "ma_nguoi": ma_nguoi,
        })
    except Exception as e:
        status, msg = describe_db_error(e)
        return jsonify({"success": False, "message": msg, "error": msg}), status


@patients_bp.route("/api/patients/<int:ma_nguoi>", methods=["PUT", "DELETE"])
def api_patient_modify(ma_nguoi):
    """PUT/DELETE hồ sơ bệnh nhân theo ma_nguoi."""
    if request.method == "PUT":
        data = request.json or {}
        cmt = str(data.get("cmt", "")).strip()
        ma_bn = str(data.get("ma_benh_nhan", "")).strip()
        ho_ten = str(data.get("ho_ten", "")).strip()
        ngay_sinh = str(data.get("ngay_sinh", "")).strip()
        gioi_tinh = str(data.get("gioi_tinh", "")).strip()

        try:
            with engine.begin() as conn:
                if cmt:
                    dup_cmt = conn.execute(
                        text("SELECT 1 FROM NGUOI WHERE cmt = :cmt AND ma_nguoi != :id LIMIT 1"),
                        {"cmt": cmt, "id": ma_nguoi},
                    ).fetchone()
                    if dup_cmt:
                        return (
                            jsonify({
                                "success": False,
                                "message": "Lỗi R1: Số CMT/CCCD đã tồn tại ở người khác!",
                                "error": "Lỗi R1: Số CMT/CCCD đã tồn tại ở người khác!",
                            }),
                            409,
                        )

                if ma_bn:
                    dup_bn = conn.execute(
                        text("SELECT 1 FROM BENH_NHAN WHERE ma_benh_nhan = :mbn AND ma_nguoi != :id LIMIT 1"),
                        {"mbn": ma_bn, "id": ma_nguoi},
                    ).fetchone()
                    if dup_bn:
                        return (
                            jsonify({
                                "success": False,
                                "message": "Lỗi R1: Mã bệnh nhân đã tồn tại ở người khác!",
                                "error": "Lỗi R1: Mã bệnh nhân đã tồn tại ở người khác!",
                            }),
                            409,
                        )

                conn.execute(
                    text("""
                    UPDATE NGUOI
                    SET cmt = COALESCE(:cmt, cmt),
                        ho_ten = COALESCE(:ho_ten, ho_ten),
                        ngay_sinh = COALESCE(:ngay_sinh, ngay_sinh),
                        gioi_tinh = COALESCE(:gioi_tinh, gioi_tinh),
                        dia_chi = COALESCE(:dia_chi, dia_chi),
                        so_dien_thoai = COALESCE(:so_dien_thoai, so_dien_thoai)
                    WHERE ma_nguoi = :ma_nguoi
                """),
                    {
                        "cmt": cmt if cmt else None,
                        "ho_ten": ho_ten if ho_ten else None,
                        "ngay_sinh": ngay_sinh if ngay_sinh else None,
                        "gioi_tinh": gioi_tinh if gioi_tinh else None,
                        "dia_chi": data.get("dia_chi"),
                        "so_dien_thoai": data.get("so_dien_thoai"),
                        "ma_nguoi": ma_nguoi,
                    },
                )

                if ma_bn:
                    conn.execute(
                        text("""
                        UPDATE BENH_NHAN SET ma_benh_nhan = :ma_benh_nhan
                        WHERE ma_nguoi = :ma_nguoi
                    """),
                        {"ma_benh_nhan": ma_bn, "ma_nguoi": ma_nguoi},
                    )

            return jsonify({"success": True, "message": "Cập nhật bệnh nhân thành công!"})
        except Exception as e:
            status, msg = describe_db_error(e)
            return jsonify({"success": False, "message": msg, "error": msg}), status

    # DELETE: Xóa bệnh nhân
    try:
        with engine.begin() as conn:
            # Kiểm tra xem có lượt khám hoặc đợt điều trị không
            has_visits = conn.execute(
                text("SELECT 1 FROM LAN_KHAM WHERE ma_benh_nhan = :id LIMIT 1"),
                {"id": ma_nguoi},
            ).fetchone()
            has_episodes = conn.execute(
                text("SELECT 1 FROM DOT_DIEU_TRI WHERE ma_benh_nhan = :id LIMIT 1"),
                {"id": ma_nguoi},
            ).fetchone()
            if has_visits or has_episodes:
                return (
                    jsonify({
                        "success": False,
                        "message": "Không thể xóa bệnh nhân đã có lịch sử khám/điều trị để bảo toàn dữ liệu!",
                        "error": "Không thể xóa bệnh nhân đã có lịch sử khám/điều trị để bảo toàn dữ liệu!",
                    }),
                    409,
                )

            conn.execute(text("DELETE FROM BENH_NHAN WHERE ma_nguoi = :id"), {"id": ma_nguoi})
            # Nếu người này không phải là nhân viên, xóa luôn bản ghi NGUOI
            is_staff = conn.execute(
                text("SELECT 1 FROM NHAN_VIEN WHERE ma_nguoi = :id LIMIT 1"), {"id": ma_nguoi}
            ).fetchone()
            if not is_staff:
                conn.execute(text("DELETE FROM NGUOI WHERE ma_nguoi = :id"), {"id": ma_nguoi})

        return jsonify({"success": True, "message": "Đã xóa bệnh nhân thành công!"})
    except Exception as e:
        status, msg = describe_db_error(e)
        return jsonify({"success": False, "message": msg, "error": msg}), status


# ==============================================================================
# TRUY VẤN LÕI #3: CHI TIẾT HỒ SƠ BỆNH NHÂN (3A, 3B, 3C, 3D)
# ==============================================================================
@patients_bp.route("/api/patients/<int:ma_nguoi>/detail", methods=["GET"])
def api_patient_detail(ma_nguoi):
    """
    Thực thi Truy vấn 3 phân tách thành 4 phần độc lập (tránh trùng dòng):
    - profile / info: Hồ sơ hành chính
    - visit_history / history_3a: Lịch sử các lượt khám (đánh số lần khám trong đợt bằng ROW_NUMBER)
    - open_episodes / open_episodes_3b: Các episode đang mở
    - nurse_events / nurse_events_3c: Các sự kiện y tá hỗ trợ
    - prescriptions / prescriptions_3d: Danh sách thuốc đã kê
    """
    with engine.connect() as conn:
        info_row = conn.execute(
            text("""
            SELECT bn.ma_nguoi, bn.ma_benh_nhan, n.cmt, n.ho_ten, n.ngay_sinh, n.gioi_tinh, n.dia_chi, n.so_dien_thoai
            FROM BENH_NHAN bn
            JOIN NGUOI n ON n.ma_nguoi = bn.ma_nguoi
            WHERE bn.ma_nguoi = :id
        """),
            {"id": ma_nguoi},
        ).mappings().first()

        profile = dict(info_row) if info_row else {}

        # 3A: Lịch sử lượt khám
        q3a = rows_to_dicts(
            conn.execute(
                text("""
            SELECT bn.ma_benh_nhan, n.ho_ten, lk.ma_lan_kham, lk.thoi_diem_vao, lk.thoi_diem_ra,
                   b.ten_benh, d.ma_dot, d.trang_thai AS tinh_trang_dot,
                   ROW_NUMBER() OVER (PARTITION BY d.ma_dot ORDER BY lk.thoi_diem_vao, lk.ma_lan_kham) AS lan_thu_trong_dot,
                   bs.ma_bac_si, bs_n.ho_ten AS ten_bac_si, cd.phi_kham_chua, cd.ket_luan
            FROM BENH_NHAN bn
            JOIN NGUOI n ON n.ma_nguoi = bn.ma_nguoi
            JOIN LAN_KHAM lk ON lk.ma_benh_nhan = bn.ma_nguoi
            JOIN CHI_TIET_CHAN_DOAN cd ON cd.ma_lan_kham = lk.ma_lan_kham
            JOIN DOT_DIEU_TRI d ON d.ma_dot = cd.ma_dot
            JOIN BENH b ON b.ma_benh = d.ma_benh
            JOIN BAC_SI bs ON bs.ma_bac_si = cd.ma_bac_si
            JOIN NGUOI bs_n ON bs_n.ma_nguoi = bs.ma_nguoi
            WHERE bn.ma_nguoi = :id
            ORDER BY lk.thoi_diem_vao DESC, b.ten_benh
        """),
                {"id": ma_nguoi},
            )
        )

        # 3B: Các episode đang điều trị (đang mở)
        q3b = rows_to_dicts(
            conn.execute(
                text("""
            SELECT bn.ma_benh_nhan, n.ho_ten, b.ten_benh, d.ma_dot,
                   COUNT(cd.ma_lan_kham) AS so_lan_kham,
                   MAX(lk.thoi_diem_vao) AS lan_kham_gan_nhat
            FROM BENH_NHAN bn
            JOIN NGUOI n ON n.ma_nguoi = bn.ma_nguoi
            JOIN DOT_DIEU_TRI d ON d.ma_benh_nhan = bn.ma_nguoi
            JOIN BENH b ON b.ma_benh = d.ma_benh
            JOIN CHI_TIET_CHAN_DOAN cd ON cd.ma_dot = d.ma_dot
            JOIN LAN_KHAM lk ON lk.ma_lan_kham = cd.ma_lan_kham
            WHERE bn.ma_nguoi = :id AND d.trang_thai = 'DANG_DIEU_TRI'
            GROUP BY bn.ma_benh_nhan, n.ho_ten, b.ten_benh, d.ma_dot
            ORDER BY b.ten_benh
        """),
                {"id": ma_nguoi},
            )
        )

        # 3C: Sự kiện y tá hỗ trợ
        q3c = rows_to_dicts(
            conn.execute(
                text("""
            SELECT lk.ma_lan_kham, lk.thoi_diem_vao, yt.ma_nguoi AS ma_y_ta,
                   n.ho_ten AS ten_y_ta, h.vai_tro, h.thoi_diem, h.ghi_chu
            FROM LAN_KHAM lk
            JOIN Y_TA_HO_TRO h ON h.ma_lan_kham = lk.ma_lan_kham
            JOIN Y_TA yt ON yt.ma_nguoi = h.ma_y_ta
            JOIN NGUOI n ON n.ma_nguoi = yt.ma_nguoi
            WHERE lk.ma_benh_nhan = :id
            ORDER BY lk.thoi_diem_vao DESC, h.thoi_diem DESC
        """),
                {"id": ma_nguoi},
            )
        )

        # 3D: Thuốc đã kê
        q3d = rows_to_dicts(
            conn.execute(
                text("""
            SELECT lk.ma_lan_kham, lk.thoi_diem_vao, d.ma_don, d.ngay_ke, d.trang_thai,
                   t.ten_thuoc, ct.so_luong, ct.don_gia_tai_thoi_diem,
                   (ct.so_luong * ct.don_gia_tai_thoi_diem) AS thanh_tien, ct.huong_dan_dung
            FROM LAN_KHAM lk
            JOIN DON_THUOC d ON d.ma_lan_kham = lk.ma_lan_kham
            JOIN CT_DON_THUOC ct ON ct.ma_don = d.ma_don
            JOIN THUOC t ON t.ma_thuoc = ct.ma_thuoc
            WHERE lk.ma_benh_nhan = :id
            ORDER BY lk.thoi_diem_vao DESC, d.ma_don DESC, t.ten_thuoc
        """),
                {"id": ma_nguoi},
            )
        )

    return jsonify({
        "success": True,
        # Format chuẩn theo tài liệu & test
        "profile": profile,
        "visit_history": q3a,
        "open_episodes": q3b,
        "prescriptions": q3d,
        "nurse_events": q3c,
        # Format tương thích 100% với patients_visits.js
        "info": profile,
        "history_3a": q3a,
        "open_episodes_3b": q3b,
        "nurse_events_3c": q3c,
        "prescriptions_3d": q3d,
    })
