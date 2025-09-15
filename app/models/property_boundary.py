from __future__ import annotations
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, Float, String, ForeignKey

from app.db.base import Base


class PropertyBoundary(Base):
    __tablename__ = "property_boundaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id", ondelete="CASCADE"), index=True)

    idx: Mapped[int] = mapped_column(Integer)  # 1..n order
    bearing: Mapped[str | None] = mapped_column(String(64))
    distance_m: Mapped[float | None] = mapped_column(Float)

    start_lat: Mapped[float | None] = mapped_column(Float)
    start_lng: Mapped[float | None] = mapped_column(Float)
    end_lat: Mapped[float | None] = mapped_column(Float)
    end_lng: Mapped[float | None] = mapped_column(Float)

    raw_text: Mapped[str | None] = mapped_column(String(512))

    property = relationship("Property", back_populates="boundaries")
