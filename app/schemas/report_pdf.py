from __future__ import annotations
from pydantic import BaseModel, HttpUrl
from typing import List


class BoundaryItem(BaseModel):
    ns: str
    deg: float
    min: float
    ew: str
    distance: float


class ReportData(BaseModel):
    property_id: int
    title_number: str
    owner: str
    snapshot: HttpUrl
    boundaries: List[BoundaryItem]
