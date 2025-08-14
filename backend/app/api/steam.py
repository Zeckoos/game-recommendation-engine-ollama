from fastapi import APIRouter, Query
from typing import List
from backend.app.services.providers.steam import SteamProvider
from backend.app.models.game_info import GameInfo

router = APIRouter()


@router.get("/search", response_model=List[GameInfo])
async def search_steam(query: str = Query(..., min_length=1, description="Search term for Steam games")):
    """
    Temporary endpoint to test Steam search.
    Returns a list of GameInfo objects from Steam.
    """
    provider = SteamProvider()
    results = await provider.search_games(query)
    return results