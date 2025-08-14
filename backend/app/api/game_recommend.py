from fastapi import APIRouter, HTTPException
from typing import List
from backend.app.models.game_filter import GameFilter
from backend.app.models.game_info import GameInfo
from backend.app.services.aggregator import GameAggregator

router = APIRouter()
aggregator = GameAggregator()

@router.post("/", response_model=List[GameInfo])
async def recommend(filter: GameFilter):
    """
    Receive a GameFilter and return enriched GameInfo from RAWG + Steam.
    """
    try:
        results = await aggregator.aggregate(filter)
        print("Final results:", results)
        return results
    except Exception as e:
        # Log and return empty list on failure
        print(f"Aggregator error: {e}")
        # Catch any unexpected errors
        raise HTTPException(status_code=500, detail=str(e))