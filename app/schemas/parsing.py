from pydantic import BaseModel
from typing import List, Optional


class DescriptionRequest(BaseModel):
    description: str


class BoundaryPoint(BaseModel):
    ns: str
    degrees: int
    minutes: int
    seconds: Optional[float] = None
    ew: Optional[str] = None
    distance_m: float


class ParseResponse(BaseModel):
    # NEW: meta fields expected by your frontend
    title_number: Optional[str] = None
    owner: Optional[str] = None
    technical_description: str

    tie_point: str
    boundaries: List[BoundaryPoint]
