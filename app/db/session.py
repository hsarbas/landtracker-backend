from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from .base import Base

# Use the URL assembled by Settings
engine = create_engine(settings.sqlalchemy_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_models():
    # import models so metadata is populated
    from app.models import tie_point  # noqa: F401
    Base.metadata.create_all(bind=engine)
