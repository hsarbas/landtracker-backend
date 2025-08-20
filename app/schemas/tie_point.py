from pydantic import BaseModel, Field


class TiePointCreate(BaseModel):
    tie_point_name: str = Field(..., description="e.g., BLLM 1")
    description: str
    province: str
    municipality: str
    northing: float
    easting: float


class TiePointRead(TiePointCreate):
    id: int
    class Config: from_attributes = True


class TiePointImport(BaseModel):
    tie_point_name: str | None = None
    description: str | None = None
    province: str | None = None
    municipality: str | None = None
    northing: float | None = None
    easting: float | None = None
