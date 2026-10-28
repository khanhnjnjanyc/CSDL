from flask import Blueprint, request, jsonify
from sqlalchemy import text
from backend.database import engine, rows_to_dicts, translate_db_error

patients_bp = Blueprint("patients", __name__)

@patients_bp.route("/api/patients", methods=["GET", "POST"])
def api_patients():
    if request.method == "GET":
        q = request.args.get("q", "").strip()
        status_filter = request.args.get("status", "").strip()
        sql = """
            SELECT bn.ma_nguoi, bn.ma_benh_nhan, n.cmt, n.ho_ten, n.ngay_sinh, n.gioi_tinh,
                   n.dia_chi, n.so_dien_thoai,
                   (SELECT COUNT(*) FROM DOT_DIEU_TRI d WHERE d.ma_benh_nhan = bn.ma_nguoi AND d.trang_thai = 'DANG_DIEU_TRI') AS so_dot_dang_mo
            FROM BENH_NHAN bn
            JOIN NGUOI n ON n.ma_nguoi = bn.ma_nguoi
            WHERE 1=1
        """
        params = {}
        if q:
            sql += " AND (bn.ma_benh_nhan LIKE :q OR n.cmt LIKE :q OR n.ho_ten LIKE :q OR n.so_dien_thoai LIKE :q)"
            params["q"] = f"%{q}%"
        if status_filter == "DANG_DIEU_TRI":
            sql += " AND EXISTS (SELECT 1 FROM DOT_DIEU_TRI d WHERE d.ma_benh_nhan = bn.ma_nguoi AND d.trang_thai = 'DANG_DIEU_TRI')"
        elif status_filter == "KHONG_BENH":
            sql += " AND NOT EXISTS (SELECT 1 FROM DOT_DIEU_TRI d WHERE d.ma_benh_nhan = bn.ma_nguoi AND d.trang_thai = 'DANG_DIEU_TRI')"
        sql += " ORDER BY bn.ma_benh_nhan"
        with engine.connect() as conn:
            return jsonify(rows_to_dicts(conn.execute(text(sql), params)))

    data = request.json
    try:
        with engine.begin() as conn:
            res = conn.execute(text("""
                INSERT INTO NGUOI (cmt, ho_ten, ngay_sinh, gioi_tinh, dia_chi, so_dien_thoai)
                VALUES (:cmt, :ho_ten, :ngay_sinh, :gioi_tinh, :dia_chi, :so_dien_thoai)
            """), {
                "cmt": data["cmt"].strip(),
                "ho_ten": data["ho_ten"].strip(),
                "ngay_sinh": data["ngay_sinh"],
                "gioi_tinh": data["gioi_tinh"],
                "dia_chi": data.get("dia_chi", ""),
                "so_dien_thoai": data.get("so_dien_thoai", "")
            })
            ma_nguoi = res.lastrowid
            conn.execute(text("""
                INSERT INTO BENH_NHAN (ma_nguoi, ma_benh_nhan) VALUES (:ma_nguoi, :ma_benh_nhan)
            """), {"ma_nguoi": ma_nguoi, "ma_benh_nhan": data["ma_benh_nhan"].strip()})
        return jsonify({"message": "Thêm hồ sơ bệnh nhân thành công!", "ma_nguoi": ma_nguoi})
    except Exception as e:
        return jsonify({"error": translate_db_error(e)}), 400


@patients_bp.route("/api/patients/<int:ma_nguoi>", methods=["PUT", "DELETE"])
def api_patient_modify(ma_nguoi):
    if request.method == "PUT":
        data = request.json
        try:
            with engine.begin() as conn:
                conn.execute(text("""
                    UPDATE NGUOI SET cmt=:cmt, ho_ten=:ho_ten, ngay_sinh=:ngay_sinh,
                           gioi_tinh=:gioi_tinh, dia_chi=:dia_chi, so_dien_thoai=:so_dien_thoai
                    WHERE ma_nguoi=:ma_nguoi
                """), {
                    "cmt": data["cmt"].strip(),
                    "ho_ten": data["ho_ten"].strip(),
                    "ngay_sinh": data["ngay_sinh"],
                    "gioi_tinh": data["gioi_tinh"],
                    "dia_chi": data.get("dia_chi", ""),
                    "so_dien_thoai": data.get("so_dien_thoai", ""),
                    "ma_nguoi": ma_nguoi
                })
                conn.execute(text("""
                    UPDATE BENH_NHAN SET ma_benh_nhan=:ma_benh_nhan WHERE ma_nguoi=:ma_nguoi
                """), {"ma_benh_nhan": data["ma_benh_nhan"].strip(), "ma_nguoi": ma_nguoi})
            return jsonify({"message": "Cập nhật bệnh nhân thành công!"})
        except Exception as e:
            return jsonify({"error": translate_db_error(e)}), 400

    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM BENH_NHAN WHERE ma_nguoi=:id"), {"id": ma_nguoi})
            conn.execute(text("DELETE FROM NGUOI WHERE ma_nguoi=:id"), {"id": ma_nguoi})
        return jsonify({"message": "Đã xóa bệnh nhân!"})
    except Exception:
        return jsonify({"error": "Không thể xóa bệnh nhân đã có lịch sử khám/điều trị để bảo toàn dữ liệu!"}), 400


@patients_bp.route("/api/patients/<int:ma_nguoi>/detail", methods=["GET"])
def api_patient_detail(ma_nguoi):
    """Thực thi Truy vấn 3A, 3B, 3C, 3D"""
    with engine.connect() as conn:
        info = conn.execute(text("""
            SELECT bn.ma_nguoi, bn.ma_benh_nhan, n.cmt, n.ho_ten, n.ngay_sinh, n.gioi_tinh, n.dia_chi, n.so_dien_thoai
            FROM BENH_NHAN bn JOIN NGUOI n ON n.ma_nguoi = bn.ma_nguoi
            WHERE bn.ma_nguoi = :id
        """), {"id": ma_nguoi}).mappings().first()

        q3a = rows_to_dicts(conn.execute(text("""
            SELECT bn.ma_benh_nhan, n.ho_ten, lk.ma_lan_kham, lk.thoi_diem_vao, lk.thoi_diem_ra,
                   b.ten_benh, d.ma_dot, d.trang_thai AS tinh_trang_dot,
                   ROW_NUMBER() OVER (PARTITION BY d.ma_dot ORDER BY lk.thoi_diem_vao, lk.ma_lan_kham) AS lan_thu_trong_dot,
                   bs.ma_bac_si, bs_n.ho_ten AS ten_bac_si, cd.phi_kham_chua, cd.ket_luan
            FROM BENH_NHAN bn JOIN NGUOI n ON n.ma_nguoi=bn.ma_nguoi
            JOIN LAN_KHAM lk ON lk.ma_benh_nhan=bn.ma_nguoi
            JOIN CHI_TIET_CHAN_DOAN cd ON cd.ma_lan_kham=lk.ma_lan_kham
            JOIN DOT_DIEU_TRI d ON d.ma_dot=cd.ma_dot
            JOIN BENH b ON b.ma_benh=d.ma_benh
            JOIN BAC_SI bs ON bs.ma_bac_si=cd.ma_bac_si
            JOIN NGUOI bs_n ON bs_n.ma_nguoi=bs.ma_nguoi
            WHERE bn.ma_nguoi=:id
            ORDER BY lk.thoi_diem_vao, b.ten_benh
        """), {"id": ma_nguoi}))

        q3b = rows_to_dicts(conn.execute(text("""
            SELECT bn.ma_benh_nhan, n.ho_ten, b.ten_benh, d.ma_dot,
                   COUNT(cd.ma_lan_kham) AS so_lan_kham,
                   MAX(lk.thoi_diem_vao) AS lan_kham_gan_nhat
            FROM BENH_NHAN bn JOIN NGUOI n ON n.ma_nguoi=bn.ma_nguoi
            JOIN DOT_DIEU_TRI d ON d.ma_benh_nhan=bn.ma_nguoi
            JOIN BENH b ON b.ma_benh=d.ma_benh
            JOIN CHI_TIET_CHAN_DOAN cd ON cd.ma_dot=d.ma_dot
            JOIN LAN_KHAM lk ON lk.ma_lan_kham=cd.ma_lan_kham
            WHERE bn.ma_nguoi=:id AND d.trang_thai='DANG_DIEU_TRI'
            GROUP BY bn.ma_benh_nhan,n.ho_ten,b.ten_benh,d.ma_dot
            ORDER BY b.ten_benh
        """), {"id": ma_nguoi}))

        q3c = rows_to_dicts(conn.execute(text("""
            SELECT lk.ma_lan_kham, lk.thoi_diem_vao, yt.ma_nguoi AS ma_y_ta,
                   n.ho_ten AS ten_y_ta, h.vai_tro, h.thoi_diem, h.ghi_chu
            FROM LAN_KHAM lk JOIN Y_TA_HO_TRO h ON h.ma_lan_kham=lk.ma_lan_kham
            JOIN Y_TA yt ON yt.ma_nguoi=h.ma_y_ta JOIN NGUOI n ON n.ma_nguoi=yt.ma_nguoi
            WHERE lk.ma_benh_nhan=:id
            ORDER BY lk.thoi_diem_vao,h.thoi_diem
        """), {"id": ma_nguoi}))

        q3d = rows_to_dicts(conn.execute(text("""
            SELECT lk.ma_lan_kham, lk.thoi_diem_vao, d.ma_don, d.ngay_ke, d.trang_thai,
                   t.ten_thuoc, ct.so_luong, ct.don_gia_tai_thoi_diem,
                   ct.so_luong*ct.don_gia_tai_thoi_diem AS thanh_tien, ct.huong_dan_dung
            FROM LAN_KHAM lk JOIN DON_THUOC d ON d.ma_lan_kham=lk.ma_lan_kham
            JOIN CT_DON_THUOC ct ON ct.ma_don=d.ma_don JOIN THUOC t ON t.ma_thuoc=ct.ma_thuoc
            WHERE lk.ma_benh_nhan=:id
            ORDER BY lk.thoi_diem_vao,d.ma_don,t.ten_thuoc
        """), {"id": ma_nguoi}))

    return jsonify({
        "info": dict(info) if info else {},
        "history_3a": q3a,
        "open_episodes_3b": q3b,
        "nurse_events_3c": q3c,
        "prescriptions_3d": q3d
    })