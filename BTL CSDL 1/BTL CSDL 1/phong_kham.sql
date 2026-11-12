
CREATE DATABASE IF NOT EXISTS phong_kham
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE phong_kham;
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS TAI_KHOAN;
DROP TABLE IF EXISTS CT_DON_THUOC;
DROP TABLE IF EXISTS DON_THUOC;
DROP TABLE IF EXISTS Y_TA_HO_TRO;
DROP TABLE IF EXISTS CHI_TIET_CHAN_DOAN;
DROP TABLE IF EXISTS DOT_DIEU_TRI;
DROP TABLE IF EXISTS LAN_KHAM;
DROP TABLE IF EXISTS BAC_SI_CHUYEN_MON;
DROP TABLE IF EXISTS THUOC;
DROP TABLE IF EXISTS BENH;
DROP TABLE IF EXISTS CHUYEN_MON;
DROP TABLE IF EXISTS BENH_NHAN;
DROP TABLE IF EXISTS Y_TA;
DROP TABLE IF EXISTS BAC_SI;
DROP TABLE IF EXISTS NHAN_VIEN;
DROP TABLE IF EXISTS NGUOI;
SET FOREIGN_KEY_CHECKS = 1;
CREATE TABLE NGUOI (
  ma_nguoi INT AUTO_INCREMENT PRIMARY KEY,
  cmt VARCHAR(12) NOT NULL UNIQUE,
  ho_ten VARCHAR(100) NOT NULL,
  ngay_sinh DATE NOT NULL,
  gioi_tinh VARCHAR(10) NOT NULL,
  dia_chi VARCHAR(255),
  so_dien_thoai VARCHAR(15) NULL,
  trang_thai_khoa TINYINT(1) NOT NULL DEFAULT 0,
  CONSTRAINT ck_nguoi_gioi_tinh CHECK (gioi_tinh IN ('Nam','Nu','Khac'))
) ENGINE=InnoDB;

CREATE TABLE NHAN_VIEN (
  ma_nguoi INT PRIMARY KEY,
  ma_nhan_vien VARCHAR(20) NOT NULL UNIQUE,
  ngay_vao_lam DATE NOT NULL,
  trang_thai VARCHAR(20) NOT NULL DEFAULT 'DANG_LAM',
  CONSTRAINT ck_nv_trang_thai CHECK (trang_thai IN ('DANG_LAM','NGHI_VIEC')),
  CONSTRAINT fk_nv_nguoi FOREIGN KEY (ma_nguoi) REFERENCES NGUOI(ma_nguoi)
) ENGINE=InnoDB;

CREATE TABLE BAC_SI (
  ma_nguoi INT PRIMARY KEY,
  ma_bac_si VARCHAR(20) NOT NULL UNIQUE,
  bac_nghe VARCHAR(50) NOT NULL,
  trinh_do_dao_tao VARCHAR(100),
  tham_nien INT NOT NULL DEFAULT 0,
  CONSTRAINT ck_bs_tham_nien CHECK (tham_nien >= 0),
  CONSTRAINT fk_bs_nv FOREIGN KEY (ma_nguoi) REFERENCES NHAN_VIEN(ma_nguoi)
) ENGINE=InnoDB;

CREATE TABLE Y_TA (
  ma_nguoi INT PRIMARY KEY,
  trinh_do VARCHAR(50) NOT NULL,
  tham_nien INT NOT NULL DEFAULT 0,
  CONSTRAINT ck_yt_tham_nien CHECK (tham_nien >= 0),
  CONSTRAINT fk_yt_nv FOREIGN KEY (ma_nguoi) REFERENCES NHAN_VIEN(ma_nguoi)
) ENGINE=InnoDB;

CREATE TABLE BENH_NHAN (
  ma_nguoi INT PRIMARY KEY,
  ma_benh_nhan VARCHAR(20) NOT NULL UNIQUE, 
  CONSTRAINT fk_bn_nguoi FOREIGN KEY (ma_nguoi) REFERENCES NGUOI(ma_nguoi)
) ENGINE=InnoDB;

DELIMITER $$
CREATE TRIGGER trg_bs_disjoint BEFORE INSERT ON BAC_SI
FOR EACH ROW
BEGIN
  IF EXISTS (SELECT 1 FROM Y_TA WHERE ma_nguoi = NEW.ma_nguoi) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Nhan vien da la y ta, khong the dong thoi la bac si';
  END IF;
END$$

CREATE TRIGGER trg_yt_disjoint BEFORE INSERT ON Y_TA
FOR EACH ROW
BEGIN
  IF EXISTS (SELECT 1 FROM BAC_SI WHERE ma_nguoi = NEW.ma_nguoi) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Nhan vien da la bac si, khong the dong thoi la y ta';
  END IF;
END$$
DELIMITER ;

CREATE TABLE CHUYEN_MON (
  ma_chuyen_mon INT AUTO_INCREMENT PRIMARY KEY,
  ten_chuyen_mon VARCHAR(100) NOT NULL UNIQUE
) ENGINE=InnoDB;

CREATE TABLE BAC_SI_CHUYEN_MON (
  ma_bac_si VARCHAR(20) NOT NULL,           
  ma_chuyen_mon INT NOT NULL,
  PRIMARY KEY (ma_bac_si, ma_chuyen_mon),
  CONSTRAINT fk_bscm_bs FOREIGN KEY (ma_bac_si) REFERENCES BAC_SI(ma_bac_si),
  CONSTRAINT fk_bscm_cm FOREIGN KEY (ma_chuyen_mon) REFERENCES CHUYEN_MON(ma_chuyen_mon)
) ENGINE=InnoDB;

CREATE TABLE BENH (
  ma_benh INT AUTO_INCREMENT PRIMARY KEY,
  ten_benh VARCHAR(150) NOT NULL,
  mo_ta TEXT
) ENGINE=InnoDB;

CREATE TABLE THUOC (
  ma_thuoc INT AUTO_INCREMENT PRIMARY KEY,
  ten_thuoc VARCHAR(150) NOT NULL,
  don_vi VARCHAR(30),
  don_gia_hien_tai DECIMAL(12,0) NOT NULL,
  ton_kho INT NOT NULL DEFAULT 0,
  CONSTRAINT ck_thuoc_gia CHECK (don_gia_hien_tai >= 0),
  CONSTRAINT ck_thuoc_ton CHECK (ton_kho >= 0)
) ENGINE=InnoDB;

CREATE TABLE LAN_KHAM (
  ma_lan_kham INT AUTO_INCREMENT PRIMARY KEY,
  ma_benh_nhan INT NOT NULL,
  thoi_diem_vao DATETIME NOT NULL,
  thoi_diem_ra DATETIME,
  ghi_chu TEXT,
  CONSTRAINT fk_lk_bn FOREIGN KEY (ma_benh_nhan) REFERENCES BENH_NHAN(ma_nguoi),
  CONSTRAINT ck_lk_time CHECK (thoi_diem_ra IS NULL OR thoi_diem_ra >= thoi_diem_vao),
  INDEX ix_lk_bn_time (ma_benh_nhan, thoi_diem_vao)
) ENGINE=InnoDB;

CREATE TABLE DOT_DIEU_TRI (
  ma_dot INT AUTO_INCREMENT PRIMARY KEY,
  ma_benh_nhan INT NOT NULL,
  ma_benh INT NOT NULL,
  ngay_bat_dau DATE NOT NULL,
  ngay_ket_thuc DATE,
  trang_thai VARCHAR(20) NOT NULL DEFAULT 'DANG_DIEU_TRI',
  ma_lan_kham_ket_thuc INT,
  dot_dang_mo TINYINT GENERATED ALWAYS AS
    (CASE WHEN trang_thai = 'DANG_DIEU_TRI' THEN 1 ELSE NULL END) STORED,
  UNIQUE KEY uq_dot_mo (ma_benh_nhan, ma_benh, dot_dang_mo),
  UNIQUE KEY uq_dot_close_ref (ma_lan_kham_ket_thuc, ma_dot),
  CONSTRAINT ck_dot_status CHECK (trang_thai IN ('DANG_DIEU_TRI','KHOI')),
  CONSTRAINT ck_dot_dates CHECK (ngay_ket_thuc IS NULL OR ngay_ket_thuc >= ngay_bat_dau),
  CONSTRAINT ck_dot_state CHECK (
    (trang_thai = 'DANG_DIEU_TRI' AND ngay_ket_thuc IS NULL AND ma_lan_kham_ket_thuc IS NULL)
    OR (trang_thai = 'KHOI' AND ngay_ket_thuc IS NOT NULL AND ma_lan_kham_ket_thuc IS NOT NULL)
  ),
  CONSTRAINT fk_dot_bn FOREIGN KEY (ma_benh_nhan) REFERENCES BENH_NHAN(ma_nguoi),
  CONSTRAINT fk_dot_benh FOREIGN KEY (ma_benh) REFERENCES BENH(ma_benh),
  INDEX ix_dot_benh_ngay (ma_benh, ngay_bat_dau)
) ENGINE=InnoDB;

CREATE TABLE CHI_TIET_CHAN_DOAN (
  ma_lan_kham INT NOT NULL,
  ma_dot INT NOT NULL,
  ma_bac_si VARCHAR(20) NOT NULL,            
  phi_kham_chua DECIMAL(12,0) NOT NULL,
  ket_luan TEXT,
  PRIMARY KEY (ma_lan_kham, ma_dot),
  CONSTRAINT ck_phi CHECK (phi_kham_chua >= 0),
  CONSTRAINT fk_ctcd_lk FOREIGN KEY (ma_lan_kham) REFERENCES LAN_KHAM(ma_lan_kham),
  CONSTRAINT fk_ctcd_dot FOREIGN KEY (ma_dot) REFERENCES DOT_DIEU_TRI(ma_dot),
  CONSTRAINT fk_ctcd_bs FOREIGN KEY (ma_bac_si) REFERENCES BAC_SI(ma_bac_si),
  INDEX ix_ctcd_dot (ma_dot, ma_lan_kham)
) ENGINE=InnoDB;

ALTER TABLE DOT_DIEU_TRI
  ADD CONSTRAINT fk_dot_lan_ket_thuc
  FOREIGN KEY (ma_lan_kham_ket_thuc, ma_dot)
  REFERENCES CHI_TIET_CHAN_DOAN(ma_lan_kham, ma_dot);

DELIMITER $$
CREATE TRIGGER trg_ctcd_bn_ins BEFORE INSERT ON CHI_TIET_CHAN_DOAN
FOR EACH ROW
BEGIN
  DECLARE v_bn_lan INT;
  DECLARE v_bn_dot INT;
  DECLARE v_trang_thai VARCHAR(20);
  SELECT ma_benh_nhan INTO v_bn_lan FROM LAN_KHAM WHERE ma_lan_kham = NEW.ma_lan_kham;
  SELECT ma_benh_nhan, trang_thai INTO v_bn_dot, v_trang_thai FROM DOT_DIEU_TRI WHERE ma_dot = NEW.ma_dot;
  IF v_bn_lan <> v_bn_dot THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Lan kham va dot dieu tri phai cung benh nhan';
  END IF;
  IF v_trang_thai <> 'DANG_DIEU_TRI' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Khong the them chan doan vao dot da dong';
  END IF;
END$$

CREATE TRIGGER trg_ctcd_bn_upd BEFORE UPDATE ON CHI_TIET_CHAN_DOAN
FOR EACH ROW
BEGIN
  DECLARE v_bn_lan INT;
  DECLARE v_bn_dot INT;
  DECLARE v_trang_thai VARCHAR(20);
  SELECT ma_benh_nhan INTO v_bn_lan FROM LAN_KHAM WHERE ma_lan_kham = NEW.ma_lan_kham;
  SELECT ma_benh_nhan, trang_thai INTO v_bn_dot, v_trang_thai FROM DOT_DIEU_TRI WHERE ma_dot = NEW.ma_dot;
  IF v_bn_lan <> v_bn_dot THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Lan kham va dot dieu tri phai cung benh nhan';
  END IF;
  IF NEW.ma_dot <> OLD.ma_dot AND v_trang_thai <> 'DANG_DIEU_TRI' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Khong the chuyen chan doan vao dot da dong';
  END IF;
END$$

CREATE TRIGGER trg_dot_khong_mo_lai BEFORE UPDATE ON DOT_DIEU_TRI
FOR EACH ROW
BEGIN
  IF OLD.trang_thai = 'KHOI' AND NEW.trang_thai <> 'KHOI' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Dot da khoi khong duoc mo lai; tai phat tao dot moi';
  END IF;
END$$
DELIMITER ;

-- Dong bo kieu du lieu ma_ho_tro INT theo Trang 9 (Muc 2.4) cua Bao cao Yeu cau 1 moi
CREATE TABLE Y_TA_HO_TRO (
  ma_ho_tro INT AUTO_INCREMENT PRIMARY KEY,
  ma_lan_kham INT NOT NULL,
  ma_y_ta INT NOT NULL,                      -- = Y_TA.ma_nguoi
  vai_tro VARCHAR(50) NOT NULL,
  thoi_diem DATETIME NOT NULL,
  ghi_chu VARCHAR(255),
  CONSTRAINT fk_ytht_lk FOREIGN KEY (ma_lan_kham) REFERENCES LAN_KHAM(ma_lan_kham),
  CONSTRAINT fk_ytht_yta FOREIGN KEY (ma_y_ta) REFERENCES Y_TA(ma_nguoi),
  INDEX ix_ytht_yta_time (ma_y_ta, thoi_diem)
) ENGINE=InnoDB;

CREATE TABLE DON_THUOC (
  ma_don INT AUTO_INCREMENT PRIMARY KEY,
  ma_lan_kham INT NOT NULL,
  ngay_ke DATETIME NOT NULL,
  trang_thai VARCHAR(20) NOT NULL DEFAULT 'DA_KE',
  thoi_diem_cap DATETIME,
  CONSTRAINT ck_don_status CHECK (trang_thai IN ('DA_KE','DA_CAP','HUY')),
  CONSTRAINT ck_don_cap CHECK (
    (trang_thai = 'DA_CAP' AND thoi_diem_cap IS NOT NULL AND thoi_diem_cap >= ngay_ke)
    OR (trang_thai IN ('DA_KE','HUY') AND thoi_diem_cap IS NULL)
  ),
  CONSTRAINT fk_don_lk FOREIGN KEY (ma_lan_kham) REFERENCES LAN_KHAM(ma_lan_kham),
  INDEX ix_don_lk (ma_lan_kham),
  INDEX ix_don_cap (trang_thai, thoi_diem_cap)
) ENGINE=InnoDB;

CREATE TABLE CT_DON_THUOC (
  ma_don INT NOT NULL,
  ma_thuoc INT NOT NULL,
  so_luong INT NOT NULL,
  don_gia_tai_thoi_diem DECIMAL(12,0) NOT NULL,
  huong_dan_dung VARCHAR(255),
  PRIMARY KEY (ma_don, ma_thuoc),
  CONSTRAINT ck_ctdt_qty CHECK (so_luong > 0),
  CONSTRAINT ck_ctdt_price CHECK (don_gia_tai_thoi_diem >= 0),
  CONSTRAINT fk_ctdt_don FOREIGN KEY (ma_don) REFERENCES DON_THUOC(ma_don),
  CONSTRAINT fk_ctdt_thuoc FOREIGN KEY (ma_thuoc) REFERENCES THUOC(ma_thuoc)
) ENGINE=InnoDB;

-- Dong bo kieu du lieu role VARCHAR(20) + CHECK theo Trang 10 (Muc 2.5) cua Bao cao Yeu cau 1 moi
CREATE TABLE TAI_KHOAN (
  cmt VARCHAR(12) PRIMARY KEY,
  role VARCHAR(20) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  active TINYINT(1) NOT NULL DEFAULT 1,
  CONSTRAINT ck_tk_role CHECK (role IN ('ADMIN','BAC_SI','Y_TA')),
  CONSTRAINT fk_tk_nguoi FOREIGN KEY (cmt) REFERENCES NGUOI(cmt)
) ENGINE=InnoDB;

INSERT INTO NGUOI (ma_nguoi,cmt,ho_ten,ngay_sinh,gioi_tinh,dia_chi,so_dien_thoai) VALUES
(1,'001000000001','Nguyen An','1998-02-14','Nam','Ha Noi','0900000001'),
(2,'001000000002','Tran Binh','1985-07-20','Nam','Ha Noi','0900000002'),
(3,'001000000003','Le Chi','2001-11-03','Nu','Ha Noi','0900000003'),
(4,'001000000004','Pham Dung','1992-05-09','Khac','Ha Noi','0900000004'),
(5,'001000000005','Hoang Em','1995-12-12','Nam','Ha Noi','0900000005'),
(10,'001000000010','Bac si Minh','1980-01-01','Nam','Ha Noi','0900000010'),
(11,'001000000011','Bac si Lan','1984-04-02','Nu','Ha Noi','0900000011'),
(20,'001000000020','Y ta Hoa','1990-08-12','Nu','Ha Noi','0900000020'),
(21,'001000000021','Y ta Nam','1991-06-15','Nam','Ha Noi','0900000021');

INSERT INTO NHAN_VIEN (ma_nguoi,ma_nhan_vien,ngay_vao_lam) VALUES
(10,'NV010','2020-01-01'),(11,'NV011','2021-03-01'),
(20,'NV020','2022-02-01'),(21,'NV021','2023-05-01');
INSERT INTO BAC_SI (ma_nguoi,ma_bac_si,bac_nghe,trinh_do_dao_tao,tham_nien) VALUES
(10,'BS010','Bac si chinh','Thac si',6),(11,'BS011','Bac si','Dai hoc',4);
INSERT INTO Y_TA (ma_nguoi,trinh_do,tham_nien) VALUES
(20,'Cao dang',4),(21,'Dai hoc',3);
INSERT INTO BENH_NHAN (ma_nguoi,ma_benh_nhan) VALUES
(1,'BN001'),(2,'BN002'),(3,'BN003'),(4,'BN004'),(5,'BN005'),(21,'BN006');

INSERT INTO CHUYEN_MON (ma_chuyen_mon,ten_chuyen_mon) VALUES
(1,'Noi tong quat'),(2,'Da lieu'),(3,'Ho hap');
INSERT INTO BAC_SI_CHUYEN_MON (ma_bac_si,ma_chuyen_mon) VALUES ('BS010',1),('BS010',3),('BS011',2);
INSERT INTO BENH (ma_benh,ten_benh,mo_ta) VALUES
(1,'Cum mua','Benh truyen nhiem duong ho hap'),
(2,'Dau nua dau','Dau dau tung con'),
(3,'Viem da','Viem da di ung hoac tiep xuc');
INSERT INTO THUOC (ma_thuoc,ten_thuoc,don_vi,don_gia_hien_tai,ton_kho) VALUES
(1,'Paracetamol','vien',5000,500),(2,'Vitamin C 500mg','vien',2000,800),
(3,'Kem boi da','tuyp',45000,100),(4,'Ibuprofen','vien',8000,300);

INSERT INTO LAN_KHAM (ma_lan_kham,ma_benh_nhan,thoi_diem_vao,thoi_diem_ra,ghi_chu) VALUES
(1001,1,'2026-10-02 08:00:00','2026-10-02 09:00:00','BN001 cum lan 1'),
(1002,1,'2026-10-05 08:30:00','2026-10-05 09:20:00','BN001 cum lan 2'),
(1003,1,'2026-10-10 10:00:00','2026-10-10 11:00:00','BN001 cum lan 3, khoi'),
(1004,2,'2026-09-15 09:00:00','2026-09-15 10:00:00','BN002 dot cum cu, khoi'),
(1005,2,'2026-10-12 09:00:00','2026-10-12 10:00:00','BN002 tai phat cum'),
(1006,3,'2026-10-03 13:00:00','2026-10-03 14:00:00','BN003 dau nua dau lan 1'),
(1007,3,'2026-10-17 13:00:00','2026-10-17 14:00:00','BN003 dau nua dau lan 2'),
(1008,4,'2026-10-20 15:00:00','2026-10-20 15:45:00','BN004 viem da'),
(1009,5,'2026-10-22 09:00:00','2026-10-22 10:15:00','BN005 hai benh trong mot luot');

-- Cac dot ban dau deu DANG_DIEU_TRI; dot khoi duoc dong bang UPDATE sau khi co chan doan.
INSERT INTO DOT_DIEU_TRI (ma_dot,ma_benh_nhan,ma_benh,ngay_bat_dau) VALUES
(5001,2,1,'2026-09-15'),(5003,1,1,'2026-10-02'),
(5004,3,2,'2026-10-03'),(5005,4,3,'2026-10-20'),
(5006,5,1,'2026-10-22'),(5007,5,3,'2026-10-22');
INSERT INTO CHI_TIET_CHAN_DOAN (ma_lan_kham,ma_dot,ma_bac_si,phi_kham_chua,ket_luan) VALUES
(1001,5003,'BS010',200000,'Theo doi cum'),
(1002,5003,'BS010',150000,'Tiep tuc dieu tri cum'),
(1003,5003,'BS011',180000,'Khoi cum'),
(1004,5001,'BS010',200000,'Khoi cum dot cu'),
(1006,5004,'BS011',250000,'Theo doi dau nua dau'),
(1007,5004,'BS011',180000,'Tiep tuc dieu tri'),
(1008,5005,'BS011',160000,'Viem da'),
(1009,5006,'BS010',150000,'Cum nhe'),
(1009,5007,'BS011',200000,'Viem da tiep xuc');
UPDATE DOT_DIEU_TRI SET ngay_ket_thuc='2026-09-15',trang_thai='KHOI',ma_lan_kham_ket_thuc=1004 WHERE ma_dot=5001;
UPDATE DOT_DIEU_TRI SET ngay_ket_thuc='2026-10-10',trang_thai='KHOI',ma_lan_kham_ket_thuc=1003 WHERE ma_dot=5003;
INSERT INTO DOT_DIEU_TRI (ma_dot,ma_benh_nhan,ma_benh,ngay_bat_dau) VALUES (5002,2,1,'2026-10-12');
INSERT INTO CHI_TIET_CHAN_DOAN (ma_lan_kham,ma_dot,ma_bac_si,phi_kham_chua,ket_luan) VALUES
(1005,5002,'BS010',220000,'Tai phat cum, mo dot moi');

INSERT INTO Y_TA_HO_TRO (ma_ho_tro,ma_lan_kham,ma_y_ta,vai_tro,thoi_diem,ghi_chu) VALUES
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
(11,1009,20,'Theo doi','2026-10-22 09:30:00','Su kien rieng, duoc tinh rieng');

INSERT INTO DON_THUOC (ma_don,ma_lan_kham,ngay_ke,trang_thai,thoi_diem_cap) VALUES
(7001,1001,'2026-10-02 08:50:00','DA_CAP','2026-10-02 09:00:00'),
(7002,1003,'2026-10-10 10:50:00','DA_CAP','2026-10-10 11:00:00'),
(7003,1005,'2026-10-12 09:50:00','DA_CAP','2026-10-12 10:00:00'),
(7004,1008,'2026-10-20 15:35:00','DA_CAP','2026-10-20 15:45:00'),
(7005,1009,'2026-10-22 10:00:00','DA_CAP','2026-10-22 10:15:00'),
(7006,1007,'2026-10-17 13:50:00','HUY',NULL),
(7007,1006,'2026-10-03 13:50:00','DA_KE',NULL),
(7008,1004,'2026-09-15 09:50:00','DA_CAP','2026-10-01 08:00:00');
INSERT INTO CT_DON_THUOC (ma_don,ma_thuoc,so_luong,don_gia_tai_thoi_diem,huong_dan_dung) VALUES
(7001,1,10,5000,'Sau an'),(7001,2,10,1800,'Hang ngay'),(7002,1,6,5000,'Khi sot'),
(7003,1,8,5200,'Sau an'),(7003,4,5,8000,'Theo don'),(7004,3,1,43000,'Boi ngoai da'),
(7005,1,10,5000,'Sau an'),(7005,2,20,2000,'Sang chieu'),
(7005,3,1,45000,'Boi vung viem'),(7005,4,6,8000,'Khi dau'),
(7006,1,10,5000,'Khi sot'),
(7007,4,4,8000,'Khi dau'),
(7008,2,5,2000,'Hang ngay');

INSERT INTO TAI_KHOAN (cmt,role,password_hash,active) VALUES
('001000000010','ADMIN','demo123',1),
('001000000011','BAC_SI','demo123',1),
('001000000020','Y_TA','demo123',1);


SET @thang_bat_dau = '2026-10-01';
SET @thang_sau = DATE_ADD(@thang_bat_dau, INTERVAL 1 MONTH);
SET @ma_benh_nhan_can_xem = 2;

SELECT b.ma_benh, b.ten_benh,
       COUNT(DISTINCT d.ma_benh_nhan) AS so_benh_nhan,
       COUNT(DISTINCT d.ma_dot) AS so_dot_mac
FROM LAN_KHAM lk
JOIN CHI_TIET_CHAN_DOAN cd ON cd.ma_lan_kham = lk.ma_lan_kham
JOIN DOT_DIEU_TRI d ON d.ma_dot = cd.ma_dot
JOIN BENH b ON b.ma_benh = d.ma_benh
WHERE lk.thoi_diem_vao >= @thang_bat_dau
  AND lk.thoi_diem_vao < @thang_sau
GROUP BY b.ma_benh, b.ten_benh
ORDER BY so_benh_nhan DESC, so_dot_mac DESC, b.ten_benh;

WITH bs_thuong AS (
  SELECT cd.ma_bac_si, COUNT(*) AS so_dot_khoi
  FROM DOT_DIEU_TRI d
  JOIN CHI_TIET_CHAN_DOAN cd
    ON cd.ma_lan_kham = d.ma_lan_kham_ket_thuc AND cd.ma_dot = d.ma_dot
  WHERE d.trang_thai = 'KHOI'
    AND d.ngay_ket_thuc >= @thang_bat_dau AND d.ngay_ket_thuc < @thang_sau
  GROUP BY cd.ma_bac_si
), yt_thuong AS (
  SELECT ma_y_ta, COUNT(*) AS so_su_kien
  FROM Y_TA_HO_TRO
  WHERE thoi_diem >= @thang_bat_dau AND thoi_diem < @thang_sau
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
SELECT 'Y_TA', nv.ma_nhan_vien, NULL,
       n.ho_ten, 5000000,
       COALESCE(t.so_su_kien,0),
       200000 * COALESCE(t.so_su_kien,0),
       5000000 + 200000 * COALESCE(t.so_su_kien,0)
FROM Y_TA yt JOIN NHAN_VIEN nv ON nv.ma_nguoi=yt.ma_nguoi
JOIN NGUOI n ON n.ma_nguoi=yt.ma_nguoi
LEFT JOIN yt_thuong t ON t.ma_y_ta=yt.ma_nguoi
WHERE nv.trang_thai='DANG_LAM' OR COALESCE(t.so_su_kien,0)>0
ORDER BY loai, ma_nhan_vien;

SELECT bn.ma_benh_nhan, n.cmt, n.ho_ten, n.ngay_sinh, n.gioi_tinh,
       n.dia_chi, n.so_dien_thoai, nv.ma_nhan_vien AS ma_nhan_vien_neu_co
FROM BENH_NHAN bn
JOIN NGUOI n ON n.ma_nguoi = bn.ma_nguoi
LEFT JOIN NHAN_VIEN nv ON nv.ma_nguoi = bn.ma_nguoi
WHERE bn.ma_nguoi = @ma_benh_nhan_can_xem;

SELECT bn.ma_benh_nhan, n.ho_ten, lk.ma_lan_kham, lk.thoi_diem_vao, lk.thoi_diem_ra,
       b.ten_benh, d.ma_dot, d.trang_thai AS tinh_trang_dot,
       d.ngay_bat_dau, d.ngay_ket_thuc,
       ROW_NUMBER() OVER (PARTITION BY d.ma_dot ORDER BY lk.thoi_diem_vao, lk.ma_lan_kham) AS lan_thu_trong_dot,
       COUNT(*) OVER (PARTITION BY d.ma_dot) AS tong_lan_kham_trong_dot,
       bs.ma_bac_si, bs_n.ho_ten AS ten_bac_si, cd.phi_kham_chua, cd.ket_luan
FROM BENH_NHAN bn JOIN NGUOI n ON n.ma_nguoi=bn.ma_nguoi
JOIN LAN_KHAM lk ON lk.ma_benh_nhan=bn.ma_nguoi
JOIN CHI_TIET_CHAN_DOAN cd ON cd.ma_lan_kham=lk.ma_lan_kham
JOIN DOT_DIEU_TRI d ON d.ma_dot=cd.ma_dot
JOIN BENH b ON b.ma_benh=d.ma_benh
JOIN BAC_SI bs ON bs.ma_bac_si=cd.ma_bac_si
JOIN NGUOI bs_n ON bs_n.ma_nguoi=bs.ma_nguoi
WHERE bn.ma_nguoi=@ma_benh_nhan_can_xem
ORDER BY lk.thoi_diem_vao, b.ten_benh;

SELECT bn.ma_benh_nhan, n.ho_ten, b.ten_benh, d.ma_dot, d.ngay_bat_dau,
       COUNT(cd.ma_lan_kham) AS so_lan_kham,
       MAX(lk.thoi_diem_vao) AS lan_kham_gan_nhat
FROM BENH_NHAN bn JOIN NGUOI n ON n.ma_nguoi=bn.ma_nguoi
JOIN DOT_DIEU_TRI d ON d.ma_benh_nhan=bn.ma_nguoi
JOIN BENH b ON b.ma_benh=d.ma_benh
JOIN CHI_TIET_CHAN_DOAN cd ON cd.ma_dot=d.ma_dot
JOIN LAN_KHAM lk ON lk.ma_lan_kham=cd.ma_lan_kham
WHERE bn.ma_nguoi=@ma_benh_nhan_can_xem AND d.trang_thai='DANG_DIEU_TRI'
GROUP BY bn.ma_benh_nhan, n.ho_ten, b.ten_benh, d.ma_dot, d.ngay_bat_dau
ORDER BY b.ten_benh;

SELECT lk.ma_lan_kham, lk.thoi_diem_vao, yt.ma_nguoi AS ma_y_ta,
       n.ho_ten AS ten_y_ta, h.ma_ho_tro, h.vai_tro, h.thoi_diem, h.ghi_chu
FROM LAN_KHAM lk JOIN Y_TA_HO_TRO h ON h.ma_lan_kham=lk.ma_lan_kham
JOIN Y_TA yt ON yt.ma_nguoi=h.ma_y_ta JOIN NGUOI n ON n.ma_nguoi=yt.ma_nguoi
WHERE lk.ma_benh_nhan=@ma_benh_nhan_can_xem
ORDER BY lk.thoi_diem_vao, h.thoi_diem;

SELECT lk.ma_lan_kham, lk.thoi_diem_vao, d.ma_don, d.ngay_ke,
       d.trang_thai AS trang_thai_don, d.thoi_diem_cap,
       t.ten_thuoc, ct.so_luong, ct.don_gia_tai_thoi_diem,
       ct.so_luong*ct.don_gia_tai_thoi_diem AS thanh_tien,
       CASE WHEN d.trang_thai='DA_CAP' THEN 'CO' ELSE 'KHONG' END AS tinh_vao_doanh_thu,
       ct.huong_dan_dung
FROM LAN_KHAM lk JOIN DON_THUOC d ON d.ma_lan_kham=lk.ma_lan_kham
JOIN CT_DON_THUOC ct ON ct.ma_don=d.ma_don JOIN THUOC t ON t.ma_thuoc=ct.ma_thuoc
WHERE lk.ma_benh_nhan=@ma_benh_nhan_can_xem
ORDER BY lk.thoi_diem_vao, d.ma_don, t.ten_thuoc;

SELECT kham.doanh_thu_kham_chua, thuoc.doanh_thu_thuoc,
       kham.doanh_thu_kham_chua + thuoc.doanh_thu_thuoc AS tong_doanh_thu
FROM (
  SELECT COALESCE(SUM(cd.phi_kham_chua),0) AS doanh_thu_kham_chua
  FROM CHI_TIET_CHAN_DOAN cd JOIN LAN_KHAM lk ON lk.ma_lan_kham=cd.ma_lan_kham
  WHERE lk.thoi_diem_vao >= @thang_bat_dau AND lk.thoi_diem_vao < @thang_sau
) kham
CROSS JOIN (
  SELECT COALESCE(SUM(ct.so_luong*ct.don_gia_tai_thoi_diem),0) AS doanh_thu_thuoc
  FROM CT_DON_THUOC ct JOIN DON_THUOC d ON d.ma_don=ct.ma_don
  WHERE d.trang_thai = 'DA_CAP'
    AND d.thoi_diem_cap >= @thang_bat_dau AND d.thoi_diem_cap < @thang_sau
) thuoc;

SELECT ten_bang, so_ban_ghi, so_dong_bao_cao,
       CASE WHEN so_ban_ghi = so_dong_bao_cao THEN 'OK' ELSE 'LECH' END AS ket_qua
FROM (
  SELECT 'NGUOI' AS ten_bang, COUNT(*) AS so_ban_ghi, 9 AS so_dong_bao_cao FROM NGUOI
  UNION ALL SELECT 'NHAN_VIEN', COUNT(*), 4 FROM NHAN_VIEN
  UNION ALL SELECT 'BAC_SI', COUNT(*), 2 FROM BAC_SI
  UNION ALL SELECT 'Y_TA', COUNT(*), 2 FROM Y_TA
  UNION ALL SELECT 'BENH_NHAN', COUNT(*), 6 FROM BENH_NHAN
  UNION ALL SELECT 'CHUYEN_MON', COUNT(*), 3 FROM CHUYEN_MON
  UNION ALL SELECT 'BAC_SI_CHUYEN_MON', COUNT(*), 3 FROM BAC_SI_CHUYEN_MON
  UNION ALL SELECT 'BENH', COUNT(*), 3 FROM BENH
  UNION ALL SELECT 'THUOC', COUNT(*), 4 FROM THUOC
  UNION ALL SELECT 'LAN_KHAM', COUNT(*), 9 FROM LAN_KHAM
  UNION ALL SELECT 'DOT_DIEU_TRI', COUNT(*), 7 FROM DOT_DIEU_TRI
  UNION ALL SELECT 'CHI_TIET_CHAN_DOAN', COUNT(*), 10 FROM CHI_TIET_CHAN_DOAN
  UNION ALL SELECT 'Y_TA_HO_TRO', COUNT(*), 11 FROM Y_TA_HO_TRO
  UNION ALL SELECT 'DON_THUOC', COUNT(*), 8 FROM DON_THUOC
  UNION ALL SELECT 'CT_DON_THUOC', COUNT(*), 13 FROM CT_DON_THUOC
  UNION ALL SELECT 'TAI_KHOAN', COUNT(*), 3 FROM TAI_KHOAN
) x;
