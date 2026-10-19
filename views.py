from flask import Blueprint, jsonify, request
from sqlalchemy import text
from extensions import db

main_bp = Blueprint('main', __name__)


# -----------------------------------------------------------------------------
# 1. Thống kê danh sách các loại bệnh trong một tháng cho trước
# Thuật toán SQL: Sử dụng LAG() để phân biệt đợt điều trị liên tiếp vs tái phát bệnh
# -----------------------------------------------------------------------------
@main_bp.route('/api/thong-ke-benh', methods=['GET'])
def thong_ke_benh():
    month = request.args.get('month')  # Định dạng: YYYY-MM
    if not month:
        return jsonify({'error': 'Vui lòng truyền tham số month (VD: 2026-10)'}), 400

    sql = text("""
        WITH DotKhamOrdered AS (
            SELECT 
                ddt.MaBN,
                ddt.MaBenh,
                ddt.NgayBatDau,
                LAG(ddt.MaBenh) OVER (PARTITION BY ddt.MaBN ORDER BY ddt.NgayBatDau) AS BenhTruoc,
                LAG(ddt.TrangThai) OVER (PARTITION BY ddt.MaBN ORDER BY ddt.NgayBatDau) AS TrangThaiTruoc
            FROM DOTDIEUTRI ddt
        ),
        CaMacBenhMoi AS (
            SELECT 
                MaBN,
                MaBenh,
                NgayBatDau
            FROM DotKhamOrdered
            WHERE 
                BenhTruoc IS NULL 
                OR BenhTruoc <> MaBenh 
                OR (BenhTruoc = MaBenh AND TrangThaiTruoc = 'Đã khỏi')
        )
        SELECT 
            b.MaBenh,
            b.TenBenh,
            COUNT(c.MaBN) AS SoLuotBenhNhan
        FROM CaMacBenhMoi c
        JOIN BENH b ON c.MaBenh = b.MaBenh
        WHERE DATE_FORMAT(c.NgayBatDau, '%Y-%m') = :month
        GROUP BY b.MaBenh, b.TenBenh
        ORDER BY SoLuotBenhNhan DESC;
    """)

    result = db.session.execute(sql, {'month': month}).fetchall()
    return jsonify([{
        'MaBenh': row.MaBenh,
        'TenBenh': row.TenBenh,
        'SoLuotBenhNhan': row.SoLuotBenhNhan
    } for row in result])


# -----------------------------------------------------------------------------
# 2. Tính lương Bác sĩ và Y tá trong tháng
# -----------------------------------------------------------------------------
@main_bp.route('/api/tinh-luong', methods=['GET'])
def tinh_luong():
    month = request.args.get('month')  # Định dạng: YYYY-MM
    if not month:
        return jsonify({'error': 'Vui lòng truyền tham số month (VD: 2026-10)'}), 400

    # Bác sĩ: 7 triệu cứng + 1 triệu cho mỗi đợt điều trị chuyển thành 'Đã khỏi' trong tháng
    sql_bs = text("""
        SELECT 
            bs.MaBS,
            n.HoTen,
            7000000 AS LuongCoBan,
            COUNT(ddt.MaDot) * 1000000 AS Thuong,
            7000000 + (COUNT(ddt.MaDot) * 1000000) AS TongLuong
        FROM BACSI bs
        JOIN NGUOI n ON bs.CMT = n.CMT
        LEFT JOIN DOTDIEUTRI ddt ON bs.MaBS = ddt.MaBS 
            AND ddt.TrangThai = 'Đã khỏi'
            AND DATE_FORMAT(ddt.NgayKetThuc, '%Y-%m') = :month
        GROUP BY bs.MaBS, n.HoTen;
    """)

    # Y tá: 5 triệu cứng + 200k cho mỗi lần hỗ trợ lượt khám thực hiện trong tháng
    sql_yt = text("""
        SELECT 
            yt.MaYTa,
            n.HoTen,
            5000000 AS LuongCoBan,
            COUNT(ht.MaLanKham) * 200000 AS Thuong,
            5000000 + (COUNT(ht.MaLanKham) * 200000) AS TongLuong
        FROM YTA yt
        JOIN NGUOI n ON yt.CMT = n.CMT
        LEFT JOIN HOTRO ht ON yt.MaYTa = ht.MaYTa
        LEFT JOIN LANKHAM lk ON ht.MaLanKham = lk.MaLanKham 
            AND DATE_FORMAT(lk.NgayVao, '%Y-%m') = :month
        GROUP BY yt.MaYTa, n.HoTen;
    """)

    result_bs = db.session.execute(sql_bs, {'month': month}).fetchall()
    result_yt = db.session.execute(sql_yt, {'month': month}).fetchall()

    return jsonify({
        'BacSi': [{
            'MaBS': r.MaBS,
            'HoTen': r.HoTen,
            'LuongCoBan': float(r.LuongCoBan),
            'Thuong': float(r.Thuong),
            'TongLuong': float(r.TongLuong)
        } for r in result_bs],
        'YTa': [{
            'MaYTa': r.MaYTa,
            'HoTen': r.HoTen,
            'LuongCoBan': float(r.LuongCoBan),
            'Thuong': float(r.Thuong),
            'TongLuong': float(r.TongLuong)
        } for r in result_yt]
    })


# -----------------------------------------------------------------------------
# 3. Hiển thị thông tin Bệnh nhân & Tình trạng bệnh hiện tại + Lịch sử
# -----------------------------------------------------------------------------
@main_bp.route('/api/benh-nhan/<int:ma_bn>', methods=['GET'])
def thong_tin_benh_nhan(ma_bn):
    # Thông tin cá nhân
    sql_nguoi = text("""
        SELECT bn.MaBN, n.CMT, n.HoTen, n.NgaySinh, n.DiaChi, n.SoDienThoai
        FROM BENHNHAN bn
        JOIN NGUOI n ON bn.CMT = n.CMT
        WHERE bn.MaBN = :ma_bn;
    """)
    info = db.session.execute(sql_nguoi, {'ma_bn': ma_bn}).fetchone()
    if not info:
        return jsonify({'error': 'Không tìm thấy bệnh nhân'}), 404

    # Tình trạng hiện tại: Các bệnh đang điều trị và số lần đã khám cho bệnh đó
    sql_hien_tai = text("""
        SELECT 
            b.MaBenh,
            b.TenBenh,
            COUNT(lk.MaLanKham) AS SoLanKhamChoBenhNay
        FROM DOTDIEUTRI ddt
        JOIN BENH b ON ddt.MaBenh = b.MaBenh
        LEFT JOIN LANKHAM lk ON ddt.MaDot = lk.MaDot
        WHERE ddt.MaBN = :ma_bn AND ddt.TrangThai = 'Đang điều trị'
        GROUP BY b.MaBenh, b.TenBenh;
    """)

    # Lịch sử khám chữa bệnh chi tiết
    sql_lich_su = text("""
        SELECT 
            ddt.MaDot,
            b.TenBenh,
            n_bs.HoTen AS TenBacSi,
            ddt.NgayBatDau,
            ddt.NgayKetThuc,
            ddt.TrangThai,
            lk.MaLanKham,
            lk.SoThuTu,
            lk.NgayVao,
            lk.TienKham
        FROM DOTDIEUTRI ddt
        JOIN BENH b ON ddt.MaBenh = b.MaBenh
        JOIN BACSI bs ON ddt.MaBS = bs.MaBS
        JOIN NGUOI n_bs ON bs.CMT = n_bs.CMT
        LEFT JOIN LANKHAM lk ON ddt.MaDot = lk.MaDot
        WHERE ddt.MaBN = :ma_bn
        ORDER BY ddt.NgayBatDau DESC, lk.SoThuTu ASC;
    """)

    result_hien_tai = db.session.execute(sql_hien_tai, {'ma_bn': ma_bn}).fetchall()
    result_lich_su = db.session.execute(sql_lich_su, {'ma_bn': ma_bn}).fetchall()

    return jsonify({
        'ThongTinCaNhan': {
            'MaBN': info.MaBN,
            'CMT': info.CMT,
            'HoTen': info.HoTen,
            'NgaySinh': str(info.NgaySinh),
            'DiaChi': info.DiaChi,
            'SoDienThoai': info.SoDienThoai
        },
        'TinhTrangHienTai': [{
            'MaBenh': r.MaBenh,
            'TenBenh': r.TenBenh,
            'SoLanKham': r.SoLanKhamChoBenhNay
        } for r in result_hien_tai],
        'LichSuKhamChua': [{
            'MaDot': r.MaDot,
            'TenBenh': r.TenBenh,
            'BacSi': r.TenBacSi,
            'NgayBatDau': str(r.NgayBatDau),
            'TrangThai': r.TrangThai,
            'MaLanKham': r.MaLanKham,
            'SoThuTu': r.SoThuTu,
            'TienKham': float(r.TienKham) if r.TienKham else 0
        } for r in result_lich_su]
    })


# -----------------------------------------------------------------------------
# 4. Tính Doanh thu Phòng khám (Tiền khám + Tiền bán thuốc)
# -----------------------------------------------------------------------------
@main_bp.route('/api/doanh-thu', methods=['GET'])
def tinh_doanh_thu():
    from_date = request.args.get('from_date')  # YYYY-MM-DD
    to_date = request.args.get('to_date')  # YYYY-MM-DD

    sql = text("""
        SELECT 
            COALESCE((
                SELECT SUM(TienKham) 
                FROM LANKHAM 
                WHERE (:from_date IS NULL OR NgayVao >= :from_date)
                  AND (:to_date IS NULL OR NgayVao <= :to_date)
            ), 0) AS TienKhamChua,

            COALESCE((
                SELECT SUM(dt.SoLuong * dt.DonGiaBan)
                FROM CHITIETDONTHUOC dt
                JOIN LANKHAM lk ON dt.MaLanKham = lk.MaLanKham
                WHERE (:from_date IS NULL OR lk.NgayVao >= :from_date)
                  AND (:to_date IS NULL OR lk.NgayVao <= :to_date)
            ), 0) AS TienBanThuoc;
    """)

    result = db.session.execute(sql, {'from_date': from_date, 'to_date': to_date}).fetchone()
    tien_kham = float(result.TienKhamChua)
    tien_thuoc = float(result.TienBanThuoc)

    return jsonify({
        'TienKhamChua': tien_kham,
        'TienBanThuoc': tien_thuoc,
        'TongDoanhThu': tien_kham + tien_thuoc
    })