from typing import List, Optional
from urllib.parse import quote_plus
from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.cors import CORSMiddleware
from typing import Iterable, List, Tuple
from pydantic_settings import BaseSettings, SettingsConfigDict
import os

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-super-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_EXPIRE_MIN", 30))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get("REFRESH_EXPIRE_DAYS", 7))

# DB is already configured in your project via app/db/session.py -> just keep using it.
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@admin.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "AdminPass123!")
ADMIN_MOBILE = os.environ.get("ADMIN_MOBILE", "+639123456789")

REFRESH_COOKIE_NAME = os.environ.get("REFRESH_COOKIE_NAME", "rt")
REFRESH_COOKIE_PATH = os.environ.get("REFRESH_COOKIE_PATH", "/api/v1/auth/refresh")
REFRESH_COOKIE_SAMESITE = os.environ.get("REFRESH_COOKIE_SAMESITE", "lax")  # "lax" or "none"
REFRESH_COOKIE_SECURE = os.environ.get("REFRESH_COOKIE_SECURE", "false")
REFRESH_COOKIE_HTTPONLY = True  # always True for security

OTP_LENGTH = int(os.getenv("OTP_LENGTH", 6))
OTP_TTL_MINUTES = int(os.getenv("OTP_TTL_MINUTES", 5))
OTP_MAX_ATTEMPTS = int(os.getenv("OTP_MAX_ATTEMPTS", 5))
OTP_RESEND_COOLDOWN_SECONDS = int(os.getenv("OTP_RESEND_COOLDOWN_SECONDS", 60))

ALLOWED_ORIGINS = [
    "http://localhost",            # REQUIRED (shim rewrites Origin to this)
    "http://localhost:9000",
    "http://127.0.0.1:9000",
    "http://192.168.1.7:9500",
    "http://192.168.1.32:9500",
    "capacitor://localhost",
    "ionic://localhost",
]


class CapacitorOriginFix:
    def __init__(self, app, capacitor_origins=("capacitor://localhost", "ionic://localhost")):
        self.app = app
        self.capacitor_origins = set(capacitor_origins)

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            return await self.app(scope, receive, send)

        headers = list(scope.get("headers") or [])
        orig_origin = None
        for k, v in headers:
            if k.lower() == b"origin":
                orig_origin = v.decode()
                break

        replaced = False
        if orig_origin and orig_origin in self.capacitor_origins:
            new_headers = [(k, v) for (k, v) in headers if k.lower() != b"origin"]
            new_headers.append((b"origin", b"http://localhost"))
            scope["headers"] = new_headers
            replaced = True

        async def send_wrapper(message):
            if replaced and message["type"] == "http.response.start":
                hdrs = list(message.get("headers") or [])
                # replace or add ACAO with the real capacitor origin
                for i, (k, v) in enumerate(hdrs):
                    if k.lower() == b"access-control-allow-origin":
                        hdrs[i] = (k, orig_origin.encode())
                        break
                else:
                    hdrs.append((b"access-control-allow-origin", orig_origin.encode()))
                if not any(k.lower() == b"vary" for k, _ in hdrs):
                    hdrs.append((b"vary", b"Origin"))
                message["headers"] = hdrs
            await send(message)

        return await self.app(scope, receive, send_wrapper)


class Settings(BaseSettings):
    # --- App ---
    app_name: str = "LandTracker"
    creds_path: str = "keys/vision-ocr.json"

    # --- DB settings ---
    # Prefer a single DATABASE_URL, but also support individual parts
    database_url: Optional[str] = None          # e.g. postgresql+psycopg2://user:pass@host:5432/db
    db_user: str = "landtracker"
    db_password: str = "landtrackerpw1234"                        # will be URL-escaped
    db_host: str = "127.0.0.1"
    db_port: int = 5433
    db_name: str = "landtracker_db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def sqlalchemy_url(self) -> str:
        """Build the SQLAlchemy URL, allowing DATABASE_URL override."""
        if self.database_url:
            return self.database_url
        return (
            "postgresql+psycopg2://"
            f"{self.db_user}:{quote_plus(self.db_password)}@"
            f"{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings()


def configure_cors(app):
    http_origins = [o for o in ALLOWED_ORIGINS if o.startswith("http")]
    # print("CORS allow_origins =>", http_origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=http_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
