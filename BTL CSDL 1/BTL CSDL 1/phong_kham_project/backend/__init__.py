import os
from flask import Flask, jsonify, render_template
from flask_cors import CORS
from backend.config import Config
from backend.seed_sqlite import init_sqlite_db
from backend.routes import all_blueprints

def create_app():
    base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, "templates"),
        static_folder=os.path.join(base_dir, "static"),
    )
    app.config.from_object(Config)
    CORS(app)

    # Tự động khởi tạo SQLite DB nếu đang ở chế độ sqlite
    init_sqlite_db()

    # Đăng ký tất cả các nhánh API Blueprints
    for bp in all_blueprints:
        app.register_blueprint(bp)

    # Route mở giao diện trang chủ MedCare (Frontend)
    @app.route("/")
    def index():
        return render_template("index.html", db_type=Config.DB_TYPE.upper())

    # Route kiểm tra nhanh trạng thái Backend
    @app.route("/api/health")
    def health_check():
        return jsonify({
            "status": "OK",
            "db_type": Config.DB_TYPE.upper(),
            "message": "Backend Quản lý Phòng khám đang hoạt động tốt!"
        })

    return app