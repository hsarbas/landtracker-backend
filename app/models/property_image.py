from __future__ import annotations
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, ForeignKey, DateTime, func, UniqueConstraint, Index

from app.db.base import Base


class PropertyImage(Base):
    __tablename__ = "property_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(
        ForeignKey("properties.id", ondelete="CASCADE"), index=True
    )

    file_path: Mapped[str] = mapped_column(String(512))
    order_index: Mapped[int] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    property = relationship("Property", back_populates="images")

    __table_args__ = (
        UniqueConstraint("property_id", "order_index", name="uq_property_image_order"),
        Index("ix_property_images_property_id_order", "property_id", "order_index"),
    )
