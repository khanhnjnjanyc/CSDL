from flask import Blueprint, request, jsonify
from sqlalchemy import text
from backend.database import engine, rows_to_dicts, translate_db_error

visits_episodes_bp = Blueprint("visits_episodes", __name__)

def _create_or_link_diagnosis(conn, ma_lan_kham, ma_benh_nhan, ngay_kham, data):
    """Xử lý tạo mới hoặc nối vào Episode đang mở trong cùng một Transaction"""
    mode = data.get("episode_mode", "AUTO")
    ma_benh = int(data["ma_benh"])
    ma_dot = data.get("ma_dot")

    if mode == "EXISTING" and ma_dot:
        ma_dot = int(ma_dot)
    elif mode == "NEW":
        res_dot = conn.execute(text("""
            INSERT INTO DOT_DIEU_TRI (ma_benh_nhan, ma_benh, ngay_bat_dau)
            VALUES (:bn, :benh, :ngay)
        """), {"bn": ma_benh_nhan, "benh": ma_benh, "ngay": ngay_kham})
        ma_dot = res_dot.lastrowid
    else:
        existing = conn.execute(text("""
            SELECT ma_dot FROM DOT_DIEU_TRI
            WHERE ma_benh_nhan = :bn AND ma_benh = :benh AND trang_thai = 'DANG_DIEU_TRI'
        """), {"bn": ma_benh_nhan, "benh": ma_benh}).scalar()
        if existing:
            ma_dot = existing
        else:
            res_dot = conn.execute(text("""
                INSERT INTO DOT_DIEU_TRI (ma_benh_nhan, ma_benh, ngay_bat_dau)
                VALUES (:bn, :benh, :ngay)
            """), {"bn": ma_benh_nhan, "benh": ma_benh, "ngay": ngay_kham})
            ma_dot = res_dot.lastrowid

    conn.execute(text("""
        INSERT INTO CHI_TIET_CHAN_DOAN (ma_lan_kham, ma_dot, ma_bac_si, phi_kham_chua, ket_luan)
        VALUES (:lk, :dot, :bs, :phi, :kl)
    """), {
        "lk": ma_lan_kham,
        "dot": ma_dot,
        "bs": data["ma_bac_si"],
        "phi": float(data.get("phi_kham_chua", 150000)),
        "kl": data.get("ket_luan", "")
    })

    if data.get("ket_thuc_khoi"):
        conn.execute(text("""
            UPDATE DOT_DIEU_TRI
            SET trang_thai = 'KHOI', ngay_ket_thuc = :ngay, ma_lan_kham_ket_thuc = :lk
            WHERE ma_dot = :dot
        """), {"ngay": ngay_kham, "lk": ma_lan_kham, "dot": ma_dot})


@visits_episodes_bp.route("/api/visits", methods=["GET", "POST"])
def api_visits():
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
                v["chan_doan"] = rows_to_dicts(conn.execute(text("""
                    SELECT cd.ma_dot, d.ma_benh, b.ten_benh, d.trang_thai, cd.ma_bac_si, n.ho_ten AS ten_bac_si,
                           cd.phi_kham_chua, cd.ket_luan
                    FROM CHI_TIET_CHAN_DOAN cd
                    JOIN DOT_DIEU_TRI d ON d.ma_dot = cd.ma_dot
                    JOIN BENH b ON b.ma_benh = d.ma_benh
                    JOIN BAC_SI bs ON bs.ma_bac_si = cd.ma_bac_si
                    JOIN NGUOI n ON n.ma_nguoi = bs.ma_nguoi
                    WHERE cd.ma_lan_kham = :lk
                """), {"lk": v["ma_lan_kham"]}))
                v["ho_tro"] = rows_to_dicts(conn.execute(text("""
                    SELECT h.ma_ho_tro, h.ma_y_ta, n.ho_ten AS ten_y_ta, h.vai_tro, h.thoi_diem, h.ghi_chu
                    FROM Y_TA_HO_TRO h
                    JOIN NGUOI n ON n.ma_nguoi = h.ma_y_ta
                    WHERE h.ma_lan_kham = :lk
                    ORDER BY h.thoi_diem
                """), {"lk": v["ma_lan_kham"]}))
        return jsonify(visits)

    data = request.json
    try:
        with engine.begin() as conn:
            vao = data["thoi_diem_vao"].replace("T", " ")
            if len(vao) == 16:
                vao += ":00"
            ra = data.get("thoi_diem_ra")
            if ra:
                ra = ra.replace("T", " ")
                if len(ra) == 16:
                    ra += ":00"
            else:
                ra = None

            res_lk = conn.execute(text("""
                INSERT INTO LAN_KHAM (ma_benh_nhan, thoi_diem_vao, thoi_diem_ra, ghi_chu)
                VALUES (:bn, :vao, :ra, :gc)
            """), {"bn": int(data["ma_benh_nhan"]), "vao": vao, "ra": ra, "gc": data.get("ghi_chu", "")})
            ma_lan_kham = res_lk.lastrowid

            if data.get("ma_benh") and data.get("ma_bac_si"):
                _create_or_link_diagnosis(conn, ma_lan_kham, int(data["ma_benh_nhan"]), vao[:10], data)

        return jsonify({"message": f"Đã tiếp nhận lượt khám #{ma_lan_kham}!", "ma_lan_kham": ma_lan_kham})
    except Exception as e:
        return jsonify({"error": translate_db_error(e)}), 400


@visits_episodes_bp.route("/api/visits/<int:ma_lan_kham>/checkout", methods=["PUT"])
def api_visit_checkout(ma_lan_kham):
    data = request.json
    ra = data["thoi_diem_ra"].replace("T", " ")
    if len(ra) == 16:
        ra += ":00"
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE LAN_KHAM SET thoi_diem_ra = :ra, ghi_chu = COALESCE(:gc, ghi_chu)
                WHERE ma_lan_kham = :lk
            """), {"ra": ra, "gc": data.get("ghi_chu"), "lk": ma_lan_kham})
        return jsonify({"message": "Đã cập nhật thời điểm ra viện!"})
    except Exception as e:
        return jsonify({"error": translate_db_error(e)}), 400


@visits_episodes_bp.route("/api/visits/<int:ma_lan_kham>/diagnoses", methods=["POST"])
def api_add_diagnosis(ma_lan_kham):
    data = request.json
    try:
        with engine.begin() as conn:
            lk = conn.execute(
                text("SELECT ma_benh_nhan, thoi_diem_vao FROM LAN_KHAM WHERE ma_lan_kham=:lk"),
                {"lk": ma_lan_kham}
            ).mappings().first()
            if not lk:
                return jsonify({"error": "Không tìm thấy lượt khám!"}), 404
            _create_or_link_diagnosis(conn, ma_lan_kham, lk["ma_benh_nhan"], str(lk["thoi_diem_vao"])[:10], data)
        return jsonify({"message": "Đã thêm bệnh/chẩn đoán vào lượt khám!"})
    except Exception as e:
        return jsonify({"error": translate_db_error(e)}), 400


@visits_episodes_bp.route("/api/visits/<int:ma_lan_kham>/nurse-support", methods=["POST"])
def api_add_nurse_support(ma_lan_kham):
    data = request.json
    td = data["thoi_diem"].replace("T", " ")
    if len(td) == 16:
        td += ":00"
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO Y_TA_HO_TRO (ma_lan_kham, ma_y_ta, vai_tro, thoi_diem, ghi_chu)
                VALUES (:lk, :yt, :vt, :td, :gc)
            """), {
                "lk": ma_lan_kham,
                "yt": int(data["ma_y_ta"]),
                "vt": data["vai_tro"].strip(),
                "td": td,
                "gc": data.get("ghi_chu", "")
            })
        return jsonify({"message": "Đã ghi nhận sự kiện y tá hỗ trợ (+200.000đ thưởng)!"})
    except Exception as e:
        return jsonify({"error": translate_db_error(e)}), 400


@visits_episodes_bp.route("/api/episodes", methods=["GET"])
def api_episodes():
    status = request.args.get("status", "")
    sql = """
        SELECT d.ma_dot, d.ma_benh_nhan, bn.ma_benh_nhan AS ma_bn_code, n.ho_ten AS ten_benh_nhan,
               d.ma_benh, b.ten_benh, d.ngay_bat_dau, d.ngay_ket_thuc, d.trang_thai, d.ma_lan_kham_ket_thuc,
               COUNT(cd.ma_lan_kham) AS so_luot_kham,
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
    if status:
        sql += " AND d.trang_thai = :st"
        params["st"] = status
    sql += """
        GROUP BY d.ma_dot, d.ma_benh_nhan, bn.ma_benh_nhan, n.ho_ten,
                 d.ma_benh, b.ten_benh, d.ngay_bat_dau, d.ngay_ket_thuc, d.trang_thai, d.ma_lan_kham_ket_thuc
        ORDER BY d.trang_thai ASC, d.ngay_bat_dau DESC, d.ma_dot DESC
    """
    with engine.connect() as conn:
        episodes = rows_to_dicts(conn.execute(text(sql), params))
        for ep in episodes:
            ep["cac_luot"] = rows_to_dicts(conn.execute(text("""
                SELECT cd.ma_lan_kham, lk.thoi_diem_vao, cd.ma_bac_si, n.ho_ten AS ten_bac_si,
                       cd.phi_kham_chua, cd.ket_luan,
                       ROW_NUMBER() OVER (ORDER BY lk.thoi_diem_vao, lk.ma_lan_kham) AS stt_luot
                FROM CHI_TIET_CHAN_DOAN cd
                JOIN LAN_KHAM lk ON lk.ma_lan_kham = cd.ma_lan_kham
                JOIN BAC_SI bs ON bs.ma_bac_si = cd.ma_bac_si
                JOIN NGUOI n ON n.ma_nguoi = bs.ma_nguoi
                WHERE cd.ma_dot = :dot
                ORDER BY lk.thoi_diem_vao, lk.ma_lan_kham
            """), {"dot": ep["ma_dot"]}))
    return jsonify(episodes)


@visits_episodes_bp.route("/api/episodes/<int:ma_dot>/cure", methods=["PUT"])
def api_cure_episode(ma_dot):
    data = request.json
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE DOT_DIEU_TRI
                SET trang_thai = 'KHOI',
                    ngay_ket_thuc = :ngay,
                    ma_lan_kham_ket_thuc = :lk
                WHERE ma_dot = :dot
            """), {
                "ngay": data["ngay_ket_thuc"],
                "lk": int(data["ma_lan_kham_ket_thuc"]),
                "dot": ma_dot
            })
        return jsonify({"message": f"Đã kết thúc KHỎI đợt #{ma_dot}! Bác sĩ tại lượt kết thúc được cộng 1.000.000đ thưởng."})
    except Exception as e:
        return jsonify({"error": translate_db_error(e)}), 400