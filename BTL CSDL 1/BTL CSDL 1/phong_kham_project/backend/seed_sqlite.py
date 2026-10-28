import os
from sqlalchemy import text
from backend.config import Config
from backend.database import engine

def init_sqlite_db(force_reset=False):
    """Tạo bảng, Trigger R5-R7 và nạp dữ liệu mẫu tháng 10/2026 khi chạy chế độ SQLite"""
    if Config.DB_TYPE != "sqlite":
        return

    if force_reset and os.path.exists(Config.SQLITE_PATH):
        engine.dispose()
        os.remove(Config.SQLITE_PATH)

    with engine.begin() as conn:
        exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='NGUOI'")
        ).fetchone()
        if exists and not force_reset:
            return

        ddl_statements = [
            """CREATE TABLE NGUOI (
                ma_nguoi INTEGER PRIMARY KEY AUTOINCREMENT,
                cmt VARCHAR(12) NOT NULL UNIQUE,
                ho_ten VARCHAR(100) NOT NULL,
                ngay_sinh DATE NOT NULL,
                gioi_tinh VARCHAR(10) NOT NULL,
                dia_chi VARCHAR(255),
                so_dien_thoai VARCHAR(15),
                trang_thai_khoa INTEGER NOT NULL DEFAULT 0,
                CONSTRAINT ck_nguoi_gioi_tinh CHECK (gioi_tinh IN ('Nam','Nu','Khac'))
            );""",
            """CREATE TABLE NHAN_VIEN (
                ma_nguoi INTEGER PRIMARY KEY,
                ma_nhan_vien VARCHAR(20) NOT NULL UNIQUE,
                ngay_vao_lam DATE NOT NULL,
                trang_thai VARCHAR(20) NOT NULL DEFAULT 'DANG_LAM',
                CONSTRAINT ck_nv_trang_thai CHECK (trang_thai IN ('DANG_LAM','NGHI_VIEC')),
                CONSTRAINT fk_nv_nguoi FOREIGN KEY (ma_nguoi) REFERENCES NGUOI(ma_nguoi)
            );""",
            """CREATE TABLE BAC_SI (
                ma_nguoi INTEGER PRIMARY KEY,
                ma_bac_si VARCHAR(20) NOT NULL UNIQUE,
                bac_nghe VARCHAR(50) NOT NULL,
                trinh_do_dao_tao VARCHAR(100),
                tham_nien INTEGER NOT NULL DEFAULT 0,
                CONSTRAINT ck_bs_tham_nien CHECK (tham_nien >= 0),
                CONSTRAINT fk_bs_nv FOREIGN KEY (ma_nguoi) REFERENCES NHAN_VIEN(ma_nguoi)
            );""",
            """CREATE TABLE Y_TA (
                ma_nguoi INTEGER PRIMARY KEY,
                trinh_do VARCHAR(50) NOT NULL,
                tham_nien INTEGER NOT NULL DEFAULT 0,
                CONSTRAINT ck_yt_tham_nien CHECK (tham_nien >= 0),
                CONSTRAINT fk_yt_nv FOREIGN KEY (ma_nguoi) REFERENCES NHAN_VIEN(ma_nguoi)
            );""",
            """CREATE TABLE BENH_NHAN (
                ma_nguoi INTEGER PRIMARY KEY,
                ma_benh_nhan VARCHAR(20) NOT NULL UNIQUE,
                CONSTRAINT fk_bn_nguoi FOREIGN KEY (ma_nguoi) REFERENCES NGUOI(ma_nguoi)
            );""",
            """CREATE TABLE CHUYEN_MON (
                ma_chuyen_mon INTEGER PRIMARY KEY AUTOINCREMENT,
                ten_chuyen_mon VARCHAR(100) NOT NULL UNIQUE
            );""",
            """CREATE TABLE BAC_SI_CHUYEN_MON (
                ma_bac_si VARCHAR(20) NOT NULL,
                ma_chuyen_mon INTEGER NOT NULL,
                PRIMARY KEY (ma_bac_si, ma_chuyen_mon),
                CONSTRAINT fk_bscm_bs FOREIGN KEY (ma_bac_si) REFERENCES BAC_SI(ma_bac_si),
                CONSTRAINT fk_bscm_cm FOREIGN KEY (ma_chuyen_mon) REFERENCES CHUYEN_MON(ma_chuyen_mon)
            );""",
            """CREATE TABLE BENH (
                ma_benh INTEGER PRIMARY KEY AUTOINCREMENT,
                ten_benh VARCHAR(150) NOT NULL,
                mo_ta TEXT
            );""",
            """CREATE TABLE THUOC (
                ma_thuoc INTEGER PRIMARY KEY AUTOINCREMENT,
                ten_thuoc VARCHAR(150) NOT NULL,
                don_vi VARCHAR(30),
                don_gia_hien_tai DECIMAL(12,0) NOT NULL,
                ton_kho INTEGER NOT NULL DEFAULT 0,
                CONSTRAINT ck_thuoc_gia CHECK (don_gia_hien_tai >= 0),
                CONSTRAINT ck_thuoc_ton CHECK (ton_kho >= 0)
            );""",
            """CREATE TABLE LAN_KHAM (
                ma_lan_kham INTEGER PRIMARY KEY AUTOINCREMENT,
                ma_benh_nhan INTEGER NOT NULL,
                thoi_diem_vao DATETIME NOT NULL,
                thoi_diem_ra DATETIME,
                ghi_chu TEXT,
                CONSTRAINT fk_lk_bn FOREIGN KEY (ma_benh_nhan) REFERENCES BENH_NHAN(ma_nguoi),
                CONSTRAINT ck_lk_time CHECK (thoi_diem_ra IS NULL OR thoi_diem_ra >= thoi_diem_vao)
            );""",
            """CREATE TABLE DOT_DIEU_TRI (
                ma_dot INTEGER PRIMARY KEY AUTOINCREMENT,
                ma_benh_nhan INTEGER NOT NULL,
                ma_benh INTEGER NOT NULL,
                ngay_bat_dau DATE NOT NULL,
                ngay_ket_thuc DATE,
                trang_thai VARCHAR(20) NOT NULL DEFAULT 'DANG_DIEU_TRI',
                ma_lan_kham_ket_thuc INTEGER,
                dot_dang_mo INTEGER GENERATED ALWAYS AS (CASE WHEN trang_thai = 'DANG_DIEU_TRI' THEN 1 ELSE NULL END) STORED,
                UNIQUE (ma_benh_nhan, ma_benh, dot_dang_mo),
                UNIQUE (ma_lan_kham_ket_thuc, ma_dot),
                CONSTRAINT ck_dot_status CHECK (trang_thai IN ('DANG_DIEU_TRI','KHOI')),
                CONSTRAINT ck_dot_dates CHECK (ngay_ket_thuc IS NULL OR ngay_ket_thuc >= ngay_bat_dau),
                CONSTRAINT ck_dot_state CHECK (
                    (trang_thai = 'DANG_DIEU_TRI' AND ngay_ket_thuc IS NULL AND ma_lan_kham_ket_thuc IS NULL)
                    OR (trang_thai = 'KHOI' AND ngay_ket_thuc IS NOT NULL AND ma_lan_kham_ket_thuc IS NOT NULL)
                ),
                CONSTRAINT fk_dot_bn FOREIGN KEY (ma_benh_nhan) REFERENCES BENH_NHAN(ma_nguoi),
                CONSTRAINT fk_dot_benh FOREIGN KEY (ma_benh) REFERENCES BENH(ma_benh)
            );""",
            """CREATE TABLE CHI_TIET_CHAN_DOAN (
                ma_lan_kham INTEGER NOT NULL,
                ma_dot INTEGER NOT NULL,
                ma_bac_si VARCHAR(20) NOT NULL,
                phi_kham_chua DECIMAL(12,0) NOT NULL,
                ket_luan TEXT,
                PRIMARY KEY (ma_lan_kham, ma_dot),
                CONSTRAINT ck_phi CHECK (phi_kham_chua >= 0),
                CONSTRAINT fk_ctcd_lk FOREIGN KEY (ma_lan_kham) REFERENCES LAN_KHAM(ma_lan_kham),
                CONSTRAINT fk_ctcd_dot FOREIGN KEY (ma_dot) REFERENCES DOT_DIEU_TRI(ma_dot),
                CONSTRAINT fk_ctcd_bs FOREIGN KEY (ma_bac_si) REFERENCES BAC_SI(ma_bac_si)
            );""",
            """CREATE TABLE Y_TA_HO_TRO (
                ma_ho_tro INTEGER PRIMARY KEY AUTOINCREMENT,
                ma_lan_kham INTEGER NOT NULL,
                ma_y_ta INTEGER NOT NULL,
                vai_tro VARCHAR(50) NOT NULL,
                thoi_diem DATETIME NOT NULL,
                ghi_chu VARCHAR(255),
                CONSTRAINT fk_ytht_lk FOREIGN KEY (ma_lan_kham) REFERENCES LAN_KHAM(ma_lan_kham),
                CONSTRAINT fk_ytht_yta FOREIGN KEY (ma_y_ta) REFERENCES Y_TA(ma_nguoi)
            );""",
            """CREATE TABLE DON_THUOC (
                ma_don INTEGER PRIMARY KEY AUTOINCREMENT,
                ma_lan_kham INTEGER NOT NULL,
                ngay_ke DATETIME NOT NULL,
                trang_thai VARCHAR(20) NOT NULL DEFAULT 'DA_KE',
                thoi_diem_cap DATETIME,
                CONSTRAINT ck_don_status CHECK (trang_thai IN ('DA_KE','DA_CAP','HUY')),
                CONSTRAINT ck_don_cap CHECK ((trang_thai = 'DA_CAP' AND thoi_diem_cap IS NOT NULL) OR (trang_thai IN ('DA_KE','HUY') AND thoi_diem_cap IS NULL)),
                CONSTRAINT fk_don_lk FOREIGN KEY (ma_lan_kham) REFERENCES LAN_KHAM(ma_lan_kham)
            );""",
            """CREATE TABLE CT_DON_THUOC (
                ma_don INTEGER NOT NULL,
                ma_thuoc INTEGER NOT NULL,
                so_luong INTEGER NOT NULL,
                don_gia_tai_thoi_diem DECIMAL(12,0) NOT NULL,
                huong_dan_dung VARCHAR(255),
                PRIMARY KEY (ma_don, ma_thuoc),
                CONSTRAINT ck_ctdt_qty CHECK (so_luong > 0),
                CONSTRAINT ck_ctdt_price CHECK (don_gia_tai_thoi_diem >= 0),
                CONSTRAINT fk_ctdt_don FOREIGN KEY (ma_don) REFERENCES DON_THUOC(ma_don),
                CONSTRAINT fk_ctdt_thuoc FOREIGN KEY (ma_thuoc) REFERENCES THUOC(ma_thuoc)
            );""",
            """CREATE TABLE TAI_KHOAN (
                cmt VARCHAR(12) PRIMARY KEY,
                role VARCHAR(20) NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                CONSTRAINT fk_tk_nguoi FOREIGN KEY (cmt) REFERENCES NGUOI(cmt)
            );""",
            """CREATE TRIGGER trg_ctcd_bn_ins BEFORE INSERT ON CHI_TIET_CHAN_DOAN
            BEGIN
                SELECT CASE
                    WHEN (SELECT ma_benh_nhan FROM LAN_KHAM WHERE ma_lan_kham = NEW.ma_lan_kham) !=
                         (SELECT ma_benh_nhan FROM DOT_DIEU_TRI WHERE ma_dot = NEW.ma_dot)
                    THEN RAISE(ABORT, 'Lan kham va dot dieu tri phai cung benh nhan')
                    WHEN (SELECT trang_thai FROM DOT_DIEU_TRI WHERE ma_dot = NEW.ma_dot) != 'DANG_DIEU_TRI'
                    THEN RAISE(ABORT, 'Khong the them chan doan vao dot da dong')
                END;
            END;""",
            """CREATE TRIGGER trg_dot_khong_mo_lai BEFORE UPDATE ON DOT_DIEU_TRI
            BEGIN
                SELECT CASE
                    WHEN OLD.trang_thai = 'KHOI' AND NEW.trang_thai != 'KHOI'
                    THEN RAISE(ABORT, 'Dot da khoi khong duoc mo lai; tai phat tao dot moi')
                    WHEN NEW.trang_thai = 'KHOI' AND NOT EXISTS (
                        SELECT 1 FROM CHI_TIET_CHAN_DOAN
                        WHERE ma_lan_kham = NEW.ma_lan_kham_ket_thuc AND ma_dot = NEW.ma_dot
                    )
                    THEN RAISE(ABORT, 'Luot kham ket thuc phai thuoc dot dieu tri nay')
                END;
            END;"""
        ]
        for stmt in ddl_statements:
            conn.execute(text(stmt))

        seed_statements = [
            """INSERT INTO NGUOI (ma_nguoi,cmt,ho_ten,ngay_sinh,gioi_tinh,dia_chi,so_dien_thoai) VALUES
            (1,'001000000001','Nguyen An','1998-02-14','Nam','Ha Noi','0900000001'),
            (2,'001000000002','Tran Binh','1985-07-20','Nam','Ha Noi','0900000002'),
            (3,'001000000003','Le Chi','2001-11-03','Nu','Ha Noi','0900000003'),
            (4,'001000000004','Pham Dung','1992-05-09','Khac','Ha Noi','0900000004'),
            (5,'001000000005','Hoang Em','1995-12-12','Nam','Ha Noi','0900000005'),
            (10,'001000000010','Bac si Minh','1980-01-01','Nam','Ha Noi','0900000010'),
            (11,'001000000011','Bac si Lan','1984-04-02','Nu','Ha Noi','0900000011'),
            (20,'001000000020','Y ta Hoa','1990-08-12','Nu','Ha Noi','0900000020'),
            (21,'001000000021','Y ta Nam','1991-06-15','Nam','Ha Noi','0900000021');""",
            """INSERT INTO NHAN_VIEN (ma_nguoi,ma_nhan_vien,ngay_vao_lam) VALUES
            (10,'NV010','2020-01-01'),(11,'NV011','2021-03-01'),
            (20,'NV020','2022-02-01'),(21,'NV021','2023-05-01');""",
            """INSERT INTO BAC_SI (ma_nguoi,ma_bac_si,bac_nghe,trinh_do_dao_tao,tham_nien) VALUES
            (10,'BS010','Bac si chinh','Thac si',6),(11,'BS011','Bac si','Dai hoc',4);""",
            """INSERT INTO Y_TA (ma_nguoi,trinh_do,tham_nien) VALUES
            (20,'Cao dang',4),(21,'Dai hoc',3);""",
            """INSERT INTO BENH_NHAN (ma_nguoi,ma_benh_nhan) VALUES
            (1,'BN001'),(2,'BN002'),(3,'BN003'),(4,'BN004'),(5,'BN005');""",
            """INSERT INTO CHUYEN_MON (ma_chuyen_mon,ten_chuyen_mon) VALUES
            (1,'Noi tong quat'),(2,'Da lieu'),(3,'Ho hap');""",
            """INSERT INTO BAC_SI_CHUYEN_MON VALUES ('BS010',1),('BS010',3),('BS011',2);""",
            """INSERT INTO BENH (ma_benh,ten_benh,mo_ta) VALUES
            (1,'Cum mua','Benh truyen nhiem duong ho hap'),
            (2,'Dau nua dau','Dau dau tung con'),
            (3,'Viem da','Viem da di ung hoac tiep xuc');""",
            """INSERT INTO THUOC (ma_thuoc,ten_thuoc,don_vi,don_gia_hien_tai,ton_kho) VALUES
            (1,'Paracetamol','vien',5000,500),(2,'Vitamin C 500mg','vien',2000,800),
            (3,'Kem boi da','tuyp',45000,100),(4,'Ibuprofen','vien',8000,300);""",
            """INSERT INTO LAN_KHAM (ma_lan_kham,ma_benh_nhan,thoi_diem_vao,thoi_diem_ra,ghi_chu) VALUES
            (1001,1,'2026-10-02 08:00:00','2026-10-02 09:00:00','BN001 cum lan 1'),
            (1002,1,'2026-10-05 08:30:00','2026-10-05 09:20:00','BN001 cum lan 2'),
            (1003,1,'2026-10-10 10:00:00','2026-10-10 11:00:00','BN001 cum lan 3, khoi'),
            (1004,2,'2026-09-15 09:00:00','2026-09-15 10:00:00','BN002 dot cum cu, khoi'),
            (1005,2,'2026-10-12 09:00:00','2026-10-12 10:00:00','BN002 tai phat cum'),
            (1006,3,'2026-10-03 13:00:00','2026-10-03 14:00:00','BN003 dau nua dau lan 1'),
            (1007,3,'2026-10-17 13:00:00','2026-10-17 14:00:00','BN003 dau nua dau lan 2'),
            (1008,4,'2026-10-20 15:00:00','2026-10-20 15:45:00','BN004 viem da'),
            (1009,5,'2026-10-22 09:00:00','2026-10-22 10:15:00','BN005 hai benh trong mot luot');""",
            """INSERT INTO DOT_DIEU_TRI (ma_dot,ma_benh_nhan,ma_benh,ngay_bat_dau) VALUES
            (5001,2,1,'2026-09-15'),(5003,1,1,'2026-10-02'),
            (5004,3,2,'2026-10-03'),(5005,4,3,'2026-10-20'),
            (5006,5,1,'2026-10-22'),(5007,5,3,'2026-10-22');""",
            """INSERT INTO CHI_TIET_CHAN_DOAN (ma_lan_kham,ma_dot,ma_bac_si,phi_kham_chua,ket_luan) VALUES
            (1001,5003,'BS010',200000,'Theo doi cum'),
            (1002,5003,'BS010',150000,'Tiep tuc dieu tri cum'),
            (1003,5003,'BS011',180000,'Khoi cum'),
            (1004,5001,'BS010',200000,'Khoi cum dot cu'),
            (1006,5004,'BS011',250000,'Theo doi dau nua dau'),
            (1007,5004,'BS011',180000,'Tiep tuc dieu tri'),
            (1008,5005,'BS011',160000,'Viem da'),
            (1009,5006,'BS010',150000,'Cum nhe'),
            (1009,5007,'BS011',200000,'Viem da tiep xuc');""",
            """UPDATE DOT_DIEU_TRI SET ngay_ket_thuc='2026-09-15',trang_thai='KHOI',ma_lan_kham_ket_thuc=1004 WHERE ma_dot=5001;""",
            """UPDATE DOT_DIEU_TRI SET ngay_ket_thuc='2026-10-10',trang_thai='KHOI',ma_lan_kham_ket_thuc=1003 WHERE ma_dot=5003;""",
            """INSERT INTO DOT_DIEU_TRI (ma_dot,ma_benh_nhan,ma_benh,ngay_bat_dau) VALUES (5002,2,1,'2026-10-12');""",
            """INSERT INTO CHI_TIET_CHAN_DOAN VALUES (1005,5002,'BS010',220000,'Tai phat cum, mo dot moi');""",
            """INSERT INTO Y_TA_HO_TRO (ma_ho_tro,ma_lan_kham,ma_y_ta,vai_tro,thoi_diem,ghi_chu) VALUES
            (1,1001,20,'Tiep don','2026-10-02 08:05:00','Do sinh hieu'),
            (2,1001,21,'Theo doi','2026-10-02 08:15:00',''),
            (3,1002,20,'Cap thuoc','2026-10-05 08:40:00',''),
            (4,1003,21,'Theo doi','2026-10-10 10:10:00',''),
            (5,1004,20,'Tiem thuoc','2026-09-15 09:10:00',''),
            (6,1005,20,'Tiep don','2026-10-12 09:05:00',''),
            (7,1006,21,'Theo doi','2026-10-03 13:10:00',''),
            (8,1007,20,'Cap thuoc','2026-10-17 13:10:00',''),
            (9,1008,21,'Cham soc','2026-10-20 15:05:00',''),
            (10,1009,20,'Tiep don','2026-10-22 09:05:00',''),
            (11,1009,20,'Theo doi','2026-10-22 09:30:00','Su kien rieng, duoc tinh rieng');""",
            """INSERT INTO DON_THUOC (ma_don,ma_lan_kham,ngay_ke,trang_thai,thoi_diem_cap) VALUES
            (7001,1001,'2026-10-02 08:50:00','DA_CAP','2026-10-02 09:00:00'),
            (7002,1003,'2026-10-10 10:50:00','DA_CAP','2026-10-10 11:00:00'),
            (7003,1005,'2026-10-12 09:50:00','DA_CAP','2026-10-12 10:00:00'),
            (7004,1008,'2026-10-20 15:35:00','DA_CAP','2026-10-20 15:45:00'),
            (7005,1009,'2026-10-22 10:00:00','DA_CAP','2026-10-22 10:15:00');""",
            """INSERT INTO CT_DON_THUOC (ma_don,ma_thuoc,so_luong,don_gia_tai_thoi_diem,huong_dan_dung) VALUES
            (7001,1,10,5000,'Sau an'),(7001,2,10,1800,'Hang ngay'),(7002,1,6,5000,'Khi sot'),
            (7003,1,8,5200,'Sau an'),(7003,4,5,8000,'Theo don'),(7004,3,1,43000,'Boi ngoai da'),
            (7005,1,10,5000,'Sau an'),(7005,2,20,2000,'Sang chieu'),
            (7005,3,1,45000,'Boi vung viem'),(7005,4,6,8000,'Khi dau');""",
            """INSERT INTO TAI_KHOAN (cmt, role, password_hash, active) VALUES
            ('001000000010', 'ADMIN', 'demo123', 1),
            ('001000000011', 'BAC_SI', 'demo123', 1),
            ('001000000020', 'Y_TA', 'demo123', 1);"""
        ]
        for stmt in seed_statements:
            conn.execute(text(stmt))