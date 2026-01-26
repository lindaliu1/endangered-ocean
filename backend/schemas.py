from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel

# define and validate api responses
Status = Literal["Endangered", "Threatened"]

class SpeciesOut(BaseModel):
    id: int
    source: str
    source_record_id: str
    detail_url: Optional[str] = None
    common_name: str
    scientific_name: str
    status: str
    image_url: str
    min_depth_m: Optional[float] = None
    max_depth_m: Optional[float] = None
    threats: list[str]

class ThreatOut(BaseModel):
    id: int
    name: str
