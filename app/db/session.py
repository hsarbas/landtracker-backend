# app/db/session.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.db.base import Base  # <- use the single Base

engine = create_engine(settings.sqlalchemy_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_models():
    # Import ALL model modules so metadata is populated before create_all
    from app.models import (
        user, role, refresh_token, otp_code, tie_point,  # existing
        property as prop, property_image, property_boundary, property_report  # NEW
    )  # noqa: F401
    Base.metadata.create_all(bind=engine)
