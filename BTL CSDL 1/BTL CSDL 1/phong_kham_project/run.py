from backend import create_app
from backend.config import Config

app = create_app()

if __name__ == "__main__":
    print(f"=== KHOI DONG BACKEND PHONG KHAM (DB_TYPE: {Config.DB_TYPE.upper()}) ===")
    print(f"=== SERVER RUNNING AT http://{Config.HOST}:{Config.PORT} ===")
    app.run(host=Config.HOST, port=Config.PORT, debug=True)
