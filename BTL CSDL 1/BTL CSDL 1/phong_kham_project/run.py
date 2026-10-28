from backend import create_app
from backend.config import Config

app = create_app()

if __name__ == "__main__":
    print(f"=== KHOI DONG BACKEND PHONG KHAM (DB_TYPE: {Config.DB_TYPE.upper()}) ===")
    app.run(host="0.0.0.0", port=5000, debug=True)