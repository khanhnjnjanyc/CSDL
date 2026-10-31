from extensions import db

class Nguoi(db.Model):
    __tablename__ = 'NGUOI'
    CMT = db.Column(db.String(12), primary_key=True)
    HoTen = db.Column(db.String(100), nullable=False)
    NgaySinh = db.Column(db.Date, nullable=False)
    DiaChi = db.Column(db.String(255))
    SoDienThoai = db.Column(db.String(15))
    TrangThaiKhoa = db.Column(db.Boolean, default=False)  # False: Hoạt động, True: Khóa

    bac_si = db.relationship('BacSy', backref='nguoi', uselist=False, cascade="all, delete")
    y_ta = db.relationship('YTa', backref='nguoi', uselist=False, cascade="all, delete")
    benh_nhan = db.relationship('BenhNhan', backref='nguoi', uselist=False, cascade="all, delete")


class BacSy(db.Model):
    __tablename__ = 'BACSI'
    MaBS = db.Column(db.Integer, primary_key=True)
    CMT = db.Column(db.String(12), db.ForeignKey('NGUOI.CMT', ondelete='CASCADE', onupdate='CASCADE'), nullable=False, unique=True)
    BacNghe = db.Column(db.String(50), nullable=False)
    ThamNien = db.Column(db.Integer, db.CheckConstraint('ThamNien >= 0'))
    TrinhDoDaoTao = db.Column(db.String(100))
    ChuyenMon = db.Column(db.String(100), nullable=False)

    dot_dieu_tri = db.relationship('DotDieuTri', backref='bac_si', lazy=True)


class YTa(db.Model):
    __tablename__ = 'YTA'
    MaYTa = db.Column(db.Integer, primary_key=True)
    CMT = db.Column(db.String(12), db.ForeignKey('NGUOI.CMT', ondelete='CASCADE', onupdate='CASCADE'), nullable=False, unique=True)
    TrinhDo = db.Column(db.String(50), nullable=False)
    ThamNien = db.Column(db.Integer, db.CheckConstraint('ThamNien >= 0'))

    ho_tro = db.relationship('HoTro', backref='y_ta', lazy=True)


class BenhNhan(db.Model):
    __tablename__ = 'BENHNHAN'
    MaBN = db.Column(db.Integer, primary_key=True)
    CMT = db.Column(db.String(12), db.ForeignKey('NGUOI.CMT', ondelete='CASCADE', onupdate='CASCADE'), nullable=False, unique=True)

    dot_dieu_tri = db.relationship('DotDieuTri', backref='benh_nhan', lazy=True)


class Benh(db.Model):
    __tablename__ = 'BENH'
    MaBenh = db.Column(db.Integer, primary_key=True)
    TenBenh = db.Column(db.String(150), nullable=False, unique=True)

    dot_dieu_tri = db.relationship('DotDieuTri', backref='benh', lazy=True)


class Thuoc(db.Model):
    __tablename__ = 'THUOC'
    MaThuoc = db.Column(db.Integer, primary_key=True)
    TenThuoc = db.Column(db.String(150), nullable=False)
    DonViTinh = db.Column(db.String(30))
    DonGia = db.Column(db.Numeric(12, 0), db.CheckConstraint('DonGia >= 0'))
    SoLuongTon = db.Column(db.Integer, default=100, nullable=False) # Kiểm tra tồn kho

    chi_tiet_don_thuoc = db.relationship('ChiTietDonThuoc', backref='thuoc', lazy=True)


class DotDieuTri(db.Model):
    __tablename__ = 'DOTDIEUTRI'
    MaDot = db.Column(db.Integer, primary_key=True)
    MaBN = db.Column(db.Integer, db.ForeignKey('BENHNHAN.MaBN'), nullable=False)
    MaBenh = db.Column(db.Integer, db.ForeignKey('BENH.MaBenh'), nullable=False)
    MaBS = db.Column(db.Integer, db.ForeignKey('BACSI.MaBS'), nullable=False)
    NgayBatDau = db.Column(db.Date, nullable=False)
    NgayKetThuc = db.Column(db.Date)
    TrangThai = db.Column(db.String(20), nullable=False)

    lan_kham = db.relationship('LanKham', backref='dot_dieu_tri', lazy=True)


class LanKham(db.Model):
    __tablename__ = 'LANKHAM'
    MaLanKham = db.Column(db.Integer, primary_key=True)
    MaDot = db.Column(db.Integer, db.ForeignKey('DOTDIEUTRI.MaDot'), nullable=False)
    SoThuTu = db.Column(db.Integer, nullable=False)
    NgayVao = db.Column(db.Date, nullable=False)
    NgayRa = db.Column(db.Date)
    TienKham = db.Column(db.Numeric(12, 0))

    don_thuoc = db.relationship('ChiTietDonThuoc', backref='lan_kham', lazy=True)
    ho_tro = db.relationship('HoTro', backref='lan_kham', lazy=True)


class HoTro(db.Model):
    __tablename__ = 'HOTRO'
    MaYTa = db.Column(db.Integer, db.ForeignKey('YTA.MaYTa'), primary_key=True)
    MaLanKham = db.Column(db.Integer, db.ForeignKey('LANKHAM.MaLanKham'), primary_key=True)
    LoaiHoTro = db.Column(db.String(50), nullable=False)


class ChiTietDonThuoc(db.Model):
    __tablename__ = 'CHITIETDONTHUOC'
    MaLanKham = db.Column(db.Integer, db.ForeignKey('LANKHAM.MaLanKham'), primary_key=True)
    MaThuoc = db.Column(db.Integer, db.ForeignKey('THUOC.MaThuoc'), primary_key=True)
    SoLuong = db.Column(db.Integer, nullable=False)
    DonGiaBan = db.Column(db.Numeric(12, 0), nullable=False)