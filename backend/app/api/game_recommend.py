from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from ..models.game_filter import GameFilter
from ..models.provider_response import ProviderResponse
from ..services.nl_query_parser import NLQueryParser
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


class UnifiedRequest(BaseModel):
    query: Optional[str] = None
    filter: Optional[GameFilter] = None


@router.post("/", response_model=ProviderResponse)
async def recommend(request_data: UnifiedRequest, request: Request):
    """
    Unified endpoint for:
    1. Natural-language query (`query`)
    2. Structured GameFilter (`filter`)

    Includes structured logging of parsed filters and unresolved metadata.
    """
    aggregator = getattr(request.app.state, "aggregator", None)
    if aggregator is None:
        raise HTTPException(status_code=503, detail="Aggregator not initialised yet")

    metadata_cache = getattr(request.app.state, "rawg_metadata_cache", None)
    if metadata_cache is None:
        raise HTTPException(status_code=503, detail="RAWG metadata cache not initialised yet")

    try:
        if request_data.filter:
            game_filter: GameFilter = request_data.filter
            leftovers = {}
            logger.info("Using provided GameFilter: %s", game_filter.model_dump())
        elif request_data.query:
            parser = NLQueryParser(metadata_cache)
            game_filter, leftovers = parser.parse(request_data.query)

            logger.info("Original query: '%s'", request_data.query)
            logger.info("Parsed GameFilter: %s", game_filter.model_dump())
            logger.info("Leftover/unresolved metadata: %s", leftovers)
        else:
            raise HTTPException(status_code=400, detail="Either 'query' or 'filter' must be provided.")

        # Aggregate results
        results = await aggregator.aggregate(game_filter)
        return results

    except Exception as e:
        logger.exception("Error processing recommendation request")
        raise HTTPException(status_code=500, detail=f"Error processing request: {e}")