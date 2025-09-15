from __future__ import annotations
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


# ---------- Boundaries ----------
class BoundaryIn(BaseModel):
    idx: int = Field(..., ge=1)
    bearing: Optional[str] = None
    distance_m: Optional[float] = None
    start_lat: Optional[float] = None
    start_lng: Optional[float] = None
    end_lat: Optional[float] = None
    end_lng: Optional[float] = None
    raw_text: Optional[str] = None


class BoundaryOut(BoundaryIn):
    id: int


# ---------- Images ----------
class PropertyImageOut(BaseModel):
    id: int
    file_path: str
    original_name: str
    order_index: int
    page_number: int


# ---------- Reports ----------
class PropertyReportOut(BaseModel):
    id: int
    report_type: str
    file_path: str
    created_at: datetime


# ---------- Create/Update ----------
class PropertyCreate(BaseModel):
    # OCR metadata
    title_number: Optional[str] = None
    owner: Optional[str] = None
    technical_description: Optional[str] = None
    ocr_raw: Optional[dict] = None

    # tie point (either link or provide fields)
    tie_point_id: Optional[int] = None
    tie_point_province: Optional[str] = None
    tie_point_municipality: Optional[str] = None
    tie_point_name: Optional[str] = None

    # boundaries:
    boundaries: List[BoundaryIn] = []


class PropertyUpdate(BaseModel):
    title_number: Optional[str] = None
    owner: Optional[str] = None
    technical_description: Optional[str] = None
    ocr_raw: Optional[dict] = None
    tie_point_id: Optional[int] = None
    tie_point_province: Optional[str] = None
    tie_point_municipality: Optional[str] = None
    tie_point_name: Optional[str] = None
    boundaries: Optional[List[BoundaryIn]] = None  # replace-all semantics


# ---------- Output ----------
class PropertyOut(BaseModel):
    id: int
    user_id: int

    title_number: Optional[str]
    owner: Optional[str]
    technical_description: Optional[str]
    ocr_raw: Optional[dict]

    tie_point_id: Optional[int]
    tie_point_province: Optional[str]
    tie_point_municipality: Optional[str]
    tie_point_name: Optional[str]

    is_archived: bool
    created_at: datetime
    updated_at: datetime

    images: List[PropertyImageOut] = []
    boundaries: List[BoundaryOut] = []
    reports: List[PropertyReportOut] = []
