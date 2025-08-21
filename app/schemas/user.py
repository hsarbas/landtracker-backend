from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr
from app.models.user import Role


def normalize_ph_mobile(msisdn: str) -> str:
    """
    Very light normalizer:
      - Remove spaces/dashes
      - If starts with '0' and length 11, convert to +63 (PH)
      - If starts with '63' and length 12, add '+'
      - If already starts with '+', keep
    Adjust for your markets as needed.
    """
    raw = msisdn.replace(" ", "").replace("-", "")
    if raw.startswith("+"):
        return raw
    if raw.startswith("0") and len(raw) == 11:
        return "+63" + raw[1:]
    if raw.startswith("63") and len(raw) == 12:
        return "+" + raw
    return raw  # fallback; you can enforce stricter validation later


class UserCreate(BaseModel):
    mobile: str = Field(min_length=7, max_length=32)
    password: str = Field(min_length=8)
    first_name: Optional[str]
    last_name: Optional[str]
    email: Optional[EmailStr]


class UserLogin(BaseModel):
    mobile: str
    password: str


class UserRead(BaseModel):
    id: int
    mobile: str
    email: Optional[EmailStr] = None
    first_name: Optional[str]
    last_name: Optional[str]
    role: Role
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True  # Pydantic v2


class UserUpdate(BaseModel):
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = None  # user can add/change later


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=8)
    new_password: str = Field(min_length=8)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class SetRoleRequest(BaseModel):
    role: Role


class LogoutResponse(BaseModel):
    ok: bool = True
