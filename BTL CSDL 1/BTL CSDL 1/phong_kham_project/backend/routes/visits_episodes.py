"""Blueprint quản lý Lượt khám (Màn hình 3) và Episode điều trị (Màn hình 4)."""
from datetime import datetime
from flask import Blueprint, jsonify, request
from sqlalchemy import text

from backend.database import (
    describe_db_error,
    engine,
    rows_to_dicts,
)

visits_episodes_bp = Blueprint("visits_episodes", __name__)


def _create_or_link_diagnosis(conn, ma_lan_kham, ma_benh_nhan, ngay_kham, data):
    """
    Xử lý tạo mới hoặc nối vào Episode trong cùng một Transaction:
    - Kiểm tra bác sĩ phụ trách.
    - Kiểm tra nếu nối vào Episode đã đóng -> chặn lại và báo lỗi.
    - Lưu chi tiết chẩn đoán vào CHI_TIET_CHAN_DOAN.
    """
    doctor_id = data.get("doctor_id") or data.get("ma_bac_si")
    if not doctor_id or not str(doctor_id).strip():
        raise ValueError("Thiếu bác sĩ phụ trách lượt khám!")

    ma_bac_si = str(doctor_id).strip()
    ma_benh = data.get("ma_benh")
    if not ma_benh:
        raise ValueError("Thiếu thông tin bệnh chẩn đoán!")
    ma_benh = int(ma_benh)

    # Xác định Episode (đợt điều trị)
    mode = data.get("episode_mode", "AUTO").upper()
    explicit_ep = data.get("episode_id") or data.get("ma_dot")

    if explicit_ep:
        ma_dot = int(explicit_ep)
        # Kiểm tra trạng thái của episode
        ep_row = conn.execute(
            text("SELECT ma_dot, ma_benh_nhan, trang_thai FROM DOT_DIEU_TRI WHERE ma_dot = :dot"),
            {"dot": ma_dot},
        ).mappings().first()
        if not ep_row:
            raise ValueError(f"Episode #{ma_dot} không tồn tại!")
        if ep_row["trang_thai"] in ("KHOI", "CLOSED", "DA_KHOI", "DA_DONG"):
            raise ValueError("Episode điều trị đã đóng, không thể nối thêm lượt khám!")
        if ep_row["ma_benh_nhan"] != ma_benh_nhan:
            raise ValueError("Lỗi R5: Lượt khám và đợt điều trị phải thuộc cùng một bệnh nhân!")
    elif mode == "NEW":
        res_dot = conn.execute(
            text("""
            INSERT INTO DOT_DIEU_TRI (ma_benh_nhan, ma_benh, ngay_bat_dau)
            VALUES (:bn, :benh, :ngay)
        """),
            {"bn": ma_benh_nhan, "benh": ma_benh, "ngay": ngay_kham},
        )
        ma_dot = res_dot.lastrowid
    else:
        # AUTO hoặc EXISTING: tìm đợt đang mở của bệnh nhân với bệnh này
        existing = conn.execute(
            text("""
            SELECT ma_dot FROM DOT_DIEU_TRI
            WHERE ma_benh_nhan = :bn AND ma_benh = :benh AND trang_thai = 'DANG_DIEU_TRI'
            LIMIT 1
        """),
            {"bn": ma_benh_nhan, "benh": ma_benh},
        ).scalar()
        if existing:
            ma_dot = existing
        else:
            res_dot = conn.execute(
                text("""
                INSERT INTO DOT_DIEU_TRI (ma_benh_nhan, ma_benh, ngay_bat_dau)
                VALUES (:bn, :benh, :ngay)
            """),
                {"bn": ma_benh_nhan, "benh": ma_benh, "ngay": ngay_kham},
            )
            ma_dot = res_dot.lastrowid

    # Lưu chi tiết chẩn đoán
    conn.execute(
        text("""
        INSERT INTO CHI_TIET_CHAN_DOAN (ma_lan_kham, ma_dot, ma_bac_si, phi_kham_chua, ket_luan)
        VALUES (:lk, :dot, :bs, :phi, :kl)
    """),
        {
            "lk": ma_lan_kham,
            "dot": ma_dot,
            "bs": ma_bac_si,
            "phi": float(data.get("phi_kham_chua", 150000)),
            "kl": str(data.get("ket_luan", "")),
        },
    )

    if data.get("ket_thuc_khoi"):
        conn.execute(
            text("""
            UPDATE DOT_DIEU_TRI
            SET trang_thai = 'KHOI', ngay_ket_thuc = :ngay, ma_lan_kham_ket_thuc = :lk
            WHERE ma_dot = :dot
        """),
            {"ngay": ngay_kham, "lk": ma_lan_kham, "dot": ma_dot},
        )

    return ma_dot


# ==============================================================================
# MÀN HÌNH 3 & TÍNH NĂNG PHỤ #5, #7, #9: LƯỢT KHÁM & Y TÁ HỖ TRỢ
# ==============================================================================
@visits_episodes_bp.route("/api/visits", methods=["GET", "POST"])
def api_visits():
    """
    GET: Danh sách lượt khám, kèm chẩn đoán và y tá hỗ trợ.
    POST: Tiếp nhận lượt khám mới trong Transaction.
          Bắt buộc kiểm tra có Bác sĩ phụ trách.
          Chặn nối vào Episode đã đóng.
    """
    if request.method == "GET":
        q = request.args.get("q", "").strip()
        sql = """
            SELECT lk.ma_lan_kham, lk.ma_benh_nhan, bn.ma_benh_nhan AS ma_bn_code, n.ho_ten AS ten_benh_nhan,
                   lk.thoi_diem_vao, lk.thoi_diem_ra, lk.ghi_chu
            FROM LAN_KHAM lk
            JOIN BENH_NHAN bn ON bn.ma_nguoi = lk.ma_benh_nhan
            JOIN NGUOI n ON n.ma_nguoi = bn.ma_nguoi
            WHERE 1=1
        """
        params = {}
        if q:
            sql += " AND (bn.ma_benh_nhan LIKE :q OR n.ho_ten LIKE :q OR lk.ghi_chu LIKE :q)"
            params["q"] = f"%{q}%"
        sql += " ORDER BY lk.thoi_diem_vao DESC, lk.ma_lan_kham DESC"

        with engine.connect() as conn:
            visits = rows_to_dicts(conn.execute(text(sql), params))
            for v in visits:
                v["chan_doan"] = rows_to_dicts(
                    conn.execute(
                        text("""
                    SELECT cd.ma_dot, d.ma_benh, b.ten_benh, d.trang_thai, cd.ma_bac_si, n.ho_ten AS ten_bac_si,
                           cd.phi_kham_chua, cd.ket_luan
                    FROM CHI_TIET_CHAN_DOAN cd
                    JOIN DOT_DIEU_TRI d ON d.ma_dot = cd.ma_dot
                    JOIN BENH b ON b.ma_benh = d.ma_benh
                    JOIN BAC_SI bs ON bs.ma_bac_si = cd.ma_bac_si
                    JOIN NGUOI n ON n.ma_nguoi = bs.ma_nguoi
                    WHERE cd.ma_lan_kham = :lk
                """),
                        {"lk": v["ma_lan_kham"]},
                    )
                )
                v["ho_tro"] = rows_to_dicts(
                    conn.execute(
                        text("""
                    SELECT h.ma_ho_tro, h.ma_y_ta, n.ho_ten AS ten_y_ta, h.vai_tro, h.thoi_diem, h.ghi_chu
                    FROM Y_TA_HO_TRO h
                    JOIN NGUOI n ON n.ma_nguoi = h.ma_y_ta
                    WHERE h.ma_lan_kham = :lk
                    ORDER BY h.thoi_diem
                """),
                        {"lk": v["ma_lan_kham"]},
                    )
                )
        return jsonify(visits)

    # POST: Tiếp nhận lượt khám
    data = request.json or {}
    ma_bn = data.get("ma_benh_nhan")
    if not ma_bn:
        return jsonify({
            "success": False,
            "message": "Thiếu mã bệnh nhân tiếp nhận!",
            "error": "Thiếu mã bệnh nhân!",
        }), 400

    doctor_id = data.get("doctor_id") or data.get("ma_bac_si")
    if not doctor_id or not str(doctor_id).strip():
        return jsonify({
            "success": False,
            "message": "Thiếu bác sĩ phụ trách lượt khám!",
            "error": "Thiếu bác sĩ phụ trách lượt khám!",
        }), 400

    raw_vao = data.get("thoi_diem_vao") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    vao = raw_vao.replace("T", " ")
    if len(vao) == 16:
        vao += ":00"

    raw_ra = data.get("thoi_diem_ra")
    if raw_ra:
        ra = raw_ra.replace("T", " ")
        if len(ra) == 16:
            ra += ":00"
        if ra < vao:
            return jsonify({
                "success": False,
                "message": "Lỗi R2: Thời điểm ra viện không được nhỏ hơn thời điểm vào khám!",
                "error": "Lỗi R2: Thời điểm ra viện không được nhỏ hơn thời điểm vào khám!",
            }), 400
    else:
        ra = None

    try:
        with engine.begin() as conn:
            # 1. Tạo lượt khám
            res_lk = conn.execute(
                text("""
                INSERT INTO LAN_KHAM (ma_benh_nhan, thoi_diem_vao, thoi_diem_ra, ghi_chu)
                VALUES (:bn, :vao, :ra, :gc)
            """),
                {
                    "bn": int(ma_bn),
                    "vao": vao,
                    "ra": ra,
                    "gc": data.get("ghi_chu", ""),
                },
            )
            ma_lan_kham = res_lk.lastrowid

            # 2. Xử lý Episode & Chẩn đoán
            if data.get("ma_benh") or data.get("episode_id"):
                _create_or_link_diagnosis(conn, ma_lan_kham, int(ma_bn), vao[:10], data)

        return jsonify({
            "success": True,
            "message": f"Đã tiếp nhận lượt khám #{ma_lan_kham} thành công!",
            "ma_lan_kham": ma_lan_kham,
        })
    except ValueError as ve:
        err_msg = str(ve)
        status = 409 if "đã đóng" in err_msg or "R5" in err_msg else 400
        return jsonify({"success": False, "message": err_msg, "error": err_msg}), status
    except Exception as e:
        status, msg = describe_db_error(e)
        return jsonify({"success": False, "message": msg, "error": msg}), status


@visits_episodes_bp.route("/api/visits/<int:ma_lan_kham>/discharge", methods=["PUT"])
@visits_episodes_bp.route("/api/visits/<int:ma_lan_kham>/checkout", methods=["PUT"])
def api_visit_discharge(ma_lan_kham):
    """Cập nhật thời điểm ra viện và ghi chú."""
    data = request.json or {}
    raw_ra = data.get("thoi_diem_ra") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ra = raw_ra.replace("T", " ")
    if len(ra) == 16:
        ra += ":00"

    try:
        with engine.begin() as conn:
            lk = conn.execute(
                text("SELECT thoi_diem_vao FROM LAN_KHAM WHERE ma_lan_kham = :lk"),
                {"lk": ma_lan_kham},
            ).mappings().first()
            if not lk:
                return jsonify({"success": False, "message": "Lượt khám không tồn tại!", "error": "404"}), 404

            if ra < str(lk["thoi_diem_vao"]):
                return jsonify({
                    "success": False,
                    "message": "Lỗi R2: Thời điểm ra viện không được nhỏ hơn thời điểm vào khám!",
                    "error": "Lỗi R2: Thời điểm ra viện không được nhỏ hơn thời điểm vào khám!",
                }), 400

            conn.execute(
                text("""
                UPDATE LAN_KHAM
                SET thoi_diem_ra = :ra, ghi_chu = COALESCE(:gc, ghi_chu)
                WHERE ma_lan_kham = :lk
            """),
                {"ra": ra, "gc": data.get("ghi_chu"), "lk": ma_lan_kham},
            )

        return jsonify({"success": True, "message": "Cập nhật thời điểm ra viện thành công!"})
    except Exception as e:
        status, msg = describe_db_error(e)
        return jsonify({"success": False, "message": msg, "error": msg}), status


@visits_episodes_bp.route("/api/visits/<int:ma_lan_kham>/nurses", methods=["POST"])
@visits_episodes_bp.route("/api/visits/<int:ma_lan_kham>/nurse-support", methods=["POST"])
def api_add_nurse_support(ma_lan_kham):
    """Ghi nhận y tá hỗ trợ vào lượt khám."""
    data = request.json or {}
    ma_y_ta = data.get("ma_y_ta")
    vai_tro = data.get("vai_tro", "Hỗ trợ khám")
    if not ma_y_ta:
        return jsonify({"success": False, "message": "Thiếu mã y tá!", "error": "Thiếu mã y tá!"}), 400

    raw_td = data.get("thoi_diem") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    td = raw_td.replace("T", " ")
    if len(td) == 16:
        td += ":00"

    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                INSERT INTO Y_TA_HO_TRO (ma_lan_kham, ma_y_ta, vai_tro, thoi_diem, ghi_chu)
                VALUES (:lk, :yt, :vt, :td, :gc)
            """),
                {
                    "lk": ma_lan_kham,
                    "yt": int(ma_y_ta),
                    "vt": str(vai_tro).strip(),
                    "td": td,
                    "gc": data.get("ghi_chu", ""),
                },
            )
        return jsonify({"success": True, "message": "Đã ghi nhận sự kiện y tá hỗ trợ (+200.000đ thưởng)!"})
    except Exception as e:
        status, msg = describe_db_error(e)
        return jsonify({"success": False, "message": msg, "error": msg}), status


# ==============================================================================
# MÀN HÌNH 4 & TÍNH NĂNG PHỤ #6: EPISODE ĐIỀU TRỊ
# ==============================================================================
@visits_episodes_bp.route("/api/episodes", methods=["GET"])
def api_episodes():
    """
    Danh sách Episode điều trị:
    Trả về mã episode, tên bệnh nhân, tên bệnh, đang ở lượt khám thứ mấy (so_luot_kham / luot_thu_may),
    và trạng thái hiện tại.
    """
    status_filter = request.args.get("status", "").strip().upper()
    sql = """
        SELECT d.ma_dot, d.ma_dot AS ma_episode, d.ma_benh_nhan, bn.ma_benh_nhan AS ma_bn_code, n.ho_ten AS ten_benh_nhan,
               d.ma_benh, b.ten_benh, d.ngay_bat_dau, d.ngay_ket_thuc, d.trang_thai, d.ma_lan_kham_ket_thuc,
               COUNT(cd.ma_lan_kham) AS so_luot_kham,
               COUNT(cd.ma_lan_kham) AS luot_thu_may,
               MAX(lk.ma_lan_kham) AS ma_lan_kham_moi_nhat,
               MAX(lk.thoi_diem_vao) AS lan_kham_moi_nhat
        FROM DOT_DIEU_TRI d
        JOIN BENH_NHAN bn ON bn.ma_nguoi = d.ma_benh_nhan
        JOIN NGUOI n ON n.ma_nguoi = bn.ma_nguoi
        JOIN BENH b ON b.ma_benh = d.ma_benh
        LEFT JOIN CHI_TIET_CHAN_DOAN cd ON cd.ma_dot = d.ma_dot
        LEFT JOIN LAN_KHAM lk ON lk.ma_lan_kham = cd.ma_lan_kham
        WHERE 1=1
    """
    params = {}
    if status_filter in ("KHOI", "CLOSED", "DA_KHOI", "DA_DONG"):
        sql += " AND d.trang_thai = 'KHOI'"
    elif status_filter in ("DANG_DIEU_TRI", "OPEN"):
        sql += " AND d.trang_thai = 'DANG_DIEU_TRI'"

    sql += """
        GROUP BY d.ma_dot, d.ma_benh_nhan, bn.ma_benh_nhan, n.ho_ten,
                 d.ma_benh, b.ten_benh, d.ngay_bat_dau, d.ngay_ket_thuc, d.trang_thai, d.ma_lan_kham_ket_thuc
        ORDER BY d.trang_thai ASC, d.ngay_bat_dau DESC, d.ma_dot DESC
    """
    with engine.connect() as conn:
        episodes = rows_to_dicts(conn.execute(text(sql), params))
        for ep in episodes:
            ep["cac_luot"] = rows_to_dicts(
                conn.execute(
                    text("""
                SELECT cd.ma_lan_kham, lk.thoi_diem_vao, cd.ma_bac_si, n.ho_ten AS ten_bac_si,
                       cd.phi_kham_chua, cd.ket_luan,
                       ROW_NUMBER() OVER (ORDER BY lk.thoi_diem_vao, lk.ma_lan_kham) AS stt_luot
                FROM CHI_TIET_CHAN_DOAN cd
                JOIN LAN_KHAM lk ON lk.ma_lan_kham = cd.ma_lan_kham
                JOIN BAC_SI bs ON bs.ma_bac_si = cd.ma_bac_si
                JOIN NGUOI n ON n.ma_nguoi = bs.ma_nguoi
                WHERE cd.ma_dot = :dot
                ORDER BY lk.thoi_diem_vao, lk.ma_lan_kham
            """),
                    {"dot": ep["ma_dot"]},
                )
            )
    return jsonify(episodes)


@visits_episodes_bp.route("/api/episodes/<int:ma_dot>/close", methods=["PUT"])
@visits_episodes_bp.route("/api/episodes/<int:ma_dot>/cure", methods=["PUT"])
def api_close_episode(ma_dot):
    """
    Kết thúc khỏi một Episode điều trị.
    Kiểm tra: Nếu Episode đã ở trạng thái đóng rồi mà gọi tiếp API đóng lần nữa
    thì trả thông báo 'Episode này đã kết thúc trước đó!'.
    """
    data = request.json or {}
    try:
        with engine.begin() as conn:
            ep = conn.execute(
                text("SELECT ma_dot, trang_thai, ngay_bat_dau FROM DOT_DIEU_TRI WHERE ma_dot = :dot"),
                {"dot": ma_dot},
            ).mappings().first()

            if not ep:
                return (
                    jsonify({"success": False, "message": "Episode không tồn tại!", "error": "404"}),
                    404,
                )

            # Kiểm tra đợt đã đóng chưa
            if ep["trang_thai"] in ("KHOI", "CLOSED", "DA_KHOI", "DA_DONG"):
                return (
                    jsonify({
                        "success": False,
                        "message": "Episode này đã kết thúc trước đó!",
                        "error": "Episode này đã kết thúc trước đó!",
                    }),
                    409,
                )

            # Lấy lượt khám kết thúc
            ma_lk_kt = data.get("ma_lan_kham_ket_thuc")
            if not ma_lk_kt:
                latest_lk = conn.execute(
                    text("""
                    SELECT cd.ma_lan_kham, lk.thoi_diem_vao
                    FROM CHI_TIET_CHAN_DOAN cd
                    JOIN LAN_KHAM lk ON lk.ma_lan_kham = cd.ma_lan_kham
                    WHERE cd.ma_dot = :dot
                    ORDER BY lk.thoi_diem_vao DESC, cd.ma_lan_kham DESC
                    LIMIT 1
                """),
                    {"dot": ma_dot},
                ).mappings().first()
                if latest_lk:
                    ma_lk_kt = latest_lk["ma_lan_kham"]
                else:
                    return (
                        jsonify({
                            "success": False,
                            "message": "Episode chưa có lượt khám chẩn đoán nào, không thể kết thúc!",
                            "error": "Chưa có lượt khám",
                        }),
                        400,
                    )

            ngay_kt = data.get("ngay_ket_thuc") or datetime.now().strftime("%Y-%m-%d")

            conn.execute(
                text("""
                UPDATE DOT_DIEU_TRI
                SET trang_thai = 'KHOI',
                    ngay_ket_thuc = :ngay,
                    ma_lan_kham_ket_thuc = :lk
                WHERE ma_dot = :dot
            """),
                {
                    "ngay": str(ngay_kt).strip(),
                    "lk": int(ma_lk_kt),
                    "dot": ma_dot,
                },
            )

        return jsonify({
            "success": True,
            "message": f"Đã kết thúc KHỎI Episode #{ma_dot} thành công! Bác sĩ tại lượt kết thúc được cộng 1.000.000đ thưởng.",
        })
    except Exception as e:
        status, msg = describe_db_error(e)
        return jsonify({"success": False, "message": msg, "error": msg}), status
