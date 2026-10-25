import os

class Config:
    # Thông tin kết nối MySQL Aiven Cloud từ ảnh của Chủ nhân
    HOST = os.getenv('DB_HOST', 'mysql-2930dc81-btlcsdlptit.b.aivencloud.com')
    PORT = os.getenv('DB_PORT', '20146')
    USER = os.getenv('DB_USER', 'avnadmin')
    PASSWORD = os.getenv('DB_PASSWORD', 'AVNS_I5Go44IW2rg3Ir8u3jy')
    DB_NAME = os.getenv('DB_NAME', 'PhongKhamTuNhan')

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{USER}:{PASSWORD}@{HOST}:{PORT}/{DB_NAME}?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'phongkham-secret-key'