# schemas.py
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import List, Optional, Union


class TiePointCreate(BaseModel):
    tie_point_name: str = Field(..., description="e.g., BLLM 1")
    description: str
    province: str
    municipality: str
    northing: float
    easting: float


class TiePointRead(BaseModel):
    id: int
    tie_point_name: Optional[str] = None
    description: Optional[str] = None
    province: Optional[str] = None
    municipality: Optional[str] = None
    northing: Optional[float] = None
    easting: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class TiePointImport(BaseModel):
    tie_point_name: Optional[Union[str, int, float]] = Field(None, alias="Tie Point Name")
    description:    Optional[Union[str, int, float]] = Field(None, alias="Description")
    province:       Optional[Union[str, int, float]] = Field(None, alias="Province")
    municipality:   Optional[Union[str, int, float]] = Field(None, alias="Municipality")
    northing:       Optional[Union[float, int, str]] = Field(None, alias="Northing")
    easting:        Optional[Union[float, int, str]] = Field(None, alias="Easting")

    @field_validator("tie_point_name", "description", "province", "municipality", mode="before")
    def to_str_or_none(cls, v):
        if v is None: return None
        if isinstance(v, (int, float)): return str(v)
        if isinstance(v, str):
            s = v.strip()
            return s or None
        return None

    @field_validator("northing", "easting", mode="before")
    def parse_num(cls, v):
        if v is None: return None
        if isinstance(v, (int, float)): return float(v)
        if isinstance(v, str):
            s = v.strip().replace(",", "")
            if s == "" or s.lower() in {"na","n/a","null","none","-"}:
                return None
            try:
                return float(s)
            except ValueError:
                # lenient: keep as NULL instead of raising
                return None
        return None

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class Boundary(BaseModel):
    ns: str        # "N" or "S"
    deg: float
    min: float
    ew: str        # "E" or "W"
    distance: float  # meters


class Payload(BaseModel):
    tie_lon: float
    tie_lat: float
    boundaries: List[Boundary]


class NERequest(BaseModel):
    northing: float
    easting: float


class LonLatResponse(BaseModel):
    lon: float
    lat: float
