from datetime import date
from typing import Optional, Tuple
from pydantic import BaseModel, HttpUrl, Field, confloat

class GameInfo(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    release_date: Optional[date] = None
    developers: Optional[Tuple[str]] = Field(default_factory=tuple)
    publishers: Optional[Tuple[str]] = Field(default_factory=tuple)
    genres: Optional[Tuple[str]] = Field(default_factory=tuple)
    platforms: Optional[Tuple[str]] = Field(default_factory=tuple)
    screenshots: Optional[Tuple[HttpUrl]] = Field(default_factory=tuple)
    price: Optional[confloat(ge=0)] = None
    store_url: Optional[HttpUrl] = None

    class Config:
        anystr_strip_whitespace = True
        validate_assignment = True
        extra = "forbid"