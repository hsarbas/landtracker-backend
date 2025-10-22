from __future__ import annotations
from datetime import datetime
from typing import List
from pydantic import BaseModel


# --- Shared read-only pieces (show up in outputs) ---
class BoundaryOut(BaseModel):
    id: int
    bearing: str
    distance_m: float


class ImageOut(BaseModel):
    id: int
    file_path: str
    order_index: int
    created_at: datetime


class ReportOut(BaseModel):
    id: int
    report_type: str
    file_path: str
    created_at: datetime


# --- Input pieces (what the client sends) ---
class BoundaryCreate(BaseModel):
    bearing: str
    distance_m: float


class TitleImageCreate(BaseModel):
    data_url: str
    order_index: int


class ReportCreate(BaseModel):
    report_type: str
    data_url: str  # must be PDF


# --- Property models ---
class PropertyCreate(BaseModel):
    user_id: int
    title_number: str
    owner: str
    technical_description: str
    tie_point_id: int


class PropertyOut(BaseModel):
    id: int
    user_id: int
    title_number: str
    owner: str
    technical_description: str
    tie_point_id: int

    created_at: datetime
    updated_at: datetime

    images: List[ImageOut] = []
    boundaries: List[BoundaryOut] = []
    reports: List[ReportOut] = []
