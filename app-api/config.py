import json
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from firebase_admin import credentials

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(
            f"Set the {name} environment variable before starting the API."
        )
    return value


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [
        item.strip() for item in os.getenv(name, default).split(",") if item.strip()
    ]


class Config:
    JWT_SECRET_KEY = required_env("JWT_SECRET_KEY")
    JWT_TOKEN_LOCATION = ["headers", "cookies"]
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        seconds=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES_SECONDS", "86400"))
    )
    JWT_COOKIE_SECURE = env_bool("JWT_COOKIE_SECURE", False)
    JWT_COOKIE_SAMESITE = "Lax"
    UPLOAD_FOLDER = "uploads/"

    CORS_ORIGINS = env_list("CORS_ORIGINS", "http://localhost:8080")
    FIREBASE_INIT_REQUIRED = env_bool("FIREBASE_INIT_REQUIRED", True)
    FIREBASE_STORAGE_BUCKET = os.getenv("FIREBASE_STORAGE_BUCKET", "")


def get_firebase_credential():
    raw_json = os.getenv("FIREBASE_CREDENTIALS_JSON", "").strip()
    credential_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "").strip()

    if raw_json:
        return credentials.Certificate(json.loads(raw_json))

    if credential_path:
        path = Path(credential_path).expanduser()
        if not path.is_absolute():
            path = BASE_DIR / path
        return credentials.Certificate(str(path))

    if Config.FIREBASE_INIT_REQUIRED:
        raise RuntimeError(
            "Set FIREBASE_CREDENTIALS_JSON or FIREBASE_CREDENTIALS_PATH before starting the API."
        )

    return None


def get_firebase_web_config() -> dict[str, str]:
    return {
        "apiKey": os.getenv("FIREBASE_WEB_API_KEY", ""),
        "authDomain": os.getenv("FIREBASE_WEB_AUTH_DOMAIN", ""),
        "projectId": os.getenv("FIREBASE_WEB_PROJECT_ID", ""),
        "storageBucket": os.getenv("FIREBASE_WEB_STORAGE_BUCKET", ""),
        "messagingSenderId": os.getenv("FIREBASE_WEB_MESSAGING_SENDER_ID", ""),
        "appId": os.getenv("FIREBASE_WEB_APP_ID", ""),
    }
