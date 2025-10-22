from __future__ import annotations
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Index, Float, String, ForeignKey

from app.db.base import Base


class PropertyBoundary(Base):
    __tablename__ = "property_boundaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(
        ForeignKey("properties.id", ondelete="CASCADE"), index=True
    )

    bearing: Mapped[str] = mapped_column(String(64))
    distance_m: Mapped[float] = mapped_column(Float)

    property = relationship("Property", back_populates="boundaries")

    __table_args__ = (
        Index("ix_property_boundaries_property_id_id", "property_id", "id"),
    )
