# models.py
from sqlalchemy import String, Float, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class TiePoint(Base):
    __tablename__ = "tie_points"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    tie_point_name: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    description:   Mapped[str | None] = mapped_column(Text, nullable=True)
    province:      Mapped[str | None] = mapped_column(String(64), nullable=True)
    municipality:  Mapped[str | None] = mapped_column(String(64), nullable=True)
    northing:      Mapped[float | None] = mapped_column(Float, nullable=True)
    easting:       Mapped[float | None] = mapped_column(Float, nullable=True)
