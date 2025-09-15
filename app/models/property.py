from __future__ import annotations
from datetime import datetime
from typing import Optional, List

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Integer, Float, ForeignKey, DateTime, JSON, Boolean

from app.db.base import Base


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    # OCR-extracted metadata from the title image
    title_number: Mapped[Optional[str]] = mapped_column(String(128))
    owner: Mapped[Optional[str]] = mapped_column(String(256))
    technical_description: Mapped[Optional[str]] = mapped_column(Text)
    ocr_raw: Mapped[Optional[dict]] = mapped_column(JSON)  # optional raw OCR payload

    # Tie point (you already have tie_point model, but keep denormalized fields too)
    tie_point_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tie_points.id"))
    tie_point_province: Mapped[Optional[str]] = mapped_column(String(128))
    tie_point_municipality: Mapped[Optional[str]] = mapped_column(String(128))
    tie_point_name: Mapped[Optional[str]] = mapped_column(String(256))

    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    images: Mapped[List["PropertyImage"]] = relationship(
        back_populates="property", cascade="all, delete-orphan", order_by="PropertyImage.order_index"
    )
    boundaries: Mapped[List["PropertyBoundary"]] = relationship(
        back_populates="property", cascade="all, delete-orphan", order_by="PropertyBoundary.idx"
    )
    reports: Mapped[List["PropertyReport"]] = relationship(
        back_populates="property", cascade="all, delete-orphan", order_by="PropertyReport.created_at.desc()"
    )
    tie_point = relationship("TiePoint", lazy="joined", foreign_keys=[tie_point_id])
