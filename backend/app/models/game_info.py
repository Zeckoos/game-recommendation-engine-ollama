from typing import List, Optional
from pydantic import BaseModel

class GameInfo(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    release_date: Optional[str] = None
    developers: Optional[List[str]] = None
    publishers: Optional[List[str]] = None
    genres: Optional[List[str]] = None
    platforms: Optional[List[str]] = None
    screenshots: Optional[List[str]] = None
    price: Optional[float] = None
    store_url: Optional[str] = None