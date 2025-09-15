from __future__ import annotations
from pydantic import BaseModel, HttpUrl


class ReportData(BaseModel):
    title_id: str | None = None
    owner: str | None = None
    snapshot: HttpUrl | None = None
    tech_desc: str | None = None