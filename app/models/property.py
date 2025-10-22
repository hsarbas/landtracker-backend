from __future__ import annotations
from datetime import datetime
from typing import Optional, List

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, ForeignKey, DateTime, func

from app.db.base import Base


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    title_number: Mapped[str] = mapped_column(String(128), index=True)
    owner: Mapped[str] = mapped_column(String(256))
    technical_description: Mapped[str] = mapped_column(Text)
    tie_point_id: Mapped[int] = mapped_column(
        ForeignKey("tie_points.id", ondelete="RESTRICT"), index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # --- Relationships ---
    images: Mapped[List["PropertyImage"]] = relationship(
        back_populates="property",
        cascade="all, delete-orphan",
        order_by="PropertyImage.order_index",
        lazy="selectin",
    )
    boundaries: Mapped[List["PropertyBoundary"]] = relationship(
        back_populates="property",
        cascade="all, delete-orphan",
        order_by="PropertyBoundary.id",
        lazy="selectin",
    )
    reports: Mapped[List["PropertyReport"]] = relationship(
        back_populates="property",
        cascade="all, delete-orphan",
        order_by="PropertyReport.created_at.desc()",
        lazy="selectin",
    )

    # Optional object refs (not exposed in your schema)
    tie_point: Mapped["TiePoint"] = relationship("TiePoint", lazy="joined")
    user: Mapped[Optional["User"]] = relationship("User", lazy="joined")