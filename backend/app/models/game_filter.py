from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import date

class GameFilter(BaseModel):
    query: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    currency: Optional[str] = "USD"
    platforms: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    release_date_from: Optional[date] = None
    release_date_to: Optional[date] = None

    @field_validator("release_date_from", "release_date_to", mode="before")
    @classmethod
    def empty_str_to_none(cls, v):
        # Convert empty strings to None for optional dates
        if v == "" or v is None:
            return None
        return v

    @field_validator("tags", "platforms", mode="before")
    @classmethod
    def normalize_list(cls, v):
        # Remove empty strings, strip whitespace, convert to lowercase
        if not v:
            return []
        return sorted({t.strip().lower() for t in v if t})

    @field_validator("min_price", "max_price")
    def non_negative(cls, v):
        if v < 0:
            raise ValueError("Price cannot be negative")
        return v

    @field_validator("max_price")
    def max_ge_min(cls, v, info):
        if "min_price" in info.data and v < info.data["min_price"]:
            raise ValueError("max_price cannot be less than min_price")
        return v