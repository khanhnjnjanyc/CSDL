"""Blueprint quản lý Nhân viên (Bác sĩ, Y tá) và Danh mục (Bệnh, Thuốc, Chuyên môn)."""
from flask import Blueprint, jsonify, request
from sqlalchemy import text

from backend.database import (
    describe_db_error,
    engine,
    rows_to_dicts,
    translate_db_error,
)

staff_catalog_bp = Blueprint("staff_catalog", __name__)


# ==============================================================================
# MÀN HÌNH 6 & TÍNH NĂNG PHỤ #2: QUẢN LÝ NHÂN VIÊN (BÁC SĨ & Y TÁ)
# ==============================================================================
@staff_catalog_bp.route("/api/staff", methods=["GET", "POST"])
def api_staff():
    """
    GET: Lấy danh sách nhân viên, hỗ trợ lọc theo role ('BAC_SI' / 'Y_TA') và từ khóa 'q'.
    POST: Thêm Bác sĩ hoặc Y tá mới (tạo đồng thời NGUOI, NHAN_VIEN và BAC_SI/Y_TA).
    """
    if request.method == "GET":
        role_filter = request.args.get("role", "").strip().upper()
        keyword = request.args.get("q", "").strip()

        with engine.connect() as conn:
            doctors = []
            if not role_filter or role_filter == "BAC_SI":
                sql_bs = """
                    SELECT n.ma_nguoi, n.cmt, n.ho_ten, n.ngay_sinh, n.gioi_tinh, n.dia_chi, n.so_dien_thoai,
                           nv.ma_nhan_vien, nv.ngay_vao_lam, nv.trang_thai,
                           bs.ma_bac_si, bs.bac_nghe, bs.trinh_do_dao_tao, bs.tham_nien
                    FROM BAC_SI bs
                    JOIN NHAN_VIEN nv ON nv.ma_nguoi = bs.ma_nguoi
                    JOIN NGUOI n ON n.ma_nguoi = bs.ma_nguoi
                    ORDER BY bs.ma_bac_si
                """
                doctors = rows_to_dicts(conn.execute(text(sql_bs)))
                for d in doctors:
                    specs = rows_to_dicts(
                        conn.execute(
                            text("""
                        SELECT cm.ma_chuyen_mon, cm.ten_chuyen_mon
                        FROM BAC_SI_CHUYEN_MON bscm
                        JOIN CHUYEN_MON cm ON cm.ma_chuyen_mon = bscm.ma_chuyen_mon
                        WHERE bscm.ma_bac_si = :bs
                    """),
                            {"bs": d["ma_bac_si"]},
                        )
                    )
                    d["chuyen_mon"] = ", ".join([s["ten_chuyen_mon"] for s in specs])

                if keyword:
                    kw = keyword.lower()
                    doctors = [
                        d
                        for d in doctors
                        if kw in str(d["ma_bac_si"]).lower()
                        or kw in str(d["ma_nhan_vien"]).lower()
                        or kw in str(d["ho_ten"]).lower()
                        or kw in str(d.get("chuyen_mon", "")).lower()
                    ]

            nurses = []
            if not role_filter or role_filter == "Y_TA":
                sql_yt = """
                    SELECT n.ma_nguoi, n.cmt, n.ho_ten, n.ngay_sinh, n.gioi_tinh, n.dia_chi, n.so_dien_thoai,
                           nv.ma_nhan_vien, nv.ngay_vao_lam, nv.trang_thai,
                           yt.trinh_do, yt.tham_nien
                    FROM Y_TA yt
                    JOIN NHAN_VIEN nv ON nv.ma_nguoi = yt.ma_nguoi
                    JOIN NGUOI n ON n.ma_nguoi = yt.ma_nguoi
                    ORDER BY nv.ma_nhan_vien
                """
                nurses = rows_to_dicts(conn.execute(text(sql_yt)))
                if keyword:
                    kw = keyword.lower()
                    nurses = [
                        n
                        for n in nurses
                        if kw in str(n["ma_nhan_vien"]).lower()
                        or kw in str(n["ho_ten"]).lower()
                        or kw in str(n.get("trinh_do", "")).lower()
                    ]

        return jsonify({
            "success": True,
            "doctors": doctors,
            "nurses": nurses,
        })

    # POST: Thêm mới nhân viên
    data = request.json or {}
    loai = data.get("loai", "BAC_SI").upper()
    try:
        # Validate trường bắt buộc
        for f in ["cmt", "ho_ten", "ngay_sinh", "gioi_tinh", "ma_nhan_vien", "ngay_vao_lam"]:
            if not data.get(f) or not str(data.get(f)).strip():
                return jsonify({
                    "success": False,
                    "message": f"Thiếu thông tin bắt buộc: {f}!",
                    "error": f"Thiếu thông tin: {f}!",
                }), 400

        if loai == "BAC_SI" and not data.get("ma_bac_si"):
            return jsonify({
                "success": False,
                "message": "Thiếu mã bác sĩ!",
                "error": "Thiếu mã bác sĩ!",
            }), 400

        with engine.begin() as conn:
            res = conn.execute(
                text("""
                INSERT INTO NGUOI (cmt, ho_ten, ngay_sinh, gioi_tinh, dia_chi, so_dien_thoai)
                VALUES (:cmt, :ho_ten, :ngay_sinh, :gioi_tinh, :dia_chi, :sdt)
            """),
                {
                    "cmt": str(data["cmt"]).strip(),
                    "ho_ten": str(data["ho_ten"]).strip(),
                    "ngay_sinh": str(data["ngay_sinh"]).strip(),
                    "gioi_tinh": str(data["gioi_tinh"]).strip(),
                    "dia_chi": data.get("dia_chi", "Hà Nội"),
                    "sdt": data.get("so_dien_thoai", ""),
                },
            )
            ma_nguoi = res.lastrowid

            conn.execute(
                text("""
                INSERT INTO NHAN_VIEN (ma_nguoi, ma_nhan_vien, ngay_vao_lam, trang_thai)
                VALUES (:id, :mnv, :nvl, 'DANG_LAM')
            """),
                {
                    "id": ma_nguoi,
                    "mnv": str(data["ma_nhan_vien"]).strip(),
                    "nvl": str(data["ngay_vao_lam"]).strip(),
                },
            )

            if loai == "BAC_SI":
                conn.execute(
                    text("""
                    INSERT INTO BAC_SI (ma_nguoi, ma_bac_si, bac_nghe, trinh_do_dao_tao, tham_nien)
                    VALUES (:id, :mbs, :bn, :td, :tn)
                """),
                    {
                        "id": ma_nguoi,
                        "mbs": str(data["ma_bac_si"]).strip(),
                        "bn": data.get("bac_nghe", "Bác sĩ"),
                        "td": data.get("trinh_do_dao_tao", "Đại học"),
                        "tn": max(0, int(data.get("tham_nien", 0))),
                    },
                )
                # Gán chuyên môn nếu có
                cm_id = data.get("ma_chuyen_mon")
                if cm_id:
                    conn.execute(
                        text("""
                        INSERT INTO BAC_SI_CHUYEN_MON (ma_bac_si, ma_chuyen_mon)
                        VALUES (:mbs, :cm)
                    """),
                        {"mbs": str(data["ma_bac_si"]).strip(), "cm": int(cm_id)},
                    )
            else:
                conn.execute(
                    text("""
                    INSERT INTO Y_TA (ma_nguoi, trinh_do, tham_nien)
                    VALUES (:id, :td, :tn)
                """),
                    {
                        "id": ma_nguoi,
                        "td": data.get("trinh_do", "Cao đẳng"),
                        "tn": max(0, int(data.get("tham_nien", 0))),
                    },
                )

        msg = f"Đã thêm {'Bác sĩ' if loai=='BAC_SI' else 'Y tá'} mới thành công!"
        return jsonify({"success": True, "message": msg})
    except Exception as e:
        status, msg = describe_db_error(e)
        return jsonify({"success": False, "message": msg, "error": msg}), status


@staff_catalog_bp.route("/api/staff/<int:ma_nguoi>", methods=["PUT", "DELETE"])
def api_staff_detail(ma_nguoi):
    """PUT/DELETE nhân viên theo ma_nguoi."""
    if request.method == "PUT":
        data = request.json or {}
        try:
            with engine.begin() as conn:
                conn.execute(
                    text("""
                    UPDATE NGUOI
                    SET ho_ten = COALESCE(:ho_ten, ho_ten),
                        dia_chi = COALESCE(:dia_chi, dia_chi),
                        so_dien_thoai = COALESCE(:sdt, so_dien_thoai)
                    WHERE ma_nguoi = :id
                """),
                    {
                        "ho_ten": data.get("ho_ten"),
                        "dia_chi": data.get("dia_chi"),
                        "sdt": data.get("so_dien_thoai"),
                        "id": ma_nguoi,
                    },
                )
                if "tham_nien" in data:
                    conn.execute(
                        text("UPDATE BAC_SI SET tham_nien = :tn WHERE ma_nguoi = :id"),
                        {"tn": int(data["tham_nien"]), "id": ma_nguoi},
                    )
                    conn.execute(
                        text("UPDATE Y_TA SET tham_nien = :tn WHERE ma_nguoi = :id"),
                        {"tn": int(data["tham_nien"]), "id": ma_nguoi},
                    )
            return jsonify({"success": True, "message": "Đã cập nhật nhân viên thành công!"})
        except Exception as e:
            status, msg = describe_db_error(e)
            return jsonify({"success": False, "message": msg, "error": msg}), status

    # DELETE
    try:
        with engine.begin() as conn:
            # Kiểm tra xem bác sĩ có chẩn đoán hoặc y tá có sự kiện hỗ trợ không
            has_diag = conn.execute(
                text("""
                SELECT 1 FROM CHI_TIET_CHAN_DOAN cd
                JOIN BAC_SI bs ON bs.ma_bac_si = cd.ma_bac_si
                WHERE bs.ma_nguoi = :id LIMIT 1
            """),
                {"id": ma_nguoi},
            ).fetchone()
            if has_diag:
                return (
                    jsonify({
                        "success": False,
                        "message": "Không thể xóa bác sĩ đã có lịch sử khám chữa bệnh!",
                        "error": "Không thể xóa bác sĩ đã có lịch sử khám chữa bệnh!",
                    }),
                    409,
                )

            has_support = conn.execute(
                text("SELECT 1 FROM Y_TA_HO_TRO WHERE ma_y_ta = :id LIMIT 1"),
                {"id": ma_nguoi},
            ).fetchone()
            if has_support:
                return (
                    jsonify({
                        "success": False,
                        "message": "Không thể xóa y tá đã có sự kiện hỗ trợ khám bệnh!",
                        "error": "Không thể xóa y tá đã có sự kiện hỗ trợ khám bệnh!",
                    }),
                    409,
                )

            conn.execute(text("DELETE FROM BAC_SI_CHUYEN_MON WHERE ma_bac_si IN (SELECT ma_bac_si FROM BAC_SI WHERE ma_nguoi=:id)"), {"id": ma_nguoi})
            conn.execute(text("DELETE FROM BAC_SI WHERE ma_nguoi = :id"), {"id": ma_nguoi})
            conn.execute(text("DELETE FROM Y_TA WHERE ma_nguoi = :id"), {"id": ma_nguoi})
            conn.execute(text("DELETE FROM NHAN_VIEN WHERE ma_nguoi = :id"), {"id": ma_nguoi})
            conn.execute(text("DELETE FROM NGUOI WHERE ma_nguoi = :id"), {"id": ma_nguoi})

        return jsonify({"success": True, "message": "Đã xóa nhân viên thành công!"})
    except Exception as e:
        status, msg = describe_db_error(e)
        return jsonify({"success": False, "message": msg, "error": msg}), status


# ==============================================================================
# MÀN HÌNH 8 & TÍNH NĂNG PHỤ #3, #4, #9: DANH MỤC (BỆNH, THUỐC, CHUYÊN MÔN)
# ==============================================================================
@staff_catalog_bp.route("/api/catalog", methods=["GET"])
def api_catalog():
    """Lấy toàn bộ dữ liệu danh mục cho Màn hình 8."""
    with engine.connect() as conn:
        diseases = rows_to_dicts(conn.execute(text("SELECT * FROM BENH ORDER BY ma_benh")))
        medicines = rows_to_dicts(conn.execute(text("SELECT * FROM THUOC ORDER BY ma_thuoc")))
        specialties = rows_to_dicts(conn.execute(text("SELECT * FROM CHUYEN_MON ORDER BY ma_chuyen_mon")))
    return jsonify({
        "success": True,
        "diseases": diseases,
        "medicines": medicines,
        "specialties": specialties,
    })


# --- CRUD BỆNH (/api/diseases) ---
@staff_catalog_bp.route("/api/diseases", methods=["GET", "POST"])
def api_diseases():
    """GET: Tìm kiếm bệnh theo q (mã/tên). POST: Thêm bệnh mới."""
    if request.method == "GET":
        keyword = request.args.get("q", "").strip()
        with engine.connect() as conn:
            if keyword:
                diseases = rows_to_dicts(
                    conn.execute(
                        text("""
                        SELECT * FROM BENH
                        WHERE CAST(ma_benh AS TEXT) LIKE :q OR ten_benh LIKE :q
                        ORDER BY ma_benh
                    """),
                        {"q": f"%{keyword}%"},
                    )
                )
            else:
                diseases = rows_to_dicts(conn.execute(text("SELECT * FROM BENH ORDER BY ma_benh")))
        return jsonify(diseases)

    # POST: Thêm bệnh mới
    data = request.json or {}
    ten_benh = str(data.get("ten_benh", "")).strip()
    if not ten_benh:
        return jsonify({
            "success": False,
            "message": "Tên bệnh không được để trống!",
            "error": "Tên bệnh không được để trống!",
        }), 400

    try:
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO BENH (ten_benh, mo_ta) VALUES (:ten, :mt)"),
                {"ten": ten_benh, "mt": data.get("mo_ta", "")},
            )
        return jsonify({"success": True, "message": "Đã thêm danh mục bệnh thành công!"})
    except Exception as e:
        status, msg = describe_db_error(e)
        return jsonify({"success": False, "message": msg, "error": msg}), status


@staff_catalog_bp.route("/api/diseases/<int:ma_benh>", methods=["PUT", "DELETE"])
def api_mod_disease(ma_benh):
    """PUT/DELETE Danh mục bệnh theo ma_benh."""
    if request.method == "PUT":
        data = request.json or {}
        ten_benh = str(data.get("ten_benh", "")).strip()
        if not ten_benh:
            return jsonify({
                "success": False,
                "message": "Tên bệnh không được để trống!",
                "error": "Tên bệnh không được để trống!",
            }), 400

        try:
            with engine.begin() as conn:
                conn.execute(
                    text("UPDATE BENH SET ten_benh=:ten, mo_ta=:mt WHERE ma_benh=:id"),
                    {"ten": ten_benh, "mt": data.get("mo_ta", ""), "id": ma_benh},
                )
            return jsonify({"success": True, "message": "Đã cập nhật bệnh thành công!"})
        except Exception as e:
            status, msg = describe_db_error(e)
            return jsonify({"success": False, "message": msg, "error": msg}), status

    # DELETE
    try:
        with engine.begin() as conn:
            # Kiểm tra xem bệnh đã có trong đợt điều trị chưa
            has_dot = conn.execute(
                text("SELECT 1 FROM DOT_DIEU_TRI WHERE ma_benh = :id LIMIT 1"),
                {"id": ma_benh},
            ).fetchone()
            if has_dot:
                return (
                    jsonify({
                        "success": False,
                        "message": "Không thể xóa bệnh đang có trong hồ sơ điều trị!",
                        "error": "Không thể xóa bệnh đang có trong hồ sơ điều trị!",
                    }),
                    409,
                )

            conn.execute(text("DELETE FROM BENH WHERE ma_benh=:id"), {"id": ma_benh})
        return jsonify({"success": True, "message": "Đã xóa bệnh thành công!"})
    except Exception as e:
        status, msg = describe_db_error(e)
        return jsonify({"success": False, "message": msg, "error": msg}), status


# --- CRUD THUỐC (/api/medicines) ---
@staff_catalog_bp.route("/api/medicines", methods=["GET", "POST"])
def api_medicines():
    """GET: Lọc thuốc theo tên/mã. POST: Thêm thuốc mới (kiểm tra đơn giá > 0)."""
    if request.method == "GET":
        keyword = request.args.get("q", "").strip()
        with engine.connect() as conn:
            if keyword:
                medicines = rows_to_dicts(
                    conn.execute(
                        text("""
                        SELECT * FROM THUOC
                        WHERE CAST(ma_thuoc AS TEXT) LIKE :q OR ten_thuoc LIKE :q
                        ORDER BY ma_thuoc
                    """),
                        {"q": f"%{keyword}%"},
                    )
                )
            else:
                medicines = rows_to_dicts(conn.execute(text("SELECT * FROM THUOC ORDER BY ma_thuoc")))
        return jsonify(medicines)

    # POST: Thêm thuốc mới
    data = request.json or {}
    ten_thuoc = str(data.get("ten_thuoc", "")).strip()
    if not ten_thuoc:
        return jsonify({
            "success": False,
            "message": "Tên thuốc không được để trống!",
            "error": "Tên thuốc không được để trống!",
        }), 400

    # Lấy giá từ don_gia_hien_tai hoặc gia_hien_hanh
    raw_price = data.get("don_gia_hien_tai") if "don_gia_hien_tai" in data else data.get("gia_hien_hanh")
    try:
        gia = float(raw_price) if raw_price is not None else 0.0
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Lỗi R1: Đơn giá hiện hành của thuốc phải là số hợp lệ!",
            "error": "Lỗi R1: Đơn giá hiện hành của thuốc phải là số hợp lệ!",
        }), 400

    # Kiểm tra ràng buộc gia_hien_hanh > 0
    if gia <= 0:
        return jsonify({
            "success": False,
            "message": "Lỗi R1: Đơn giá hiện hành của thuốc phải lớn hơn 0!",
            "error": "Lỗi R1: Đơn giá hiện hành của thuốc phải lớn hơn 0!",
        }), 400

    try:
        ton_kho = max(0, int(data.get("ton_kho", 0)))
        with engine.begin() as conn:
            conn.execute(
                text("""
                INSERT INTO THUOC (ten_thuoc, don_vi, don_gia_hien_tai, ton_kho)
                VALUES (:ten, :dv, :gia, :tk)
            """),
                {
                    "ten": ten_thuoc,
                    "dv": str(data.get("don_vi", "viên")).strip(),
                    "gia": gia,
                    "tk": ton_kho,
                },
            )
        return jsonify({"success": True, "message": "Đã thêm thuốc mới thành công!"})
    except Exception as e:
        status, msg = describe_db_error(e)
        return jsonify({"success": False, "message": msg, "error": msg}), status


@staff_catalog_bp.route("/api/medicines/<int:ma_thuoc>", methods=["PUT", "DELETE"])
def api_mod_medicine(ma_thuoc):
    """PUT: Cập nhật giá & tồn kho thuốc (giá > 0). DELETE: Xóa thuốc (chặn nếu đã kê đơn)."""
    if request.method == "PUT":
        data = request.json or {}
        ten_thuoc = str(data.get("ten_thuoc", "")).strip()

        raw_price = data.get("don_gia_hien_tai") if "don_gia_hien_tai" in data else data.get("gia_hien_hanh")
        if raw_price is not None:
            try:
                gia = float(raw_price)
                if gia <= 0:
                    return jsonify({
                        "success": False,
                        "message": "Lỗi R1: Đơn giá hiện hành của thuốc phải lớn hơn 0!",
                        "error": "Lỗi R1: Đơn giá hiện hành của thuốc phải lớn hơn 0!",
                    }), 400
            except (ValueError, TypeError):
                return jsonify({
                    "success": False,
                    "message": "Lỗi R1: Đơn giá hiện hành phải là số hợp lệ!",
                    "error": "Lỗi R1: Đơn giá hiện hành phải là số hợp lệ!",
                }), 400
        else:
            gia = None

        try:
            with engine.begin() as conn:
                conn.execute(
                    text("""
                    UPDATE THUOC
                    SET ten_thuoc = COALESCE(:ten, ten_thuoc),
                        don_vi = COALESCE(:dv, don_vi),
                        don_gia_hien_tai = COALESCE(:gia, don_gia_hien_tai),
                        ton_kho = COALESCE(:tk, ton_kho)
                    WHERE ma_thuoc = :id
                """),
                    {
                        "ten": ten_thuoc if ten_thuoc else None,
                        "dv": data.get("don_vi"),
                        "gia": gia,
                        "tk": int(data["ton_kho"]) if "ton_kho" in data else None,
                        "id": ma_thuoc,
                    },
                )
            return jsonify({
                "success": True,
                "message": "Đã cập nhật giá hiện hành & tồn kho! Đơn cũ vẫn giữ nguyên giá chốt lịch sử.",
            })
        except Exception as e:
            status, msg = describe_db_error(e)
            return jsonify({"success": False, "message": msg, "error": msg}), status

    # DELETE
    try:
        with engine.begin() as conn:
            # Kiểm tra xem thuốc đã từng được kê trong CT_DON_THUOC chưa
            has_presc = conn.execute(
                text("SELECT 1 FROM CT_DON_THUOC WHERE ma_thuoc = :id LIMIT 1"),
                {"id": ma_thuoc},
            ).fetchone()
            if has_presc:
                return (
                    jsonify({
                        "success": False,
                        "message": "Mã đã tồn tại hoặc danh mục đang được sử dụng ở nơi khác, không thể xóa/sửa!",
                        "error": "Không thể xóa thuốc đã từng được kê đơn!",
                    }),
                    409,
                )

            conn.execute(text("DELETE FROM THUOC WHERE ma_thuoc=:id"), {"id": ma_thuoc})
        return jsonify({"success": True, "message": "Đã xóa thuốc thành công!"})
    except Exception as e:
        status, msg = describe_db_error(e)
        return jsonify({"success": False, "message": msg, "error": msg}), status
