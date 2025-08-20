from pydantic import BaseModel
from typing import List


class Bearing(BaseModel):
    ns: str
    deg: int
    min: int
    sec: float | None = None
    ew: str | None = None
    distance: float


class Payload(BaseModel):
    tie_lat: float
    tie_lon: float
    boundaries: List[Bearing]


class NERequest(BaseModel):
    easting: float
    northing: float


class LonLatResponse(BaseModel):
    lon: float
    lat: float
