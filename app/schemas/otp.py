from __future__ import annotations
from pydantic import BaseModel, Field


class OtpRequest(BaseModel):
    mobile: str = Field(min_length=7, max_length=32)


class OtpConfirm(BaseModel):
    mobile: str
    code: str = Field(min_length=4, max_length=8)


class OtpStatus(BaseModel):
    ok: bool
    message: str


class MobileChangeRequest(BaseModel):
    new_mobile: str = Field(min_length=7, max_length=32)


class MobileChangeConfirm(BaseModel):
    new_mobile: str
    code: str = Field(min_length=4, max_length=8)
