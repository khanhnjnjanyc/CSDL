"""Blueprint Báo cáo thống kê (Màn hình 7: Truy vấn lõi #1, #2, #4 và Xuất báo cáo CSV/XLSX/PDF)."""
import csv
import io
from flask import Blueprint, Response, jsonify, request
from sqlalchemy import text

from backend.database import engine, get_month_bounds, rows_to_dicts

reports_bp = Blueprint("reports", __name__)


# ==============================================================================
# HÀM TRUY VẤN LÕI DÙNG CHUNG (TƯƠNG THÍCH CẢ SQLITE VÀ MYSQL)
# ==============================================================================
def _query_diseases_report(conn, dt_start, dt_end):
    """Truy vấn 1: Thống kê bệnh theo tháng (dùng khoảng nửa mở [dt_start, dt_end))."""
    sql = """
        SELECT b.ma_benh, b.ten_benh,
               COUNT(DISTINCT d.ma_dot) AS so_dot_mac,
               COUNT(DISTINCT lk.ma_benh_nhan) AS so_benh_nhan,
               COUNT(DISTINCT lk.ma_benh_nhan) AS so_benh_nhan_duy_nhat
        FROM LAN_KHAM lk
        JOIN CHI_TIET_CHAN_DOAN cd ON cd.ma_lan_kham = lk.ma_lan_kham
        JOIN DOT_DIEU_TRI d ON d.ma_dot = cd.ma_dot
        JOIN BENH b ON b.ma_benh = d.ma_benh
        WHERE lk.thoi_diem_vao >= :dt1 AND lk.thoi_diem_vao < :dt2
        GROUP BY b.ma_benh, b.ten_benh
        ORDER BY so_dot_mac DESC, so_benh_nhan_duy_nhat DESC, b.ten_benh ASC
    """
    return rows_to_dicts(conn.execute(text(sql), {"dt1": dt_start, "dt2": dt_end}))


def _query_diseases_evidence(conn, dt_start, dt_end):
    """Danh sách đợt và bệnh nhân căn cứ cho Truy vấn 1."""
    sql = """
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
    """
    return rows_to_dicts(conn.execute(text(sql), {"dt1": dt_start, "dt2": dt_end}))


def _query_payroll_report(conn, d_start, d_end, dt_start, dt_end):
    """Truy vấn 2: Bảng lương Bác sĩ & Y tá theo tháng."""
    sql = """
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
               COALESCE(t.so_dot_khoi, 0) AS so_su_kien,
               COALESCE(t.so_dot_khoi, 0) AS so_ca_thuong,
               1000000 * COALESCE(t.so_dot_khoi, 0) AS tien_thuong,
               7000000 + 1000000 * COALESCE(t.so_dot_khoi, 0) AS tong_luong
        FROM BAC_SI bs
        JOIN NHAN_VIEN nv ON nv.ma_nguoi = bs.ma_nguoi
        JOIN NGUOI n ON n.ma_nguoi = bs.ma_nguoi
        LEFT JOIN bs_thuong t ON t.ma_bac_si = bs.ma_bac_si
        WHERE nv.trang_thai = 'DANG_LAM' OR COALESCE(t.so_dot_khoi, 0) > 0
        UNION ALL
        SELECT 'Y_TA' AS loai, nv.ma_nhan_vien, CAST(yt.ma_nguoi AS CHAR) AS ma_chuyen_biet,
               n.ho_ten, 5000000 AS luong_co_ban,
               COALESCE(t.so_su_kien, 0) AS so_su_kien,
               COALESCE(t.so_su_kien, 0) AS so_ca_thuong,
               200000 * COALESCE(t.so_su_kien, 0) AS tien_thuong,
               5000000 + 200000 * COALESCE(t.so_su_kien, 0) AS tong_luong
        FROM Y_TA yt
        JOIN NHAN_VIEN nv ON nv.ma_nguoi = yt.ma_nguoi
        JOIN NGUOI n ON n.ma_nguoi = yt.ma_nguoi
        LEFT JOIN yt_thuong t ON t.ma_y_ta = yt.ma_nguoi
        WHERE nv.trang_thai = 'DANG_LAM' OR COALESCE(t.so_su_kien, 0) > 0
        ORDER BY loai, ma_nhan_vien
    """
    return rows_to_dicts(conn.execute(text(sql), {
        "d1": d_start,
        "d2": d_end,
        "dt1": dt_start,
        "dt2": dt_end,
    }))


def _query_doctor_evidence(conn, d_start, d_end, ma_bac_si=None):
    """Căn cứ thưởng cho Bác sĩ (các đợt khỏi kết thúc trong tháng)."""
    sql = """
        SELECT d.ma_dot, bn.ma_benh_nhan, n_bn.ho_ten AS ten_benh_nhan, b.ten_benh,
               d.ngay_ket_thuc, d.ma_lan_kham_ket_thuc, cd.ma_bac_si, n_bs.ho_ten AS ten_bac_si
        FROM DOT_DIEU_TRI d
        JOIN CHI_TIET_CHAN_DOAN cd
          ON cd.ma_lan_kham = d.ma_lan_kham_ket_thuc AND cd.ma_dot = d.ma_dot
        JOIN BENH_NHAN bn ON bn.ma_nguoi = d.ma_benh_nhan
        JOIN NGUOI n_bn ON n_bn.ma_nguoi = bn.ma_nguoi
        JOIN BENH b ON b.ma_benh = d.ma_benh
        JOIN BAC_SI bs ON bs.ma_bac_si = cd.ma_bac_si
        JOIN NGUOI n_bs ON n_bs.ma_nguoi = bs.ma_nguoi
        WHERE d.trang_thai = 'KHOI' AND d.ngay_ket_thuc >= :d1 AND d.ngay_ket_thuc < :d2
    """
    params = {"d1": d_start, "d2": d_end}
    if ma_bac_si:
        sql += " AND (cd.ma_bac_si = :mbs OR bs.ma_bac_si = :mbs)"
        params["mbs"] = ma_bac_si
    sql += " ORDER BY d.ngay_ket_thuc"
    return rows_to_dicts(conn.execute(text(sql), params))


def _query_nurse_evidence(conn, dt_start, dt_end, ma_y_ta=None):
    """Căn cứ thưởng cho Y tá (các sự kiện hỗ trợ trong tháng)."""
    sql = """
        SELECT h.ma_ho_tro, h.ma_lan_kham, h.ma_y_ta, n.ho_ten AS ten_y_ta,
               h.vai_tro, h.thoi_diem, h.ghi_chu
        FROM Y_TA_HO_TRO h
        JOIN NGUOI n ON n.ma_nguoi = h.ma_y_ta
        WHERE h.thoi_diem >= :dt1 AND h.thoi_diem < :dt2
    """
    params = {"dt1": dt_start, "dt2": dt_end}
    if ma_y_ta:
        sql += " AND (h.ma_y_ta = :mye OR CAST(h.ma_y_ta AS CHAR) = :mye)"
        params["mye"] = str(ma_y_ta)
    sql += " ORDER BY h.thoi_diem"
    return rows_to_dicts(conn.execute(text(sql), params))


def _query_revenue_report(conn, dt_start, dt_end):
    """Truy vấn 4: Doanh thu theo tháng (tiền khám + tiền thuốc DA_CAP)."""
    # 1. Chi tiết dòng tiền khám
    sql_exam = """
        SELECT 'KHAM_CHUA_BENH' AS loai_giao_dich,
               lk.ma_lan_kham, lk.thoi_diem_vao, bn.ma_benh_nhan, n.ho_ten AS ten_benh_nhan,
               b.ten_benh, cd.ma_dot, cd.phi_kham_chua
        FROM CHI_TIET_CHAN_DOAN cd
        JOIN LAN_KHAM lk ON lk.ma_lan_kham = cd.ma_lan_kham
        JOIN DOT_DIEU_TRI d ON d.ma_dot = cd.ma_dot
        JOIN BENH b ON b.ma_benh = d.ma_benh
        JOIN BENH_NHAN bn ON bn.ma_nguoi = lk.ma_benh_nhan
        JOIN NGUOI n ON n.ma_nguoi = bn.ma_nguoi
        WHERE lk.thoi_diem_vao >= :dt1 AND lk.thoi_diem_vao < :dt2
        ORDER BY lk.thoi_diem_vao, cd.ma_lan_kham
    """
    exam_lines = rows_to_dicts(conn.execute(text(sql_exam), {"dt1": dt_start, "dt2": dt_end}))

    # 2. Chi tiết dòng tiền thuốc
    sql_med = """
        SELECT 'CAP_THUOC' AS loai_giao_dich,
               d.ma_don, d.thoi_diem_cap, t.ten_thuoc, ct.so_luong, ct.don_gia_tai_thoi_diem,
               (ct.so_luong * ct.don_gia_tai_thoi_diem) AS thanh_tien
        FROM CT_DON_THUOC ct
        JOIN DON_THUOC d ON d.ma_don = ct.ma_don
        JOIN THUOC t ON t.ma_thuoc = ct.ma_thuoc
        WHERE d.trang_thai = 'DA_CAP'
          AND d.thoi_diem_cap >= :dt1 AND d.thoi_diem_cap < :dt2
        ORDER BY d.thoi_diem_cap, d.ma_don
    """
    med_lines = rows_to_dicts(conn.execute(text(sql_med), {"dt1": dt_start, "dt2": dt_end}))

    tien_kham = sum(float(l["phi_kham_chua"] or 0) for l in exam_lines)
    tien_thuoc = sum(float(l["thanh_tien"] or 0) for l in med_lines)
    tong_doanh_thu = tien_kham + tien_thuoc

    # Hợp nhất danh sách giao dịch tổng thể
    transactions = []
    for l in exam_lines:
        transactions.append({
            "loai": "Khám chữa bệnh",
            "ma_tham_chieu": f"Lượt #{l['ma_lan_kham']}",
            "thoi_diem": l["thoi_diem_vao"],
            "dien_giai": f"{l['ten_benh']} ({l['ten_benh_nhan']})",
            "so_tien": l["phi_kham_chua"],
        })
    for l in med_lines:
        transactions.append({
            "loai": "Cấp thuốc",
            "ma_tham_chieu": f"Đơn #{l['ma_don']}",
            "thoi_diem": l["thoi_diem_cap"],
            "dien_giai": f"{l['ten_thuoc']} ({l['so_luong']} viên/tuýp)",
            "so_tien": l["thanh_tien"],
        })

    summary = {
        "tien_kham": tien_kham,
        "tien_thuoc": tien_thuoc,
        "tong_doanh_thu": tong_doanh_thu,
        "doanh_thu_kham_chua": tien_kham,
        "doanh_thu_thuoc": tien_thuoc,
    }

    return summary, exam_lines, med_lines, transactions


# ==============================================================================
# CÁC ROUTE API BÁO CÁO (BƯỚC BE-11)
# ==============================================================================
@reports_bp.route("/api/reports/diseases", methods=["GET"])
def api_reports_diseases():
    """Thống kê bệnh theo tháng (Truy vấn lõi 1)."""
    month = request.args.get("month", "2026-10")
    _, _, dt_start, dt_end = get_month_bounds(month)
    with engine.connect() as conn:
        diseases = _query_diseases_report(conn, dt_start, dt_end)
        evidence = _query_diseases_evidence(conn, dt_start, dt_end)
    return jsonify({
        "success": True,
        "month": month,
        "diseases": diseases,
        "evidence": evidence,
    })


@reports_bp.route("/api/reports/payroll", methods=["GET"])
def api_reports_payroll():
    """Bảng tính lương Bác sĩ & Y tá theo tháng (Truy vấn lõi 2)."""
    month = request.args.get("month", "2026-10")
    d_start, d_end, dt_start, dt_end = get_month_bounds(month)
    with engine.connect() as conn:
        payroll = _query_payroll_report(conn, d_start, d_end, dt_start, dt_end)
        bs_evidence = _query_doctor_evidence(conn, d_start, d_end)
        yt_evidence = _query_nurse_evidence(conn, dt_start, dt_end)
    return jsonify({
        "success": True,
        "month": month,
        "payroll": payroll,
        "doctor_evidence": bs_evidence,
        "nurse_evidence": yt_evidence,
    })


@reports_bp.route("/api/reports/payroll/<string:emp_id>/evidence", methods=["GET"])
def api_reports_payroll_evidence(emp_id):
    """Căn cứ thưởng chi tiết của một nhân viên trong tháng."""
    month = request.args.get("month", "2026-10")
    d_start, d_end, dt_start, dt_end = get_month_bounds(month)
    with engine.connect() as conn:
        if emp_id.startswith("BS") or emp_id.startswith("NV01"):
            evidence = _query_doctor_evidence(conn, d_start, d_end, ma_bac_si=emp_id)
            loai = "BAC_SI"
        else:
            evidence = _query_nurse_evidence(conn, dt_start, dt_end, ma_y_ta=emp_id)
            loai = "Y_TA"
    return jsonify({
        "success": True,
        "month": month,
        "employee_id": emp_id,
        "role": loai,
        "evidence": evidence,
    })


@reports_bp.route("/api/reports/revenue", methods=["GET"])
def api_reports_revenue():
    """Doanh thu theo tháng (Truy vấn lõi 4)."""
    month = request.args.get("month", "2026-10")
    _, _, dt_start, dt_end = get_month_bounds(month)
    with engine.connect() as conn:
        summary, exam_lines, med_lines, transactions = _query_revenue_report(conn, dt_start, dt_end)
    return jsonify({
        "success": True,
        "month": month,
        "summary": summary,
        "tien_kham": summary["tien_kham"],
        "tien_thuoc": summary["tien_thuoc"],
        "tong_doanh_thu": summary["tong_doanh_thu"],
        "transactions": transactions,
        "exam_lines": exam_lines,
        "med_lines": med_lines,
    })


@reports_bp.route("/api/reports", methods=["GET"])
def api_reports():
    """API tổng hợp cả 4 truy vấn cho Màn hình 7 Frontend."""
    month = request.args.get("month", "2026-10")
    d_start, d_end, dt_start, dt_end = get_month_bounds(month)

    with engine.connect() as conn:
        q1_diseases = _query_diseases_report(conn, dt_start, dt_end)
        q1_evidence = _query_diseases_evidence(conn, dt_start, dt_end)
        q2_payroll = _query_payroll_report(conn, d_start, d_end, dt_start, dt_end)
        q2_bs_evidence = _query_doctor_evidence(conn, d_start, d_end)
        q2_yt_evidence = _query_nurse_evidence(conn, dt_start, dt_end)
        q4_summary, q4_exam_lines, q4_med_lines, _ = _query_revenue_report(conn, dt_start, dt_end)

    return jsonify({
        "success": True,
        "month": month,
        "q1_diseases": q1_diseases,
        "q1_evidence": q1_evidence,
        "q2_payroll": q2_payroll,
        "q2_bs_evidence": q2_bs_evidence,
        "q2_yt_evidence": q2_yt_evidence,
        "q4_summary": q4_summary,
        "q4_exam_lines": q4_exam_lines,
        "q4_med_lines": q4_med_lines,
    })


# ==============================================================================
# XUẤT BÁO CÁO RA FILE: CSV (UTF-8-SIG), EXCEL (XLSX), PDF (BƯỚC BE-12)
# ==============================================================================
def _build_csv(headers, data_rows):
    """Xuất CSV với mã hóa utf-8-sig (BOM) để Microsoft Excel hiển thị đúng tiếng Việt."""
    output = io.StringIO()
    output.write("\ufeff")  # UTF-8 BOM
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in data_rows:
        writer.writerow(row)
    return output.getvalue().encode("utf-8-sig")


def _build_excel(sheet_title, headers, data_rows):
    """Xuất file Excel (.xlsx) với định dạng đẹp."""
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_title[:30]

    # Tiêu đề bảng
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="0D9488", end_color="0D9488", fill_type="solid")  # Teal color
    thin_border = Border(
        left=Side(style="thin", color="CCCCCC"),
        right=Side(style="thin", color="CCCCCC"),
        top=Side(style="thin", color="CCCCCC"),
        bottom=Side(style="thin", color="CCCCCC"),
    )

    ws.append(headers)
    for col_idx, cell in enumerate(ws[1], start=1):
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for r in data_rows:
        ws.append(r)

    # Định dạng ô dữ liệu
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=len(headers)):
        for cell in row:
            cell.border = thin_border
            if isinstance(cell.value, (int, float)):
                cell.number_format = "#,##0"

    # Tự căn chỉnh chiều rộng cột
    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = col[0].column_letter
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _build_pdf(title, headers, data_rows):
    """Xuất file PDF dùng reportlab."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        name="TitleStyle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#0D9488"),
    )

    elements = [
        Paragraph(title, title_style),
        Spacer(1, 15),
    ]

    # Convert headers and rows to string
    table_data = [[str(h) for h in headers]]
    for r in data_rows:
        table_data.append([str(v) if v is not None else "" for v in r])

    t = Table(table_data)
    t.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0D9488")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ])
    )
    elements.append(t)
    doc.build(elements)
    return buf.getvalue()


@reports_bp.route("/api/reports/export", methods=["GET"])
@reports_bp.route("/api/export/<string:report_type>", methods=["GET"])
def api_export_report(report_type=None):
    """
    Xuất báo cáo sang CSV, Excel (.xlsx) hoặc PDF.
    - Hỗ trợ loại: 'revenue', 'payroll', 'diseases', 'patient_history'.
    - Định dạng: 'csv' (utf-8-sig có BOM), 'xlsx', 'pdf'.
    """
    rep_type = (report_type or request.args.get("type", "revenue")).lower()
    fmt = request.args.get("format", "csv").lower()
    month = request.args.get("month", "2026-10")
    d_start, d_end, dt_start, dt_end = get_month_bounds(month)

    with engine.connect() as conn:
        if rep_type == "payroll":
            title = f"BANG_LUONG_NHAN_VIEN_THANG_{month}"
            headers = [
                "Loại NV",
                "Mã NV",
                "Mã Chuyên Biệt",
                "Họ Tên",
                "Lương Cơ Bản",
                "Số Ca Thưởng",
                "Tiền Thưởng",
                "Tổng Lương",
            ]
            payroll_rows = _query_payroll_report(conn, d_start, d_end, dt_start, dt_end)
            data_rows = [
                [
                    r["loai"],
                    r["ma_nhan_vien"],
                    r["ma_chuyen_biet"],
                    r["ho_ten"],
                    r["luong_co_ban"],
                    r["so_ca_thuong"],
                    r["tien_thuong"],
                    r["tong_luong"],
                ]
                for r in payroll_rows
            ]

        elif rep_type in ("diseases", "benh"):
            title = f"THONG_KE_BENH_THANG_{month}"
            headers = [
                "Mã Bệnh",
                "Tên Bệnh",
                "Số Đợt Mắc",
                "Số Bệnh Nhân Duy Nhất",
            ]
            dis_rows = _query_diseases_report(conn, dt_start, dt_end)
            data_rows = [
                [
                    r["ma_benh"],
                    r["ten_benh"],
                    r["so_dot_mac"],
                    r["so_benh_nhan_duy_nhat"],
                ]
                for r in dis_rows
            ]

        elif rep_type in ("patient_history", "benh_nhan"):
            title = f"LICH_SU_BENH_NHAN_{month}"
            headers = [
                "Mã Lượt",
                "Mã BN",
                "Họ Tên",
                "Thời Điểm Vào",
                "Bệnh Chẩn Đoán",
                "Bác Sĩ",
                "Phí Khám",
            ]
            sql = """
                SELECT lk.ma_lan_kham, bn.ma_benh_nhan, n.ho_ten, lk.thoi_diem_vao, b.ten_benh, cd.ma_bac_si, cd.phi_kham_chua
                FROM LAN_KHAM lk
                JOIN CHI_TIET_CHAN_DOAN cd ON cd.ma_lan_kham = lk.ma_lan_kham
                JOIN DOT_DIEU_TRI d ON d.ma_dot = cd.ma_dot
                JOIN BENH b ON b.ma_benh = d.ma_benh
                JOIN BENH_NHAN bn ON bn.ma_nguoi = lk.ma_benh_nhan
                JOIN NGUOI n ON n.ma_nguoi = bn.ma_nguoi
                WHERE lk.thoi_diem_vao >= :dt1 AND lk.thoi_diem_vao < :dt2
                ORDER BY lk.thoi_diem_vao
            """
            rows = rows_to_dicts(conn.execute(text(sql), {"dt1": dt_start, "dt2": dt_end}))
            data_rows = [
                [
                    r["ma_lan_kham"],
                    r["ma_benh_nhan"],
                    r["ho_ten"],
                    r["thoi_diem_vao"],
                    r["ten_benh"],
                    r["ma_bac_si"],
                    r["phi_kham_chua"],
                ]
                for r in rows
            ]

        else:  # revenue
            title = f"BAO_CAO_DOANH_THU_THANG_{month}"
            headers = [
                "Loại Giao Dịch",
                "Mã Tham Chiếu",
                "Thời Điểm",
                "Tên Hạng Mục / Diễn Giải",
                "Số Tiền (VNĐ)",
            ]
            _, exam_lines, med_lines, _ = _query_revenue_report(conn, dt_start, dt_end)
            data_rows = []
            for e in exam_lines:
                data_rows.append([
                    "Khám chữa bệnh",
                    f"Lượt #{e['ma_lan_kham']}",
                    e["thoi_diem_vao"],
                    f"{e['ten_benh']} - {e['ten_benh_nhan']}",
                    e["phi_kham_chua"],
                ])
            for m in med_lines:
                data_rows.append([
                    "Cấp thuốc",
                    f"Đơn #{m['ma_don']}",
                    m["thoi_diem_cap"],
                    f"{m['ten_thuoc']} ({m['so_luong']} viên/tuýp)",
                    m["thanh_tien"],
                ])

    # Tạo nội dung trả về theo format
    if fmt == "xlsx":
        content = _build_excel(title, headers, data_rows)
        mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"{title}.xlsx"
    elif fmt == "pdf":
        content = _build_pdf(title, headers, data_rows)
        mimetype = "application/pdf"
        filename = f"{title}.pdf"
    else:  # csv
        content = _build_csv(headers, data_rows)
        mimetype = "text/csv; charset=utf-8-sig"
        filename = f"{title}.csv"

    return Response(
        content,
        mimetype=mimetype,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
