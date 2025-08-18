from pydantic import BaseModel, Field
from typing import Tuple
from .game_info import GameInfo

class ProviderResponse(BaseModel):
    results: Tuple[GameInfo, ...] = Field(default_factory=tuple)
    total: int = 0

    class Config:
        frozen = True           # Immutable → prevents accidental mutation
        validate_assignment = True
        extra = "forbid"