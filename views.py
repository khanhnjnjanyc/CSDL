import io
import pandas as pd
from flask import Blueprint, jsonify, request, send_file
from sqlalchemy import text
from extensions import db
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

main_bp = Blueprint('main', __name__)

# ==============================================================================
# 1, 2, 3. QUẢN LÝ HỒ SƠ (THÊM, SỬA, XEM, KHÓA) BỆNH NHÂN, BÁC SĨ, Y TÁ
# ==============================================================================

@main_bp.route('/api/hoso/<string:role>', methods=['POST', 'GET'])
def quan_ly_hoso(role):
    # GET: Xem danh sách
    if request.method == 'GET':
        sql = text(f"""
            SELECT n.CMT, n.HoTen, n.NgaySinh, n.DiaChi, n.SoDienThoai, n.TrangThaiKhoa,
                   x.Ma{role.capitalize()}
            FROM NGUOI n
            JOIN {role.upper()} x ON n.CMT = x.CMT
        """)
        rows = db.session.execute(sql).fetchall()
        return jsonify([dict(r._mapping) for r in rows])

    # POST: Thêm mới hồ sơ
    data = request.json
    cmt, hoten = data.get('CMT'), data.get('HoTen')
    ngaysinh, diachi, sdt = data.get('NgaySinh'), data.get('DiaChi'), data.get('SoDienThoai')

    db.session.execute(
        text("INSERT INTO NGUOI (CMT, HoTen, NgaySinh, DiaChi, SoDienThoai) VALUES (:cmt, :ht, :ns, :dc, :sdt)"),
        {'cmt': cmt, 'ht': hoten, 'ns': ngaysinh, 'dc': diachi, 'sdt': sdt}
    )

    if role == 'benhnhan':
        db.session.execute(text("INSERT INTO BENHNHAN (MaBN, CMT) VALUES (:id, :cmt)"), {'id': data.get('MaBN'), 'cmt': cmt})
    elif role == 'bacsi':
        db.session.execute(
            text("INSERT INTO BACSI (MaBS, CMT, BacNghe, ThamNien, TrinhDoDaoTao, ChuyenMon) VALUES (:id, :cmt, :bn, :tn, :td, :cm)"),
            {'id': data.get('MaBS'), 'cmt': cmt, 'bn': data.get('BacNghe'), 'tn': data.get('ThamNien'), 'td': data.get('TrinhDoDaoTao'), 'cm': data.get('ChuyenMon')}
        )
    elif role == 'yta':
        db.session.execute(
            text("INSERT INTO YTA (MaYTa, CMT, TrinhDo, ThamNien) VALUES (:id, :cmt, :td, :tn)"),
            {'id': data.get('MaYTa'), 'cmt': cmt, 'td': data.get('TrinhDo'), 'tn': data.get('ThamNien')}
        )

    db.session.commit()
    return jsonify({'message': f'Thêm {role} thành công!'})


@main_bp.route('/api/hoso/khoa/<string:cmt>', methods=['PUT'])
def khoa_ho_so(cmt):
    status = request.json.get('TrangThaiKhoa', True)
    db.session.execute(
        text("UPDATE NGUOI SET TrangThaiKhoa = :st WHERE CMT = :cmt"),
        {'st': status, 'cmt': cmt}
    )
    db.session.commit()
    return jsonify({'message': f"Đã {'khóa' if status else 'mở khóa'} hồ sơ {cmt}"})


# ==============================================================================
# 4. TÌM KIẾM VÀ LỌC BỆNH NHÂN
# ==============================================================================
@main_bp.route('/api/benh-nhan/tim-kiem', methods=['GET'])
def tim_kiem_benh_nhan():
    kw = f"%{request.args.get('keyword', '')}%"
    sql = text("""
        SELECT bn.MaBN, n.CMT, n.HoTen, n.NgaySinh, n.DiaChi, n.SoDienThoai
        FROM BENHNHAN bn
        JOIN NGUOI n ON bn.CMT = n.CMT
        WHERE CAST(bn.MaBN AS CHAR) LIKE :kw 
           OR n.HoTen LIKE :kw 
           OR n.CMT LIKE :kw 
           OR n.SoDienThoai LIKE :kw
    """)
    result = db.session.execute(sql, {'kw': kw}).fetchall()
    return jsonify([dict(r._mapping) for r in result])


# ==============================================================================
# 5. TẠO, CẬP NHẬT VÀ XEM CHI TIẾT LẦN KHÁM
# ==============================================================================
@main_bp.route('/api/lan-kham', methods=['POST'])
def tao_lan_kham():
    d = request.json
    sql = text("""
        INSERT INTO LANKHAM (MaLanKham, MaDot, SoThuTu, NgayVao, NgayRa, TienKham)
        VALUES (:mlk, :md, :stt, :nv, :nr, :tk)
    """)
    db.session.execute(sql, {'mlk': d['MaLanKham'], 'md': d['MaDot'], 'stt': d['SoThuTu'], 'nv': d['NgayVao'], 'nr': d.get('NgayRa'), 'tk': d['TienKham']})
    db.session.commit()
    return jsonify({'message': 'Tạo lần khám thành công'})


# ==============================================================================
# 6. GÁN Y TÁ HỖ TRỢ CHO LẦN KHÁM
# ==============================================================================
@main_bp.route('/api/lan-kham/gan-y-ta', methods=['POST'])
def gan_y_ta_ho_tro():
    # Payload format: {"MaLanKham": 1, "DanhSachYTa": [{"MaYTa": 1, "LoaiHoTro": "Chăm sóc"}]}
    data = request.json
    mlk = data['MaLanKham']
    for yt in data['DanhSachYTa']:
        db.session.execute(
            text("INSERT INTO HOTRO (MaYTa, MaLanKham, LoaiHoTro) VALUES (:yt, :lk, :vt)"),
            {'yt': yt['MaYTa'], 'lk': mlk, 'vt': yt['LoaiHoTro']}
        )
    db.session.commit()
    return jsonify({'message': 'Phân công Y tá thành công'})


# ==============================================================================
# 7. QUẢN LÝ DANH MỤC BỆNH VÀ CHUYÊN MÔN BÁC SĨ
# ==============================================================================
@main_bp.route('/api/danh-muc/benh', methods=['GET', 'POST'])
def me_benh():
    if request.method == 'GET':
        res = db.session.execute(text("SELECT * FROM BENH")).fetchall()
        return jsonify([dict(r._mapping) for r in res])
    data = request.json
    db.session.execute(text("INSERT INTO BENH (MaBenh, TenBenh) VALUES (:id, :ten)"), {'id': data['MaBenh'], 'ten': data['TenBenh']})
    db.session.commit()
    return jsonify({'message': 'Thêm danh mục bệnh thành công'})


# ==============================================================================
# 8. KÊ ĐƠN THUỐC, TÍNH THÀNH TIỀN VÀ KIỂM TRA TỒN KHO
# ==============================================================================
@main_bp.route('/api/don-thuoc/ke-don', methods=['POST'])
def ke_don_thuoc():
    data = request.json  # {"MaLanKham": 1, "MaThuoc": 1, "SoLuong": 5}
    mlk, mt, sl = data['MaLanKham'], data['MaThuoc'], data['SoLuong']

    # Kiểm tra tồn kho
    thuoc = db.session.execute(text("SELECT DonGia, SoLuongTon FROM THUOC WHERE MaThuoc = :mt"), {'mt': mt}).fetchone()
    if not thuoc or thuoc.SoLuongTon < sl:
        return jsonify({'error': 'Thuốc không đủ số lượng tồn kho!'}), 400

    don_gia = thuoc.DonGia
    # Trừ kho và kê đơn
    db.session.execute(text("UPDATE THUOC SET SoLuongTon = SoLuongTon - :sl WHERE MaThuoc = :mt"), {'sl': sl, 'mt': mt})
    db.session.execute(
        text("INSERT INTO CHITIETDONTHUOC (MaLanKham, MaThuoc, SoLuong, DonGiaBan) VALUES (:lk, :mt, :sl, :dg)"),
        {'lk': mlk, 'mt': mt, 'sl': sl, 'dg': don_gia}
    )
    db.session.commit()
    return jsonify({'message': 'Kê đơn thuốc thành công', 'ThanhTien': float(don_gia * sl)})


# ==============================================================================
# 9. IN/XUẤT HÓA ĐƠN LẦN KHÁM RA PDF
# ==============================================================================
@main_bp.route('/api/hoa-don/pdf/<int:ma_lan_kham>', methods=['GET'])
def xuat_pdf_hoa_don(ma_lan_kham):
    sql = text("""
        SELECT lk.MaLanKham, lk.TienKham, n.HoTen
        FROM LANKHAM lk
        JOIN DOTDIEUTRI ddt ON lk.MaDot = ddt.MaDot
        JOIN BENHNHAN bn ON ddt.MaBN = bn.MaBN
        JOIN NGUOI n ON bn.CMT = n.CMT
        WHERE lk.MaLanKham = :lk
    """)
    info = db.session.execute(sql, {'lk': ma_lan_kham}).fetchone()

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.drawString(100, 750, f"--- HOA DON KHAM BENH ---")
    p.drawString(100, 720, f"Ma Lan Kham: {info.MaLanKham}")
    p.drawString(100, 690, f"Benh Nhan: {info.HoTen}")
    p.drawString(100, 660, f"Tien Kham: {info.TienKham} VND")
    p.showPage()
    p.save()

    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"HoaDon_{ma_lan_kham}.pdf", mimetype='application/pdf')


# ==============================================================================
# 10. XUẤT BÁO CÁO DOANH THU HOẶC LƯƠNG RA EXCEL/CSV
# ==============================================================================
@main_bp.route('/api/bao-cao/export', methods=['GET'])
def export_excel():
    fmt = request.args.get('format', 'excel')
    sql = text("""
        SELECT lk.MaLanKham, lk.NgayVao, lk.TienKham, 
               COALESCE(SUM(dt.SoLuong * dt.DonGiaBan), 0) AS TienThuoc
        FROM LANKHAM lk
        LEFT JOIN CHITIETDONTHUOC dt ON lk.MaLanKham = dt.MaLanKham
        GROUP BY lk.MaLanKham, lk.NgayVao, lk.TienKham
    """)
    rows = db.session.execute(sql).fetchall()
    df = pd.DataFrame([dict(r._mapping) for r in rows])

    output = io.BytesIO()
    if fmt == 'csv':
        df.to_csv(output, index=False, encoding='utf-8-sig')
        mimetype = 'text/csv'
        filename = "BaoCaoDoanhThu.csv"
    else:
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='DoanhThu')
        mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        filename = "BaoCaoDoanhThu.xlsx"

    output.seek(0)
    return send_file(output, as_attachment=True, download_name=filename, mimetype=mimetype)