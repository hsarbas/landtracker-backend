from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr
from app.schemas.role import RoleRead


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
    # optional: let backend default to "client" if not provided
    role_id: Optional[int] = None


class UserLogin(BaseModel):
    mobile: str
    password: str


class UserRead(BaseModel):
    id: int
    mobile: str
    email: Optional[EmailStr] = None
    first_name: Optional[str]
    last_name: Optional[str]
    is_active: bool
    created_at: datetime
    role: RoleRead  # embed the role object

    class Config:
        from_attributes = True


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
    role_id: int


class LogoutResponse(BaseModel):
    ok: bool = True
