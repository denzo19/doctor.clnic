import os

from env_loader import load_env_file


load_env_file(os.path.join(os.path.dirname(__file__), ".env"))


DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "doctor_health"),
    "port": int(os.environ.get("DB_PORT", "3306")),
}

SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret-key")
