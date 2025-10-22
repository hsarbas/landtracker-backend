# app/schemas/tie_point.py
from typing import Optional
from pydantic import BaseModel, Field
from pydantic import ConfigDict  # Pydantic v2


class TiePointCreate(BaseModel):
    tie_point_name: str = Field(..., description="e.g., BLLM 1")
    description: Optional[str] = None
    province: Optional[str] = None
    municipality: Optional[str] = None
    northing: Optional[float] = None
    easting: Optional[float] = None


class TiePointRead(TiePointCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)  # v2 replacement for Config.from_attributes


class TiePointImport(BaseModel):
    # Accept BOTH JSON alias keys (your file) and code field names
    tie_point_name: Optional[str] = Field(None, alias="Tie Point Name")
    description: Optional[str] = Field(None, alias="Description")
    province: Optional[str] = Field(None, alias="Province")
    municipality: Optional[str] = Field(None, alias="Municipality")
    northing: Optional[float] = Field(None, alias="Northing")
    easting: Optional[float] = Field(None, alias="Easting")

    # Allow population via either alias or field name
    model_config = ConfigDict(populate_by_name=True)
