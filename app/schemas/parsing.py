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
    tie_point: str
    boundaries: List[BoundaryPoint]
