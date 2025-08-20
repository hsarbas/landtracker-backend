from typing import List, Optional
from urllib.parse import quote_plus
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- App ---
    app_name: str = "LandTracker"
    creds_path: str = "keys/vision-ocr.json"
    cors_origins: List[str] = [
        "capacitor://localhost",
        "http://localhost:9000",
        "http://127.0.0.1",
        "http://192.168.1.20",
        "http://192.168.1.5",
    ]

    # --- DB settings ---
    # Prefer a single DATABASE_URL, but also support individual parts
    database_url: Optional[str] = None          # e.g. postgresql+psycopg2://user:pass@host:5432/db
    db_user: str = "postgres"
    db_password: str = ""                        # will be URL-escaped
    db_host: str = "127.0.0.1"
    db_port: int = 5432
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

def configure_cors(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
