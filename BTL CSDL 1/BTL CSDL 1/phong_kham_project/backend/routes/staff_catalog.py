from flask import Blueprint, request, jsonify
from sqlalchemy import text
from backend.database import engine, rows_to_dicts, translate_db_error

staff_catalog_bp = Blueprint("staff_catalog", __name__)

@staff_catalog_bp.route("/api/staff", methods=["GET", "POST"])
def api_staff():
    if request.method == "GET":
        with engine.connect() as conn:
            doctors = rows_to_dicts(conn.execute(text("""
                SELECT n.ma_nguoi, n.cmt, n.ho_ten, n.ngay_sinh, n.gioi_tinh, n.so_dien_thoai,
                       nv.ma_nhan_vien, nv.ngay_vao_lam, nv.trang_thai,
                       bs.ma_bac_si, bs.bac_nghe, bs.trinh_do_dao_tao, bs.tham_nien
                FROM BAC_SI bs
                JOIN NHAN_VIEN nv ON nv.ma_nguoi = bs.ma_nguoi
                JOIN NGUOI n ON n.ma_nguoi = bs.ma_nguoi
                ORDER BY bs.ma_bac_si
            """)))
            for d in doctors:
                specs = rows_to_dicts(conn.execute(text("""
                    SELECT cm.ma_chuyen_mon, cm.ten_chuyen_mon
                    FROM BAC_SI_CHUYEN_MON bscm
                    JOIN CHUYEN_MON cm ON cm.ma_chuyen_mon = bscm.ma_chuyen_mon
                    WHERE bscm.ma_bac_si = :bs
                """), {"bs": d["ma_bac_si"]}))
                d["chuyen_mon"] = ", ".join([s["ten_chuyen_mon"] for s in specs])

            nurses = rows_to_dicts(conn.execute(text("""
                SELECT n.ma_nguoi, n.cmt, n.ho_ten, n.ngay_sinh, n.gioi_tinh, n.so_dien_thoai,
                       nv.ma_nhan_vien, nv.ngay_vao_lam, nv.trang_thai,
                       yt.trinh_do, yt.tham_nien
                FROM Y_TA yt
                JOIN NHAN_VIEN nv ON nv.ma_nguoi = yt.ma_nguoi
                JOIN NGUOI n ON n.ma_nguoi = yt.ma_nguoi
                ORDER BY nv.ma_nhan_vien
            """)))
        return jsonify({"doctors": doctors, "nurses": nurses})

    data = request.json
    loai = data.get("loai", "BAC_SI")
    try:
        with engine.begin() as conn:
            res = conn.execute(text("""
                INSERT INTO NGUOI (cmt, ho_ten, ngay_sinh, gioi_tinh, dia_chi, so_dien_thoai)
                VALUES (:cmt, :ho_ten, :ngay_sinh, :gioi_tinh, :dia_chi, :sdt)
            """), {
                "cmt": data["cmt"].strip(),
                "ho_ten": data["ho_ten"].strip(),
                "ngay_sinh": data["ngay_sinh"],
                "gioi_tinh": data["gioi_tinh"],
                "dia_chi": data.get("dia_chi", "Ha Noi"),
                "sdt": data.get("so_dien_thoai", "")
            })
            ma_nguoi = res.lastrowid

            conn.execute(text("""
                INSERT INTO NHAN_VIEN (ma_nguoi, ma_nhan_vien, ngay_vao_lam, trang_thai)
                VALUES (:id, :mnv, :nvl, 'DANG_LAM')
            """), {"id": ma_nguoi, "mnv": data["ma_nhan_vien"].strip(), "nvl": data["ngay_vao_lam"]})

            if loai == "BAC_SI":
                conn.execute(text("""
                    INSERT INTO BAC_SI (ma_nguoi, ma_bac_si, bac_nghe, trinh_do_dao_tao, tham_nien)
                    VALUES (:id, :mbs, :bn, :td, :tn)
                """), {
                    "id": ma_nguoi,
                    "mbs": data["ma_bac_si"].strip(),
                    "bn": data.get("bac_nghe", "Bac si"),
                    "td": data.get("trinh_do_dao_tao", "Dai hoc"),
                    "tn": int(data.get("tham_nien", 0))
                })
            else:
                conn.execute(text("""
                    INSERT INTO Y_TA (ma_nguoi, trinh_do, tham_nien)
                    VALUES (:id, :td, :tn)
                """), {"id": ma_nguoi, "td": data.get("trinh_do", "Cao dang"), "tn": int(data.get("tham_nien", 0))})
        return jsonify({"message": f"Đã thêm {'Bác sĩ' if loai=='BAC_SI' else 'Y tá'} mới!"})
    except Exception as e:
        return jsonify({"error": translate_db_error(e)}), 400


@staff_catalog_bp.route("/api/catalog", methods=["GET"])
def api_catalog():
    with engine.connect() as conn:
        diseases = rows_to_dicts(conn.execute(text("SELECT * FROM BENH ORDER BY ma_benh")))
        medicines = rows_to_dicts(conn.execute(text("SELECT * FROM THUOC ORDER BY ma_thuoc")))
        specialties = rows_to_dicts(conn.execute(text("SELECT * FROM CHUYEN_MON ORDER BY ma_chuyen_mon")))
    return jsonify({"diseases": diseases, "medicines": medicines, "specialties": specialties})


@staff_catalog_bp.route("/api/diseases", methods=["POST"])
def api_add_disease():
    data = request.json
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO BENH (ten_benh, mo_ta) VALUES (:ten, :mt)"),
                     {"ten": data["ten_benh"].strip(), "mt": data.get("mo_ta", "")})
    return jsonify({"message": "Đã thêm danh mục bệnh!"})


@staff_catalog_bp.route("/api/diseases/<int:ma_benh>", methods=["PUT", "DELETE"])
def api_mod_disease(ma_benh):
    if request.method == "PUT":
        data = request.json
        with engine.begin() as conn:
            conn.execute(text("UPDATE BENH SET ten_benh=:ten, mo_ta=:mt WHERE ma_benh=:id"),
                         {"ten": data["ten_benh"].strip(), "mt": data.get("mo_ta", ""), "id": ma_benh})
        return jsonify({"message": "Đã cập nhật bệnh!"})
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM BENH WHERE ma_benh=:id"), {"id": ma_benh})
        return jsonify({"message": "Đã xóa bệnh!"})
    except Exception:
        return jsonify({"error": "Không thể xóa bệnh đang có trong hồ sơ điều trị!"}), 400


@staff_catalog_bp.route("/api/medicines", methods=["POST"])
def api_add_medicine():
    data = request.json
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO THUOC (ten_thuoc, don_vi, don_gia_hien_tai, ton_kho)
                VALUES (:ten, :dv, :gia, :tk)
            """), {
                "ten": data["ten_thuoc"].strip(),
                "dv": data["don_vi"].strip(),
                "gia": float(data["don_gia_hien_tai"]),
                "tk": int(data["ton_kho"])
            })
        return jsonify({"message": "Đã thêm thuốc mới!"})
    except Exception as e:
        return jsonify({"error": translate_db_error(e)}), 400


@staff_catalog_bp.route("/api/medicines/<int:ma_thuoc>", methods=["PUT", "DELETE"])
def api_mod_medicine(ma_thuoc):
    if request.method == "PUT":
        data = request.json
        try:
            with engine.begin() as conn:
                conn.execute(text("""
                    UPDATE THUOC SET ten_thuoc=:ten, don_vi=:dv, don_gia_hien_tai=:gia, ton_kho=:tk
                    WHERE ma_thuoc=:id
                """), {
                    "ten": data["ten_thuoc"].strip(),
                    "dv": data["don_vi"].strip(),
                    "gia": float(data["don_gia_hien_tai"]),
                    "tk": int(data["ton_kho"]),
                    "id": ma_thuoc
                })
            return jsonify({"message": "Đã cập nhật giá hiện hành & tồn kho! Đơn cũ vẫn giữ nguyên giá chốt lịch sử."})
        except Exception as e:
            return jsonify({"error": translate_db_error(e)}), 400
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM THUOC WHERE ma_thuoc=:id"), {"id": ma_thuoc})
        return jsonify({"message": "Đã xóa thuốc!"})
    except Exception:
        return jsonify({"error": "Không thể xóa thuốc đã từng được kê đơn!"}), 400