from fastapi import APIRouter, HTTPException, Request, Query
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

@router.post("/", response_model=ProviderResponse, summary="Get game recommendations with pagination")
async def recommend(
        request_data: UnifiedRequest,
        request: Request,
        limit: int = Query(10, ge=1, le=50, description="Number of results per page (default 10)"),
        page: int = Query(1, ge=1, description="Page number to retrieve (default 1)")):
    """
   Unified endpoint for game recommendations.

    Supports:
    1. Natural-language query (`query`)
    2. Structured `GameFilter` (`filter`)

    Pagination:
    - `limit`: number of results per page
    - `page`: page number
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
            # Parse natural-language query
            parser = NLQueryParser(metadata_cache)
            game_filter, leftovers = await parser.parse(request_data.query)

            logger.info("Original query: '%s'", request_data.query)
            logger.info("Parsed GameFilter: %s", game_filter.model_dump())
            logger.info("Leftover/unresolved metadata: %s", leftovers)

        else:
            raise HTTPException(status_code=400, detail="Either 'query' or 'filter' must be provided.")

        # Aggregate results
        results: ProviderResponse = await aggregator.aggregate(
            filters=game_filter,
            limit=limit,
            page=page,
        )

        return results

    except Exception as e:
        logger.exception("Error processing recommendation request")
        raise HTTPException(status_code=500, detail=f"Error processing request: {e}")