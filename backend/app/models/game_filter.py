from datetime import date
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, confloat

class Currency(str, Enum):
    USD = "USD"
    EUR = "EUR"
    AUD = "AUD"

class GameFilter(BaseModel):
    query: Optional[str] = ""
    min_price: Optional[confloat(ge=0)] = 0.0
    max_price: Optional[confloat(ge=0)] = float("inf")
    currency: Currency = Currency.USD

    platforms: Optional[List[str]] = Field(default_factory=list)
    genres: Optional[List[str]] = Field(default_factory=list)
    tags: Optional[List[str]] = Field(default_factory=list)

    release_date_from: Optional[date] = None
    release_date_to: Optional[date] = None

    class Config:
        use_enum_values = True       # serialize enum to its value
        populate_by_name = True
        validate_assignment = True   # ensures updates are validated
        str_strip_whitespace = True
        extra = "forbid"             # disallow unknown fields