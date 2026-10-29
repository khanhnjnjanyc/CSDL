import os
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from backend.config import Config
from backend.seed_sqlite import init_sqlite_db
from backend.routes import all_blueprints


def create_app():
    base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    template_dir = os.path.join(base_dir, "templates")
    # Hỗ trợ cả tên thư mục 'Static' và 'static'
    static_dir = (
        os.path.join(base_dir, "Static")
        if os.path.isdir(os.path.join(base_dir, "Static"))
        else os.path.join(base_dir, "static")
    )

    app = Flask(
        __name__,
        template_folder=template_dir,
        static_folder=static_dir,
        static_url_path="/static",
    )
    app.config.from_object(Config)
    CORS(app)

    # Tự động khởi tạo SQLite DB nếu đang ở chế độ sqlite
    init_sqlite_db()

    # Đăng ký tất cả 6 nhánh API Blueprints
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
            "message": "Backend Quản lý Phòng khám đang hoạt động tốt!",
        })

    # Xử lý lỗi 404 và 500 cho các route API
    @app.errorhandler(404)
    def handle_404(e):
        if request.path.startswith("/api/"):
            return (
                jsonify({
                    "success": False,
                    "message": f"Endpoint {request.path} không tồn tại (404 Not Found)!",
                    "error": "404 Not Found",
                }),
                404,
            )
        return render_template("index.html", db_type=Config.DB_TYPE.upper()), 404

    @app.errorhandler(500)
    def handle_500(e):
        if request.path.startswith("/api/"):
            return (
                jsonify({
                    "success": False,
                    "message": "Lỗi máy chủ nội bộ (500 Internal Server Error)!",
                    "error": str(e),
                }),
                500,
            )
        return jsonify({"success": False, "message": "Lỗi máy chủ nội bộ!"}), 500

    return app
