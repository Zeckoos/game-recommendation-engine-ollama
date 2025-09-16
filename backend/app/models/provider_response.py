import math

from pydantic import BaseModel, Field
from typing import Tuple, Optional
from .game_info import GameInfo

class ProviderResponse(BaseModel):
    """Wrapper Class for provider response"""
    results: Tuple[GameInfo, ...] = Field(default_factory=tuple)
    total: int = 0
    limit: Optional[int] = None
    page: Optional[int] = None
    total_pages: Optional[int] = None

    @classmethod
    def create(
            cls, results: Tuple[GameInfo, ...], total: int, limit: int, page: int
    ):
        total_pages = math.ceil(total / limit) if limit and limit > 0 else 1
        return cls(
            results=results,
            total=total,
            limit=limit,
            page=page,
            total_pages=total_pages,
        )

    class Config:
        frozen = True           # Immutable → prevents accidental mutation
        validate_assignment = True
        extra = "forbid"