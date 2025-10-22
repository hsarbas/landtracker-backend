# app/core/config.py
from __future__ import annotations
from typing import Optional, List, Literal
from urllib.parse import quote_plus
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from starlette.middleware.cors import CORSMiddleware


class Settings(BaseSettings):
    # Pydantic Settings
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",          # ignore unknown env keys safely
        case_sensitive=False,
    )

    # --- App ---
    app_name: str = "LandTracker"
    creds_path: str = Field("keys/vision-ocr.json", alias="GOOGLE_VISION_CREDS_PATH")

    # --- Security / JWT ---
    secret_key: str = Field("dev-super-secret-change-me", alias="SECRET_KEY")
    algorithm: str = Field("HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(30, alias="ACCESS_EXPIRE_MIN")
    refresh_token_expire_days: int = Field(7, alias="REFRESH_EXPIRE_DAYS")

    # --- Admin seed ---
    admin_email: Optional[str] = Field("admin@admin.com", alias="ADMIN_EMAIL")
    admin_password: str = Field("AdminPass123!", alias="ADMIN_PASSWORD")
    admin_mobile: Optional[str] = Field("+639123456789", alias="ADMIN_MOBILE")

    # --- Refresh cookie config ---
    refresh_cookie_name: str = Field("rt", alias="REFRESH_COOKIE_NAME")
    refresh_cookie_path: str = Field("/v1/auth/refresh", alias="REFRESH_COOKIE_PATH")
    refresh_cookie_samesite: Literal["lax", "none", "strict"] = Field("lax", alias="REFRESH_COOKIE_SAMESITE")
    refresh_cookie_secure: bool = Field(False, alias="REFRESH_COOKIE_SECURE")
    refresh_cookie_httponly: bool = True  # always True

    # --- OTP ---
    otp_length: int = Field(6, alias="OTP_LENGTH")
    otp_ttl_minutes: int = Field(5, alias="OTP_TTL_MINUTES")
    otp_max_attempts: int = Field(5, alias="OTP_MAX_ATTEMPTS")
    otp_resend_cooldown_seconds: int = Field(60, alias="OTP_RESEND_COOLDOWN_SECONDS")

    # --- Directories / Paths ---
    title_img_dir: str = Field("resources/uploads/title_images", alias="TITLE_IMG_DIR")
    reports_dir: str = Field("resources/reports", alias="LT_REPORTS_DIR")
    lt_logo_path: str = Field("app/static/logo.png", alias="LT_LOGO_PATH")

    # --- Database ---
    database_url: Optional[str] = Field(None, alias="DATABASE_URL")  # full URL override
    db_user: str = Field("landtracker", alias="DB_USER")
    db_password: str = Field("landtrackerpw1234", alias="DB_PASSWORD")
    db_host: str = Field("127.0.0.1", alias="DB_HOST")
    db_port: int = Field(5433, alias="DB_PORT")
    db_name: str = Field("landtracker_db", alias="DB_NAME")

    # --- SMTP / Email ---
    smtp_host: str = Field("smtp-relay.brevo.com", alias="SMTP_HOST")
    smtp_port: int = Field(587, alias="SMTP_PORT")
    smtp_user: str = Field(..., alias="SMTP_USER")
    smtp_password: str = Field(..., alias="SMTP_PASSWORD")
    smtp_from_name: str = Field("LandTracker", alias="SMTP_FROM_NAME")
    smtp_from_email: str = Field("no-reply@landtracker.ph", alias="SMTP_FROM_EMAIL")

    app_frontend_url: str = Field("http://localhost:9000", alias="APP_FRONTEND_URL")
    app_backend_url: str = Field("http://192.168.1.78:8000", alias="APP_BACKEND_URL")

    # --- CORS ---
    # Comma-separated in .env or leave default list
    allowed_origins: List[str] = [
        "http://localhost",
        "http://localhost:9000",
        "http://127.0.0.1:9000",
        "http://192.168.1.78:9000",
        "http://192.168.1.14:9000",
        "http://192.168.1.78:9500",
        "capacitor://localhost",
        "ionic://localhost",
    ]

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _parse_origins(cls, v):
        # Accept "a,b,c" or JSON array; pass lists through.
        if v is None:
            return []
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            "postgresql+psycopg2://"
            f"{self.db_user}:{quote_plus(self.db_password)}@"
            f"{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings()

# --- Backwards-compatible module-level constants (if other modules import them) ---
SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes
REFRESH_TOKEN_EXPIRE_DAYS = settings.refresh_token_expire_days

ADMIN_EMAIL = settings.admin_email
ADMIN_PASSWORD = settings.admin_password
ADMIN_MOBILE = settings.admin_mobile

REFRESH_COOKIE_NAME = settings.refresh_cookie_name
REFRESH_COOKIE_PATH = settings.refresh_cookie_path
REFRESH_COOKIE_SAMESITE = settings.refresh_cookie_samesite
REFRESH_COOKIE_SECURE = settings.refresh_cookie_secure
REFRESH_COOKIE_HTTPONLY = settings.refresh_cookie_httponly

OTP_LENGTH = settings.otp_length
OTP_TTL_MINUTES = settings.otp_ttl_minutes
OTP_MAX_ATTEMPTS = settings.otp_max_attempts
OTP_RESEND_COOLDOWN_SECONDS = settings.otp_resend_cooldown_seconds

SMTP_HOST = settings.smtp_host
SMTP_PORT = settings.smtp_port
SMTP_USER = settings.smtp_user
SMTP_PASSWORD = settings.smtp_password
SMTP_FROM_NAME = settings.smtp_from_name
SMTP_FROM_EMAIL = settings.smtp_from_email

APP_FRONTEND_URL = settings.app_frontend_url
APP_BACKEND_URL = settings.app_backend_url


ALLOWED_ORIGINS = settings.allowed_origins  # used by CapacitorOriginFix/configure_cors


# --- CORS helpers (unchanged call sites) ---
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


def configure_cors(app):
    http_origins = [o for o in settings.allowed_origins if o.startswith("http")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=http_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
