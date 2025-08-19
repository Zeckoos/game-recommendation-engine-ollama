from fastapi import APIRouter, HTTPException, Request
from backend.app.models.game_filter import GameFilter
from backend.app.models.provider_response import ProviderResponse

router = APIRouter()

@router.post("/", response_model=ProviderResponse)
async def recommend(game_filter: GameFilter, request: Request):
    """
    Receive a GameFilter and return enriched GameInfo from RAWG + Steam.
    """
    aggregator = getattr(request.app.state, "aggregator", None)
    if aggregator is None:
        raise HTTPException(status_code=503, detail="Aggregator not initialized yet")

    try:
        results = await aggregator.aggregate(game_filter)
        return results
    except Exception as e:
        print(f"Aggregator error: {e}")
        raise HTTPException(status_code=500, detail=str(e))