from fastapi import APIRouter, Query
from backend.app.models.provider_response import ProviderResponse
from backend.app.services.providers.steam import SteamProvider

router = APIRouter()


@router.get("/search", response_model=ProviderResponse)
async def search_steam(query: str = Query(..., min_length=1, description="Search term for Steam games")):
    """
    Temporary endpoint to test Steam search.
    Returns a list of GameInfo objects from Steam.
    """
    provider = SteamProvider()
    results = await provider.search_games(query)
    return results