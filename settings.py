# settings.py
import os
from typing import List
from pydantic_settings import BaseSettings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


class Settings(BaseSettings):
    app_name: str = "Vision OCR Service"

    # Google creds
    creds_path: str = os.getenv(
        "GOOGLE_APPLICATION_CREDENTIALS",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys/vision-ocr.json")
    )

    # CORS
    cors_origins: List[str] = ["*"]



    # --- DB settings ---
    db_user: str = os.getenv("DB_USER", "postgres")
    db_password: str = os.getenv("DB_PASSWORD", "")
    db_host: str = os.getenv("DB_HOST", "127.0.0.1")
    db_port: int = int(os.getenv("DB_PORT", "5432"))
    db_name: str = os.getenv("DB_NAME", "landtracker_db")

    @property
    def database_url(self) -> str:
        # postgresql+psycopg2://user:pass@host:port/db
        if self.db_password:
            return (
                f"postgresql+psycopg2://{self.db_user}:{self.db_password}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}"
            )
        return (
            f"postgresql+psycopg2://{self.db_user}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()


def configure_cors(app: FastAPI):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
