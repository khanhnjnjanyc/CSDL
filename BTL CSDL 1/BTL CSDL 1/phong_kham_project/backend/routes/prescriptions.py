"""Blueprint quản lý Đơn thuốc và Chi tiết đơn thuốc (Màn hình 5 & Tính năng phụ #8)."""
from datetime import datetime
from flask import Blueprint, jsonify, request
from sqlalchemy import text

from backend.database import (
    describe_db_error,
    engine,
    rows_to_dicts,
)

prescriptions_bp = Blueprint("prescriptions", __name__)


# ==============================================================================
# MÀN HÌNH 5 & TÍNH NĂNG PHỤ #8: ĐƠN THUỐC
# ==============================================================================
@prescriptions_bp.route("/api/prescriptions", methods=["GET", "POST"])
def api_prescriptions():
    """
    GET: Lấy danh sách tất cả các đơn thuốc, kèm chi tiết từng dòng thuốc và tổng tiền.
    POST: Kê đơn thuốc nhiều dòng trong Transaction.
          Bắt buộc kiểm tra: mảng items hợp lệ, số lượng > 0 (nguyên dương).
          Tự động lấy giá hiện hành từ bảng THUOC chốt giá vào dòng đơn (CT_DON_THUOC),
          tuyệt đối không tin tưởng tổng tiền do client tính sẵn.
    """
    if request.method == "GET":
        with engine.connect() as conn:
            dons = rows_to_dicts(
                conn.execute(
                    text("""
                SELECT d.ma_don, d.ma_lan_kham, lk.thoi_diem_vao, bn.ma_benh_nhan, n.ho_ten AS ten_benh_nhan,
                       d.ngay_ke, d.trang_thai, d.thoi_diem_cap,
                       COALESCE((SELECT SUM(ct.so_luong * ct.don_gia_tai_thoi_diem)
                                 FROM CT_DON_THUOC ct WHERE ct.ma_don = d.ma_don), 0) AS tong_tien
                FROM DON_THUOC d
                JOIN LAN_KHAM lk ON lk.ma_lan_kham = d.ma_lan_kham
                JOIN BENH_NHAN bn ON bn.ma_nguoi = lk.ma_benh_nhan
                JOIN NGUOI n ON n.ma_nguoi = bn.ma_nguoi
                ORDER BY d.ngay_ke DESC, d.ma_don DESC
            """)
                )
            )
            for d in dons:
                d["chi_tiet"] = rows_to_dicts(
                    conn.execute(
                        text("""
                    SELECT ct.ma_thuoc, t.ten_thuoc, t.don_vi, ct.so_luong, ct.don_gia_tai_thoi_diem,
                           (ct.so_luong * ct.don_gia_tai_thoi_diem) AS thanh_tien, ct.huong_dan_dung
                    FROM CT_DON_THUOC ct
                    JOIN THUOC t ON t.ma_thuoc = ct.ma_thuoc
                    WHERE ct.ma_don = :don
                    ORDER BY t.ten_thuoc
                """),
                        {"don": d["ma_don"]},
                    )
                )
        return jsonify(dons)

    # POST: Kê đơn thuốc nhiều dòng
    data = request.json or {}
    ma_lk = data.get("ma_lan_kham")
    if not ma_lk:
        return (
            jsonify({
                "success": False,
                "message": "Thiếu mã lượt khám kê đơn!",
                "error": "Thiếu mã lượt khám!",
            }),
            400,
        )

    items = data.get("items")
    # Kiểm tra mảng items
    if not items or not isinstance(items, list) or len(items) == 0:
        return (
            jsonify({
                "success": False,
                "message": "Số lượng thuốc không hợp lệ (phải > 0)!",
                "error": "Đơn thuốc phải có ít nhất 1 dòng thuốc!",
            }),
            400,
        )

    # Validate từng dòng thuốc trong items trước khi mở transaction
    for it in items:
        raw_qty = it.get("so_luong")
        try:
            # Kiểm tra phải là số nguyên
            val_float = float(raw_qty)
            val_int = int(raw_qty)
            if val_float != val_int or val_int <= 0:
                return (
                    jsonify({
                        "success": False,
                        "message": "Số lượng thuốc không hợp lệ (phải > 0)!",
                        "error": "Số lượng thuốc không hợp lệ (phải > 0)!",
                    }),
                    400,
                )
        except (ValueError, TypeError):
            return (
                jsonify({
                    "success": False,
                    "message": "Số lượng thuốc không hợp lệ (phải > 0)!",
                    "error": "Số lượng thuốc không hợp lệ (phải > 0)!",
                }),
                400,
            )

    raw_nk = data.get("ngay_ke") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ngay_ke = raw_nk.replace("T", " ")
    if len(ngay_ke) == 16:
        ngay_ke += ":00"

    trang_thai = data.get("trang_thai", "DA_CAP")
    thoi_diem_cap = ngay_ke if trang_thai == "DA_CAP" else None

    try:
        with engine.begin() as conn:
            # 1. Tạo đơn thuốc
            res_don = conn.execute(
                text("""
                INSERT INTO DON_THUOC (ma_lan_kham, ngay_ke, trang_thai, thoi_diem_cap)
                VALUES (:lk, :nk, :tt, :tdc)
            """),
                {
                    "lk": int(ma_lk),
                    "nk": ngay_ke,
                    "tt": trang_thai,
                    "tdc": thoi_diem_cap,
                },
            )
            ma_don = res_don.lastrowid

            tong_tien = 0.0

            # 2. Xử lý từng dòng thuốc: Tự động lấy gia_hien_hanh chốt giá
            for item in items:
                ma_thuoc = int(item["ma_thuoc"])
                so_luong = int(item["so_luong"])

                thuoc_row = conn.execute(
                    text("SELECT ten_thuoc, don_gia_hien_tai, ton_kho FROM THUOC WHERE ma_thuoc = :id"),
                    {"id": ma_thuoc},
                ).mappings().first()

                if not thuoc_row:
                    raise ValueError(f"Thuốc có mã #{ma_thuoc} không tồn tại trong danh mục!")

                # Tự động lấy giá hiện hành từ bảng THUOC để chốt giá (gia_chot), không tin tưởng giá FE gửi
                gia_chot = float(thuoc_row["don_gia_hien_tai"])
                thanh_tien = so_luong * gia_chot
                tong_tien += thanh_tien

                if trang_thai == "DA_CAP" and thuoc_row["ton_kho"] < so_luong:
                    raise ValueError(
                        f"Thuốc '{thuoc_row['ten_thuoc']}' không đủ tồn kho (Còn: {thuoc_row['ton_kho']}, yêu cầu: {so_luong})!"
                    )

                conn.execute(
                    text("""
                    INSERT INTO CT_DON_THUOC (ma_don, ma_thuoc, so_luong, don_gia_tai_thoi_diem, huong_dan_dung)
                    VALUES (:don, :thuoc, :sl, :gia, :hd)
                """),
                    {
                        "don": ma_don,
                        "thuoc": ma_thuoc,
                        "sl": so_luong,
                        "gia": gia_chot,
                        "hd": item.get("huong_dan_dung", "Theo chỉ dẫn của bác sĩ"),
                    },
                )

                if trang_thai == "DA_CAP":
                    conn.execute(
                        text("UPDATE THUOC SET ton_kho = ton_kho - :sl WHERE ma_thuoc = :id"),
                        {"sl": so_luong, "id": ma_thuoc},
                    )

        return jsonify({
            "success": True,
            "message": f"Đã tạo đơn thuốc #{ma_don} thành công!",
            "ma_don": ma_don,
            "tong_tien": tong_tien,
        })
    except ValueError as ve:
        err_msg = str(ve)
        status = 409 if "tồn kho" in err_msg else 400
        return jsonify({"success": False, "message": err_msg, "error": err_msg}), status
    except Exception as e:
        status, msg = describe_db_error(e)
        return jsonify({"success": False, "message": msg, "error": msg}), status


@prescriptions_bp.route("/api/prescriptions/<int:ma_don>", methods=["GET"])
def api_get_prescription(ma_don):
    """Lấy thông tin chi tiết một đơn thuốc theo ID."""
    with engine.connect() as conn:
        don = conn.execute(
            text("""
            SELECT d.ma_don, d.ma_lan_kham, lk.thoi_diem_vao, bn.ma_benh_nhan, n.ho_ten AS ten_benh_nhan,
                   d.ngay_ke, d.trang_thai, d.thoi_diem_cap,
                   COALESCE((SELECT SUM(ct.so_luong * ct.don_gia_tai_thoi_diem)
                             FROM CT_DON_THUOC ct WHERE ct.ma_don = d.ma_don), 0) AS tong_tien
            FROM DON_THUOC d
            JOIN LAN_KHAM lk ON lk.ma_lan_kham = d.ma_lan_kham
            JOIN BENH_NHAN bn ON bn.ma_nguoi = lk.ma_benh_nhan
            JOIN NGUOI n ON n.ma_nguoi = bn.ma_nguoi
            WHERE d.ma_don = :don
        """),
            {"don": ma_don},
        ).mappings().first()

        if not don:
            return jsonify({"success": False, "message": f"Không tìm thấy đơn thuốc #{ma_don}!", "error": "404"}), 404

        don_dict = dict(don)
        don_dict["chi_tiet"] = rows_to_dicts(
            conn.execute(
                text("""
            SELECT ct.ma_thuoc, t.ten_thuoc, t.don_vi, ct.so_luong, ct.don_gia_tai_thoi_diem,
                   (ct.so_luong * ct.don_gia_tai_thoi_diem) AS thanh_tien, ct.huong_dan_dung
            FROM CT_DON_THUOC ct
            JOIN THUOC t ON t.ma_thuoc = ct.ma_thuoc
            WHERE ct.ma_don = :don
            ORDER BY t.ten_thuoc
        """),
                {"don": ma_don},
            )
        )

    return jsonify({"success": True, "prescription": don_dict, **don_dict})


@prescriptions_bp.route("/api/prescriptions/<int:ma_don>/status", methods=["PUT"])
def api_prescription_status(ma_don):
    """Cập nhật trạng thái đơn thuốc (DA_CAP, HUY, DA_KE). Hỗ trợ hủy đơn & hoàn kho."""
    data = request.json or {}
    new_status = data.get("trang_thai")
    if not new_status:
        return jsonify({"success": False, "message": "Thiếu trạng thái cập nhật!", "error": "400"}), 400

    new_status = new_status.upper()
    if new_status not in ("DA_CAP", "DA_KE", "HUY"):
        return jsonify({
            "success": False,
            "message": f"Trạng thái '{new_status}' không hợp lệ! Chỉ chấp nhận: DA_CAP, DA_KE, HUY.",
            "error": "Trạng thái không hợp lệ!",
        }), 400

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Theo ràng buộc ck_don_cap: Nếu trang_thai != 'DA_CAP' thì thoi_diem_cap BẮT BUỘC phải là NULL
    tdc = data.get("thoi_diem_cap", now_str).replace("T", " ") if new_status == "DA_CAP" else None
    if tdc and len(tdc) == 16:
        tdc += ":00"

    try:
        with engine.begin() as conn:
            # Kiểm tra trạng thái hiện tại
            cur_don = conn.execute(
                text("SELECT trang_thai FROM DON_THUOC WHERE ma_don = :don"),
                {"don": ma_don},
            ).mappings().first()
            if not cur_don:
                return jsonify({"success": False, "message": "Đơn thuốc không tồn tại!", "error": "404"}), 404

            prev_status = cur_don["trang_thai"]

            # TRƯỜNG HỢP 1: Xác nhận cấp thuốc từ trạng thái chưa cấp (DA_KE/HUY) -> trừ tồn kho
            if new_status == "DA_CAP" and prev_status != "DA_CAP":
                lines = conn.execute(
                    text("SELECT ma_thuoc, so_luong FROM CT_DON_THUOC WHERE ma_don = :don"),
                    {"don": ma_don},
                ).fetchall()
                # Kiểm tra tồn kho trước khi trừ
                for line in lines:
                    cur_stock = conn.execute(
                        text("SELECT ten_thuoc, ton_kho FROM THUOC WHERE ma_thuoc = :id"),
                        {"id": line.ma_thuoc},
                    ).mappings().first()
                    if cur_stock and cur_stock["ton_kho"] < line.so_luong:
                        raise ValueError(
                            f"Thuốc '{cur_stock['ten_thuoc']}' không đủ tồn kho (Còn: {cur_stock['ton_kho']}, yêu cầu: {line.so_luong})!"
                        )
                for line in lines:
                    conn.execute(
                        text("UPDATE THUOC SET ton_kho = ton_kho - :sl WHERE ma_thuoc = :id"),
                        {"sl": line.so_luong, "id": line.ma_thuoc},
                    )

            # TRƯỜNG HỢP 2: Hủy đơn thuốc (hoặc quay về DA_KE) từ trạng thái đã cấp (DA_CAP) -> hoàn tồn kho
            elif new_status in ("HUY", "DA_KE") and prev_status == "DA_CAP":
                lines = conn.execute(
                    text("SELECT ma_thuoc, so_luong FROM CT_DON_THUOC WHERE ma_don = :don"),
                    {"don": ma_don},
                ).fetchall()
                for line in lines:
                    conn.execute(
                        text("UPDATE THUOC SET ton_kho = ton_kho + :sl WHERE ma_thuoc = :id"),
                        {"sl": line.so_luong, "id": line.ma_thuoc},
                    )

            conn.execute(
                text("""
                UPDATE DON_THUOC SET trang_thai = :tt, thoi_diem_cap = :tdc WHERE ma_don = :don
            """),
                {"tt": new_status, "tdc": tdc, "don": ma_don},
            )

        msg = (
            f"Đã hủy đơn thuốc #{ma_don} và hoàn trả thuốc về kho thành công!"
            if new_status == "HUY" and prev_status == "DA_CAP"
            else f"Đã cập nhật trạng thái đơn #{ma_don} sang {new_status}!"
        )

        return jsonify({
            "success": True,
            "message": msg,
            "ma_don": ma_don,
            "trang_thai": new_status,
        })
    except ValueError as ve:
        return jsonify({"success": False, "message": str(ve), "error": str(ve)}), 409
    except Exception as e:
        status, msg = describe_db_error(e)
        return jsonify({"success": False, "message": msg, "error": msg}), status


@prescriptions_bp.route("/api/prescriptions/<int:ma_don>", methods=["DELETE"])
def api_delete_prescription(ma_don):
    """Xóa hoàn toàn đơn thuốc. Nếu đơn đang ở DA_CAP thì hoàn lại tồn kho trước khi xóa."""
    try:
        with engine.begin() as conn:
            cur_don = conn.execute(
                text("SELECT trang_thai FROM DON_THUOC WHERE ma_don = :don"),
                {"don": ma_don},
            ).mappings().first()
            if not cur_don:
                return jsonify({"success": False, "message": "Đơn thuốc không tồn tại!", "error": "404"}), 404

            # Nếu đã cấp thuốc thì hoàn kho
            if cur_don["trang_thai"] == "DA_CAP":
                lines = conn.execute(
                    text("SELECT ma_thuoc, so_luong FROM CT_DON_THUOC WHERE ma_don = :don"),
                    {"don": ma_don},
                ).fetchall()
                for line in lines:
                    conn.execute(
                        text("UPDATE THUOC SET ton_kho = ton_kho + :sl WHERE ma_thuoc = :id"),
                        {"sl": line.so_luong, "id": line.ma_thuoc},
                    )

            # Xóa chi tiết và đơn thuốc
            conn.execute(text("DELETE FROM CT_DON_THUOC WHERE ma_don = :don"), {"don": ma_don})
            conn.execute(text("DELETE FROM DON_THUOC WHERE ma_don = :don"), {"don": ma_don})

        return jsonify({
            "success": True,
            "message": f"Đã xóa hoàn toàn đơn thuốc #{ma_don}!",
        })
    except Exception as e:
        status, msg = describe_db_error(e)
        return jsonify({"success": False, "message": msg, "error": msg}), status
