from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.models.user import User


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # JWT ID (unique random uuid per refresh token)
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)

    # Security flags
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Optional: detect reuse/rotation
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Expiry mirrors JWT exp (not authoritative, but useful for cleanup)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Audit (optional)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255))
    ip_addr: Mapped[Optional[str]] = mapped_column(String(64))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped[User] = relationship(User, backref="refresh_tokens")


Index("ix_refresh_tokens_user_revoked", RefreshToken.user_id, RefreshToken.is_revoked)
