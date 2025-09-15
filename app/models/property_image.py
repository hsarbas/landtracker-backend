from __future__ import annotations
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, ForeignKey

from app.db.base import Base


class PropertyImage(Base):
    __tablename__ = "property_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id", ondelete="CASCADE"), index=True)

    # Where you saved it (relative or absolute path/URL).
    file_path: Mapped[str] = mapped_column(String(512))
    original_name: Mapped[str] = mapped_column(String(256))
    order_index: Mapped[int] = mapped_column(Integer, default=0)  # supports future multi-image
    page_number: Mapped[int] = mapped_column(Integer, default=1)  # if ever you PDF->images

    property = relationship("Property", back_populates="images")
