import csv
import io
from flask import Blueprint, request, jsonify, Response
from sqlalchemy import text
from backend.database import engine, get_month_bounds, rows_to_dicts

reports_bp = Blueprint("reports", __name__)

# Trong file backend/routes/reports.py, thay thế hàm api_reports() bằng đoạn sau:
@reports_bp.route("/api/reports", methods=["GET"])
def api_reports():
    month = request.args.get("month", "2026-10")
    d_start, d_end, dt_start, dt_end = get_month_bounds(month)

    with engine.connect() as conn:
        # Truy vấn 1: Thống kê bệnh trong tháng
        q1_diseases = rows_to_dicts(conn.execute(text("""
            SELECT b.ma_benh, b.ten_benh,
                   COUNT(DISTINCT d.ma_dot) AS so_dot_mac,
                   COUNT(DISTINCT d.ma_benh_nhan) AS so_benh_nhan
            FROM LAN_KHAM lk
            JOIN CHI_TIET_CHAN_DOAN cd ON cd.ma_lan_kham = lk.ma_lan_kham
            JOIN DOT_DIEU_TRI d ON d.ma_dot = cd.ma_dot
            JOIN BENH b ON b.ma_benh = d.ma_benh
            WHERE lk.thoi_diem_vao >= :dt1
              AND lk.thoi_diem_vao < :dt2
            GROUP BY b.ma_benh, b.ten_benh
            ORDER BY so_benh_nhan DESC, so_dot_mac DESC, b.ten_benh
        """), {"dt1": dt_start, "dt2": dt_end}))

        # Danh sách bệnh nhân & đợt khám làm căn cứ cho từng bệnh ở Truy vấn 1
        q1_evidence = rows_to_dicts(conn.execute(text("""
            SELECT DISTINCT b.ma_benh, b.ten_benh, bn.ma_nguoi, bn.ma_benh_nhan, n.ho_ten,
                   d.ma_dot, d.ngay_bat_dau, d.trang_thai,
                   COUNT(cd.ma_lan_kham) AS so_luot_trong_thang
            FROM LAN_KHAM lk
            JOIN CHI_TIET_CHAN_DOAN cd ON cd.ma_lan_kham = lk.ma_lan_kham
            JOIN DOT_DIEU_TRI d ON d.ma_dot = cd.ma_dot
            JOIN BENH b ON b.ma_benh = d.ma_benh
            JOIN BENH_NHAN bn ON bn.ma_nguoi = d.ma_benh_nhan
            JOIN NGUOI n ON n.ma_nguoi = bn.ma_nguoi
            WHERE lk.thoi_diem_vao >= :dt1 AND lk.thoi_diem_vao < :dt2
            GROUP BY b.ma_benh, b.ten_benh, bn.ma_nguoi, bn.ma_benh_nhan, n.ho_ten, d.ma_dot, d.ngay_bat_dau, d.trang_thai
            ORDER BY b.ma_benh, bn.ma_benh_nhan
        """), {"dt1": dt_start, "dt2": dt_end}))

        # Truy vấn 2: Tính lương Bác sĩ & Y tá
        q2_payroll = rows_to_dicts(conn.execute(text("""
            WITH bs_thuong AS (
              SELECT cd.ma_bac_si, COUNT(*) AS so_dot_khoi
              FROM DOT_DIEU_TRI d
              JOIN CHI_TIET_CHAN_DOAN cd
                ON cd.ma_lan_kham = d.ma_lan_kham_ket_thuc AND cd.ma_dot = d.ma_dot
              WHERE d.trang_thai = 'KHOI'
                AND d.ngay_ket_thuc >= :d1 AND d.ngay_ket_thuc < :d2
              GROUP BY cd.ma_bac_si
            ), yt_thuong AS (
              SELECT ma_y_ta, COUNT(*) AS so_su_kien
              FROM Y_TA_HO_TRO
              WHERE thoi_diem >= :dt1 AND thoi_diem < :dt2
              GROUP BY ma_y_ta
            )
            SELECT 'BAC_SI' AS loai, nv.ma_nhan_vien, bs.ma_bac_si AS ma_chuyen_biet,
                   n.ho_ten, 7000000 AS luong_co_ban,
                   COALESCE(t.so_dot_khoi,0) AS so_su_kien,
                   1000000 * COALESCE(t.so_dot_khoi,0) AS tien_thuong,
                   7000000 + 1000000 * COALESCE(t.so_dot_khoi,0) AS tong_luong
            FROM BAC_SI bs JOIN NHAN_VIEN nv ON nv.ma_nguoi=bs.ma_nguoi
            JOIN NGUOI n ON n.ma_nguoi=bs.ma_nguoi
            LEFT JOIN bs_thuong t ON t.ma_bac_si=bs.ma_bac_si
            WHERE nv.trang_thai='DANG_LAM' OR COALESCE(t.so_dot_khoi,0)>0
            UNION ALL
            SELECT 'Y_TA', nv.ma_nhan_vien, CAST(yt.ma_nguoi AS CHAR),
                   n.ho_ten, 5000000,
                   COALESCE(t.so_su_kien,0),
                   200000 * COALESCE(t.so_su_kien,0),
                   5000000 + 200000 * COALESCE(t.so_su_kien,0)
            FROM Y_TA yt JOIN NHAN_VIEN nv ON nv.ma_nguoi=yt.ma_nguoi
            JOIN NGUOI n ON n.ma_nguoi=yt.ma_nguoi
            LEFT JOIN yt_thuong t ON t.ma_y_ta=yt.ma_nguoi
            WHERE nv.trang_thai='DANG_LAM' OR COALESCE(t.so_su_kien,0)>0
            ORDER BY loai, ma_nhan_vien
        """), {"d1": d_start, "d2": d_end, "dt1": dt_start, "dt2": dt_end}))

        q2_bs_evidence = rows_to_dicts(conn.execute(text("""
            SELECT d.ma_dot, bn.ma_benh_nhan, n_bn.ho_ten AS ten_benh_nhan, b.ten_benh,
                   d.ngay_ket_thuc, d.ma_lan_kham_ket_thuc, cd.ma_bac_si, n_bs.ho_ten AS ten_bac_si
            FROM DOT_DIEU_TRI d
            JOIN CHI_TIET_CHAN_DOAN cd ON cd.ma_lan_kham = d.ma_lan_kham_ket_thuc AND cd.ma_dot = d.ma_dot
            JOIN BENH_NHAN bn ON bn.ma_nguoi = d.ma_benh_nhan
            JOIN NGUOI n_bn ON n_bn.ma_nguoi = bn.ma_nguoi
            JOIN BENH b ON b.ma_benh = d.ma_benh
            JOIN BAC_SI bs ON bs.ma_bac_si = cd.ma_bac_si
            JOIN NGUOI n_bs ON n_bs.ma_nguoi = bs.ma_nguoi
            WHERE d.trang_thai = 'KHOI' AND d.ngay_ket_thuc >= :d1 AND d.ngay_ket_thuc < :d2
            ORDER BY d.ngay_ket_thuc
        """), {"d1": d_start, "d2": d_end}))

        q2_yt_evidence = rows_to_dicts(conn.execute(text("""
            SELECT h.ma_ho_tro, h.ma_lan_kham, h.ma_y_ta, n.ho_ten AS ten_y_ta, h.vai_tro, h.thoi_diem, h.ghi_chu
            FROM Y_TA_HO_TRO h
            JOIN NGUOI n ON n.ma_nguoi = h.ma_y_ta
            WHERE h.thoi_diem >= :dt1 AND h.thoi_diem < :dt2
            ORDER BY h.ma_y_ta, h.thoi_diem
        """), {"dt1": dt_start, "dt2": dt_end}))

        # Truy vấn 4: Doanh thu
        q4_summary = conn.execute(text("""
            SELECT kham.doanh_thu_kham_chua, thuoc.doanh_thu_thuoc,
                   kham.doanh_thu_kham_chua+thuoc.doanh_thu_thuoc AS tong_doanh_thu
            FROM (
              SELECT COALESCE(SUM(cd.phi_kham_chua),0) AS doanh_thu_kham_chua
              FROM CHI_TIET_CHAN_DOAN cd JOIN LAN_KHAM lk ON lk.ma_lan_kham=cd.ma_lan_kham
              WHERE lk.thoi_diem_vao >= :dt1 AND lk.thoi_diem_vao < :dt2
            ) kham
            CROSS JOIN (
              SELECT COALESCE(SUM(ct.so_luong*ct.don_gia_tai_thoi_diem),0) AS doanh_thu_thuoc
              FROM CT_DON_THUOC ct JOIN DON_THUOC d ON d.ma_don=ct.ma_don
              JOIN LAN_KHAM lk ON lk.ma_lan_kham=d.ma_lan_kham
              WHERE d.trang_thai = 'DA_CAP'
                AND d.thoi_diem_cap >= :dt1 AND d.thoi_diem_cap < :dt2
            ) thuoc
        """), {"dt1": dt_start, "dt2": dt_end}).mappings().first()

        q4_exam_lines = rows_to_dicts(conn.execute(text("""
            SELECT lk.ma_lan_kham, lk.thoi_diem_vao, bn.ma_benh_nhan, n.ho_ten AS ten_benh_nhan,
                   b.ten_benh, cd.ma_dot, cd.ma_bac_si, cd.phi_kham_chua
            FROM CHI_TIET_CHAN_DOAN cd
            JOIN LAN_KHAM lk ON lk.ma_lan_kham = cd.ma_lan_kham
            JOIN DOT_DIEU_TRI d ON d.ma_dot = cd.ma_dot
            JOIN BENH b ON b.ma_benh = d.ma_benh
            JOIN BENH_NHAN bn ON bn.ma_nguoi = lk.ma_benh_nhan
            JOIN NGUOI n ON n.ma_nguoi = bn.ma_nguoi
            WHERE lk.thoi_diem_vao >= :dt1 AND lk.thoi_diem_vao < :dt2
            ORDER BY lk.thoi_diem_vao
        """), {"dt1": dt_start, "dt2": dt_end}))

        q4_med_lines = rows_to_dicts(conn.execute(text("""
            SELECT d.ma_don, d.ma_lan_kham, d.thoi_diem_cap, t.ten_thuoc,
                   ct.so_luong, ct.don_gia_tai_thoi_diem,
                   (ct.so_luong * ct.don_gia_tai_thoi_diem) AS thanh_tien
            FROM CT_DON_THUOC ct
            JOIN DON_THUOC d ON d.ma_don = ct.ma_don
            JOIN THUOC t ON t.ma_thuoc = ct.ma_thuoc
            WHERE d.trang_thai = 'DA_CAP' AND d.thoi_diem_cap >= :dt1 AND d.thoi_diem_cap < :dt2
            ORDER BY d.thoi_diem_cap, d.ma_don
        """), {"dt1": dt_start, "dt2": dt_end}))

    return jsonify({
        "month": month,
        "q1_diseases": q1_diseases,
        "q1_evidence": q1_evidence,
        "q2_payroll": q2_payroll,
        "q2_bs_evidence": q2_bs_evidence,
        "q2_yt_evidence": q2_yt_evidence,
        "q4_summary": dict(q4_summary) if q4_summary else {},
        "q4_exam_lines": q4_exam_lines,
        "q4_med_lines": q4_med_lines
    })


@reports_bp.route("/api/export/<string:report_type>", methods=["GET"])
def api_export_csv(report_type):
    month = request.args.get("month", "2026-10")
    d_start, d_end, dt_start, dt_end = get_month_bounds(month)

    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output)

    with engine.connect() as conn:
        if report_type == "payroll":
            writer.writerow(["Loai NV", "Ma NV", "Ma Chuyen Biet", "Ho Ten", "Luong Co Ban", "So Ca Thuong", "Tien Thuong", "Tong Luong"])
            rows = conn.execute(text("""
                WITH bs_thuong AS (
                  SELECT cd.ma_bac_si, COUNT(*) AS so_dot_khoi
                  FROM DOT_DIEU_TRI d JOIN CHI_TIET_CHAN_DOAN cd ON cd.ma_lan_kham = d.ma_lan_kham_ket_thuc AND cd.ma_dot = d.ma_dot
                  WHERE d.trang_thai = 'KHOI' AND d.ngay_ket_thuc >= :d1 AND d.ngay_ket_thuc < :d2
                  GROUP BY cd.ma_bac_si
                ), yt_thuong AS (
                  SELECT ma_y_ta, COUNT(*) AS so_su_kien FROM Y_TA_HO_TRO
                  WHERE thoi_diem >= :dt1 AND thoi_diem < :dt2 GROUP BY ma_y_ta
                )
                SELECT 'BAC_SI', nv.ma_nhan_vien, bs.ma_bac_si, n.ho_ten, 7000000, COALESCE(t.so_dot_khoi,0),
                       1000000 * COALESCE(t.so_dot_khoi,0), 7000000 + 1000000 * COALESCE(t.so_dot_khoi,0)
                FROM BAC_SI bs JOIN NHAN_VIEN nv ON nv.ma_nguoi=bs.ma_nguoi JOIN NGUOI n ON n.ma_nguoi=bs.ma_nguoi
                LEFT JOIN bs_thuong t ON t.ma_bac_si=bs.ma_bac_si
                UNION ALL
                SELECT 'Y_TA', nv.ma_nhan_vien, '', n.ho_ten, 5000000, COALESCE(t.so_su_kien,0),
                       200000 * COALESCE(t.so_su_kien,0), 5000000 + 200000 * COALESCE(t.so_su_kien,0)
                FROM Y_TA yt JOIN NHAN_VIEN nv ON nv.ma_nguoi=yt.ma_nguoi JOIN NGUOI n ON n.ma_nguoi=yt.ma_nguoi
                LEFT JOIN yt_thuong t ON t.ma_y_ta=yt.ma_nguoi
            """), {"d1": d_start, "d2": d_end, "dt1": dt_start, "dt2": dt_end}).fetchall()
            for r in rows:
                writer.writerow(list(r))
            filename = f"bang_luong_{month}.csv"

        elif report_type == "diseases":
            writer.writerow(["Ma Benh", "Ten Benh", "So Dot Mac", "So Benh Nhan Duy Nhat"])
            rows = conn.execute(text("""
                SELECT b.ma_benh, b.ten_benh, COUNT(DISTINCT d.ma_dot) AS so_dot_mac, COUNT(DISTINCT d.ma_benh_nhan) AS so_benh_nhan
                FROM LAN_KHAM lk JOIN CHI_TIET_CHAN_DOAN cd ON cd.ma_lan_kham = lk.ma_lan_kham
                JOIN DOT_DIEU_TRI d ON d.ma_dot = cd.ma_dot JOIN BENH b ON b.ma_benh = d.ma_benh
                WHERE lk.thoi_diem_vao >= :dt1 AND lk.thoi_diem_vao < :dt2
                GROUP BY b.ma_benh, b.ten_benh ORDER BY so_dot_mac DESC, so_benh_nhan DESC
            """), {"dt1": dt_start, "dt2": dt_end}).fetchall()
            for r in rows:
                writer.writerow(list(r))
            filename = f"thong_ke_benh_{month}.csv"

        else:
            writer.writerow(["Loai Giao Dich", "Ma Tham Chieu", "Thoi Diem", "Ten Hang Muc", "So Tien"])
            exam_rows = conn.execute(text("""
                SELECT 'KHAM_CHUA_BENH', lk.ma_lan_kham, lk.thoi_diem_vao, b.ten_benh, cd.phi_kham_chua
                FROM CHI_TIET_CHAN_DOAN cd JOIN LAN_KHAM lk ON lk.ma_lan_kham = cd.ma_lan_kham
                JOIN DOT_DIEU_TRI d ON d.ma_dot = cd.ma_dot JOIN BENH b ON b.ma_benh = d.ma_benh
                WHERE lk.thoi_diem_vao >= :dt1 AND lk.thoi_diem_vao < :dt2
            """), {"dt1": dt_start, "dt2": dt_end}).fetchall()
            for r in exam_rows:
                writer.writerow(list(r))

            med_rows = conn.execute(text("""
                SELECT 'CAP_THUOC', d.ma_don, d.thoi_diem_cap, t.ten_thuoc, (ct.so_luong * ct.don_gia_tai_thoi_diem)
                FROM CT_DON_THUOC ct JOIN DON_THUOC d ON d.ma_don = ct.ma_don JOIN THUOC t ON t.ma_thuoc = ct.ma_thuoc
                WHERE d.trang_thai = 'DA_CAP' AND d.thoi_diem_cap >= :dt1 AND d.thoi_diem_cap < :dt2
            """), {"dt1": dt_start, "dt2": dt_end}).fetchall()
            for r in med_rows:
                writer.writerow(list(r))
            filename = f"doanh_thu_{month}.csv"

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )