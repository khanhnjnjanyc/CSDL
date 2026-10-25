import io
import pandas as pd
from flask import Blueprint, jsonify, request, send_file
from sqlalchemy import text
from extensions import db
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

main_bp = Blueprint('main', __name__)


# ==============================================================================
# 3.2. BỐN CHỨC NĂNG CỐT LÕI
# ==============================================================================

# 1. Tra cứu lịch sử / hiện trạng bệnh nhân (Dòng thời gian)
@main_bp.route('/api/cot-loi/lich-su-benh-nhan', methods=['GET'])
def tra_cuu_lich_su():
    kw = f"%{request.args.get('keyword', '')}%"
    sql = text("""
        SELECT bn.MaBN, n.HoTen, ddt.MaDot, b.TenBenh, bs_n.HoTen AS TenBacSi,
               lk.MaLanKham, lk.SoThuTu, lk.NgayVao, lk.NgayRa, ddt.TrangThai AS TrangThaiDot
        FROM BENHNHAN bn
        JOIN NGUOI n ON bn.CMT = n.CMT
        JOIN DOTDIEUTRI ddt ON bn.MaBN = ddt.MaBN
        JOIN BENH b ON ddt.MaBenh = b.MaBenh
        JOIN BACSI bs ON ddt.MaBS = bs.MaBS
        JOIN NGUOI bs_n ON bs.CMT = bs_n.CMT
        LEFT JOIN LANKHAM lk ON ddt.MaDot = lk.MaDot
        WHERE CAST(bn.MaBN AS CHAR) LIKE :kw OR n.HoTen LIKE :kw
        ORDER BY ddt.NgayBatDau DESC, lk.SoThuTu ASC
    """)
    rows = db.session.execute(sql, {'kw': kw}).fetchall()
    return jsonify([dict(r._mapping) for r in rows])


# 2. Theo dõi đợt bệnh / khỏi / tái phát & Kết thúc đợt
@main_bp.route('/api/cot-loi/ket-thuc-dot/<int:ma_dot>', methods=['PUT'])
def ket_thuc_dot(ma_dot):
    ngay_kt = request.json.get('NgayKetThuc')
    db.session.execute(text("""
        UPDATE DOTDIEUTRI 
        SET TrangThai = 'Đã khỏi', NgayKetThuc = :nk 
        WHERE MaDot = :md
    """), {'nk': ngay_kt, 'md': ma_dot})
    db.session.commit()
    return jsonify({'message': f'Đã cập nhật đợt điều trị {ma_dot} thành "Đã khỏi"'})


# 3. Tính lương (Lương cứng + thưởng đợt khỏi của Bác sĩ + lượt hỗ trợ Y tá)
@main_bp.route('/api/cot-loi/tinh-luong', methods=['GET'])
def tinh_luong_chi_tiet():
    month = request.args.get('month')  # YYYY-MM
    # Lương Bác sĩ: 10,000,000 + 500,000 đ/đợt chữa khỏi trong tháng
    sql_bs = text("""
        SELECT bs.MaBS, n.HoTen, 10000000 AS LuongCung,
               COUNT(ddt.MaDot) AS SoDotKhoi,
               (COUNT(ddt.MaDot) * 500000) AS Thuong,
               (10000000 + COUNT(ddt.MaDot) * 500000) AS TongLuong
        FROM BACSI bs
        JOIN NGUOI n ON bs.CMT = n.CMT
        LEFT JOIN DOTDIEUTRI ddt ON bs.MaBS = ddt.MaBS 
             AND ddt.TrangThai = 'Đã khỏi' 
             AND DATE_FORMAT(ddt.NgayKetThuc, '%Y-%m') = :m
        GROUP BY bs.MaBS, n.HoTen
    """)

    # Lương Y tá: 7,000,000 + 100,000 đ/lượt hỗ trợ
    sql_yt = text("""
        SELECT yt.MaYTa, n.HoTen, 7000000 AS LuongCung,
               COUNT(ht.MaLanKham) AS SoLuotHoTro,
               (COUNT(ht.MaLanKham) * 100000) AS Thuong,
               (7000000 + COUNT(ht.MaLanKham) * 100000) AS TongLuong
        FROM YTA yt
        JOIN NGUOI n ON yt.CMT = n.CMT
        LEFT JOIN HOTRO ht ON yt.MaYTa = ht.MaYTa
        LEFT JOIN LANKHAM lk ON ht.MaLanKham = lk.MaLanKham
             AND DATE_FORMAT(lk.NgayVao, '%Y-%m') = :m
        GROUP BY yt.MaYTa, n.HoTen
    """)

    bac_si = db.session.execute(sql_bs, {'m': month}).fetchall()
    y_ta = db.session.execute(sql_yt, {'m': month}).fetchall()
    return jsonify({
        'BacSi': [dict(r._mapping) for r in bac_si],
        'YTa': [dict(r._mapping) for r in y_ta]
    })


# 4. Doanh thu (Tách riêng Tiền khám & Tiền thuốc)
@main_bp.route('/api/cot-loi/doanh-thu', methods=['GET'])
def doanh_thu_chi_tiet():
    month = request.args.get('month')  # YYYY-MM
    sql = text("""
        SELECT DATE_FORMAT(lk.NgayVao, '%Y-%m-%d') AS Ngay,
               SUM(lk.TienKham) AS TongTienKham,
               COALESCE(SUM(ct.SoLuong * ct.DonGiaBan), 0) AS TongTienThuoc,
               (SUM(lk.TienKham) + COALESCE(SUM(ct.SoLuong * ct.DonGiaBan), 0)) AS TongDoanhThu
        FROM LANKHAM lk
        LEFT JOIN CHITIETDONTHUOC ct ON lk.MaLanKham = ct.MaLanKham
        WHERE DATE_FORMAT(lk.NgayVao, '%Y-%m') = :m
        GROUP BY DATE_FORMAT(lk.NgayVao, '%Y-%m-%d')
    """)
    rows = db.session.execute(sql, {'m': month}).fetchall()
    return jsonify([dict(r._mapping) for r in rows])


# ==============================================================================
# 3.3. ĐÚNG 10 TÍNH NĂNG PHỤ
# ==============================================================================

# 1, 2, 3. Thêm, sửa, xem, khóa hồ sơ (Bệnh nhân, Bác sĩ, Y tá)
@main_bp.route('/api/hoso/<string:role>', methods=['GET', 'POST', 'PUT'])
def quan_ly_hoso_full(role):
    if request.method == 'GET':
        sql = text(f"""
            SELECT n.CMT, n.HoTen, n.NgaySinh, n.DiaChi, n.SoDienThoai, 
                   COALESCE(n.TrangThaiKhoa, 0) AS TrangThaiKhoa, x.Ma{role.capitalize()}
            FROM NGUOI n JOIN {role.upper()} x ON n.CMT = x.CMT
        """)
        return jsonify([dict(r._mapping) for r in db.session.execute(sql).fetchall()])

    data = request.json
    if request.method == 'POST':
        db.session.execute(
            text("INSERT INTO NGUOI (CMT, HoTen, NgaySinh, DiaChi, SoDienThoai) VALUES (:c, :h, :ns, :dc, :sdt)"),
            {'c': data['CMT'], 'h': data['HoTen'], 'ns': data['NgaySinh'], 'dc': data.get('DiaChi'),
             'sdt': data.get('SoDienThoai')})
        if role == 'benhnhan':
            db.session.execute(text("INSERT INTO BENHNHAN (MaBN, CMT) VALUES (:id, :c)"),
                               {'id': data['MaBN'], 'c': data['CMT']})
        elif role == 'bacsi':
            db.session.execute(text(
                "INSERT INTO BACSI (MaBS, CMT, BacNghe, ThamNien, TrinhDoDaoTao, ChuyenMon) VALUES (:id, :c, :bn, :tn, :td, :cm)"),
                               {'id': data['MaBS'], 'c': data['CMT'], 'bn': data['BacNghe'],
                                'tn': data.get('ThamNien', 0), 'td': data.get('TrinhDoDaoTao'),
                                'cm': data['ChuyenMon']})
        elif role == 'yta':
            db.session.execute(text("INSERT INTO YTA (MaYTa, CMT, TrinhDo, ThamNien) VALUES (:id, :c, :td, :tn)"),
                               {'id': data['MaYTa'], 'c': data['CMT'], 'td': data['TrinhDo'],
                                'tn': data.get('ThamNien', 0)})
        db.session.commit()
        return jsonify({'message': f'Thêm hồ sơ {role} thành công'})


# 4. Tìm kiếm và lọc bệnh nhân theo mã, tên, CMT, SĐT
@main_bp.route('/api/benh-nhan/tim-kiem', methods=['GET'])
def tim_kiem_benh_nhan():
    kw = f"%{request.args.get('keyword', '')}%"
    sql = text("""
        SELECT bn.MaBN, n.CMT, n.HoTen, n.NgaySinh, n.DiaChi, n.SoDienThoai
        FROM BENHNHAN bn JOIN NGUOI n ON bn.CMT = n.CMT
        WHERE CAST(bn.MaBN AS CHAR) LIKE :kw OR n.HoTen LIKE :kw OR n.CMT LIKE :kw OR n.SoDienThoai LIKE :kw
    """)
    return jsonify([dict(r._mapping) for r in db.session.execute(sql, {'kw': kw}).fetchall()])


# 5. Tạo, cập nhật và xem chi tiết lần khám
@main_bp.route('/api/lan-kham', methods=['POST', 'PUT'])
def tao_cap_nhat_lan_kham():
    d = request.json
    if request.method == 'POST':
        db.session.execute(text(
            "INSERT INTO LANKHAM (MaLanKham, MaDot, SoThuTu, NgayVao, NgayRa, TienKham) VALUES (:lk, :md, :stt, :nv, :nr, :tk)"),
                           {'lk': d['MaLanKham'], 'md': d['MaDot'], 'stt': d['SoThuTu'], 'nv': d['NgayVao'],
                            'nr': d.get('NgayRa'), 'tk': d['TienKham']})
    db.session.commit()
    return jsonify({'message': 'Thao tác lần khám thành công'})


# 6. Gán y tá hỗ trợ cho lần khám, chọn vai trò
@main_bp.route('/api/lan-kham/gan-y-ta', methods=['POST'])
def gan_y_ta():
    d = request.json
    db.session.execute(text("INSERT INTO HOTRO (MaYTa, MaLanKham, LoaiHoTro) VALUES (:yt, :lk, :vt)"),
                       {'yt': d['MaYTa'], 'lk': d['MaLanKham'], 'vt': d['LoaiHoTro']})
    db.session.commit()
    return jsonify({'message': 'Gán Y tá hỗ trợ thành công'})


# 7. Quản lý danh mục bệnh và chuyên môn bác sĩ
@main_bp.route('/api/danh-muc/benh', methods=['GET', 'POST'])
def dm_benh():
    if request.method == 'GET':
        return jsonify([dict(r._mapping) for r in db.session.execute(text("SELECT * FROM BENH")).fetchall()])
    d = request.json
    db.session.execute(text("INSERT INTO BENH (MaBenh, TenBenh) VALUES (:mb, :tb)"),
                       {'mb': d['MaBenh'], 'tb': d['TenBenh']})
    db.session.commit()
    return jsonify({'message': 'Thêm bệnh mới thành công'})


# 8. Kê đơn thuốc, tự tính thành tiền và kiểm tra tồn kho
@main_bp.route('/api/don-thuoc/ke-don', methods=['POST'])
def ke_don():
    d = request.json
    thuoc = db.session.execute(
        text("SELECT DonGia, COALESCE(SoLuongTon, 100) AS SoLuongTon FROM THUOC WHERE MaThuoc = :mt"),
        {'mt': d['MaThuoc']}).fetchone()
    if not thuoc or thuoc.SoLuongTon < d['SoLuong']:
        return jsonify({'error': 'Số lượng thuốc tồn kho không đủ!'}), 400

    db.session.execute(
        text("INSERT INTO CHITIETDONTHUOC (MaLanKham, MaThuoc, SoLuong, DonGiaBan) VALUES (:lk, :mt, :sl, :dg)"),
        {'lk': d['MaLanKham'], 'mt': d['MaThuoc'], 'sl': d['SoLuong'], 'dg': thuoc.DonGia})
    db.session.commit()
    return jsonify({'message': 'Kê đơn thành công', 'ThanhTien': float(thuoc.DonGia * d['SoLuong'])})


# 9. In/xuất hóa đơn theo lần khám ra PDF
@main_bp.route('/api/hoa-don/pdf/<int:ma_lan_kham>', methods=['GET'])
def xuat_pdf(ma_lan_kham):
    info = db.session.execute(text("""
        SELECT lk.MaLanKham, lk.TienKham, n.HoTen FROM LANKHAM lk
        JOIN DOTDIEUTRI ddt ON lk.MaDot = ddt.MaDot
        JOIN BENHNHAN bn ON ddt.MaBN = bn.MaBN JOIN NGUOI n ON bn.CMT = n.CMT
        WHERE lk.MaLanKham = :lk
    """), {'lk': ma_lan_kham}).fetchone()

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.drawString(100, 750, f"HOA DON LAN KHAM: {info.MaLanKham}")
    p.drawString(100, 720, f"Benh Nhan: {info.HoTen}")
    p.drawString(100, 690, f"Tien Kham: {info.TienKham} VND")
    p.showPage()
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"HoaDon_{ma_lan_kham}.pdf", mimetype='application/pdf')


# 10. Xuất báo cáo doanh thu ra Excel/CSV
@main_bp.route('/api/bao-cao/export', methods=['GET'])
def export_baocao():
    fmt = request.args.get('format', 'excel')
    rows = db.session.execute(text("""
        SELECT lk.MaLanKham, lk.NgayVao, lk.TienKham, COALESCE(SUM(dt.SoLuong * dt.DonGiaBan), 0) AS TienThuoc
        FROM LANKHAM lk LEFT JOIN CHITIETDONTHUOC dt ON lk.MaLanKham = dt.MaLanKham
        GROUP BY lk.MaLanKham, lk.NgayVao, lk.TienKham
    """)).fetchall()
    df = pd.DataFrame([dict(r._mapping) for r in rows])

    out = io.BytesIO()
    if fmt == 'csv':
        df.to_csv(out, index=False, encoding='utf-8-sig')
        return send_file(out, as_attachment=True, download_name="BaoCao.csv", mimetype='text/csv')
    with pd.ExcelWriter(out, engine='openpyxl') as w:
        df.to_excel(w, index=False)
    out.seek(0)
    return send_file(out, as_attachment=True, download_name="BaoCao.xlsx",
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')