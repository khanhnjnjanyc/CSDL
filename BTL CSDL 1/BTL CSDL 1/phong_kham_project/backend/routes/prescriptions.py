from datetime import datetime
from flask import Blueprint, request, jsonify
from sqlalchemy import text
from backend.database import engine, rows_to_dicts, translate_db_error

prescriptions_bp = Blueprint("prescriptions", __name__)

@prescriptions_bp.route("/api/prescriptions", methods=["GET", "POST"])
def api_prescriptions():
    if request.method == "GET":
        with engine.connect() as conn:
            dons = rows_to_dicts(conn.execute(text("""
                SELECT d.ma_don, d.ma_lan_kham, lk.thoi_diem_vao, bn.ma_benh_nhan, n.ho_ten AS ten_benh_nhan,
                       d.ngay_ke, d.trang_thai, d.thoi_diem_cap,
                       COALESCE((SELECT SUM(ct.so_luong * ct.don_gia_tai_thoi_diem) FROM CT_DON_THUOC ct WHERE ct.ma_don = d.ma_don), 0) AS tong_tien
                FROM DON_THUOC d
                JOIN LAN_KHAM lk ON lk.ma_lan_kham = d.ma_lan_kham
                JOIN BENH_NHAN bn ON bn.ma_nguoi = lk.ma_benh_nhan
                JOIN NGUOI n ON n.ma_nguoi = bn.ma_nguoi
                ORDER BY d.ngay_ke DESC, d.ma_don DESC
            """)))
            for d in dons:
                d["chi_tiet"] = rows_to_dicts(conn.execute(text("""
                    SELECT ct.ma_thuoc, t.ten_thuoc, t.don_vi, ct.so_luong, ct.don_gia_tai_thoi_diem,
                           (ct.so_luong * ct.don_gia_tai_thoi_diem) AS thanh_tien, ct.huong_dan_dung
                    FROM CT_DON_THUOC ct
                    JOIN THUOC t ON t.ma_thuoc = ct.ma_thuoc
                    WHERE ct.ma_don = :don
                """), {"don": d["ma_don"]}))
        return jsonify(dons)

    data = request.json
    items = data.get("items", [])
    if not items:
        return jsonify({"error": "Đơn thuốc phải có ít nhất 1 dòng thuốc!"}), 400

    ngay_ke = data["ngay_ke"].replace("T", " ")
    if len(ngay_ke) == 16:
        ngay_ke += ":00"
    trang_thai = data.get("trang_thai", "DA_CAP")
    thoi_diem_cap = ngay_ke if trang_thai == "DA_CAP" else None

    try:
        with engine.begin() as conn:
            res_don = conn.execute(text("""
                INSERT INTO DON_THUOC (ma_lan_kham, ngay_ke, trang_thai, thoi_diem_cap)
                VALUES (:lk, :nk, :tt, :tdc)
            """), {"lk": int(data["ma_lan_kham"]), "nk": ngay_ke, "tt": trang_thai, "tdc": thoi_diem_cap})
            ma_don = res_don.lastrowid

            for item in items:
                ma_thuoc = int(item["ma_thuoc"])
                so_luong = int(item["so_luong"])
                if so_luong <= 0:
                    raise ValueError("Lỗi R1: Số lượng thuốc phải lớn hơn 0!")

                thuoc_row = conn.execute(
                    text("SELECT ten_thuoc, don_gia_hien_tai, ton_kho FROM THUOC WHERE ma_thuoc=:id"),
                    {"id": ma_thuoc}
                ).mappings().first()
                if not thuoc_row:
                    raise ValueError("Thuốc không tồn tại!")
                if trang_thai == "DA_CAP" and thuoc_row["ton_kho"] < so_luong:
                    raise ValueError(f"Thuốc '{thuoc_row['ten_thuoc']}' không đủ tồn kho (Còn: {thuoc_row['ton_kho']})!")

                don_gia = float(item.get("don_gia_tai_thoi_diem") or thuoc_row["don_gia_hien_tai"])
                conn.execute(text("""
                    INSERT INTO CT_DON_THUOC (ma_don, ma_thuoc, so_luong, don_gia_tai_thoi_diem, huong_dan_dung)
                    VALUES (:don, :thuoc, :sl, :gia, :hd)
                """), {
                    "don": ma_don, "thuoc": ma_thuoc, "sl": so_luong,
                    "gia": don_gia, "hd": item.get("huong_dan_dung", "Theo chỉ dẫn")
                })

                if trang_thai == "DA_CAP":
                    conn.execute(
                        text("UPDATE THUOC SET ton_kho = ton_kho - :sl WHERE ma_thuoc = :id"),
                        {"sl": so_luong, "id": ma_thuoc}
                    )
        return jsonify({"message": f"Đã tạo đơn thuốc #{ma_don} thành công!", "ma_don": ma_don})
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": translate_db_error(e)}), 400


@prescriptions_bp.route("/api/prescriptions/<int:ma_don>/status", methods=["PUT"])
def api_prescription_status(ma_don):
    data = request.json
    new_status = data["trang_thai"]
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tdc = data.get("thoi_diem_cap", now_str).replace("T", " ") if new_status == "DA_CAP" else None
    if tdc and len(tdc) == 16:
        tdc += ":00"
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE DON_THUOC SET trang_thai = :tt, thoi_diem_cap = :tdc WHERE ma_don = :don
            """), {"tt": new_status, "tdc": tdc, "don": ma_don})
        return jsonify({"message": f"Đã cập nhật trạng thái đơn #{ma_don} sang {new_status}!"})
    except Exception as e:
        return jsonify({"error": translate_db_error(e)}), 400