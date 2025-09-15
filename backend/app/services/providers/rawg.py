import logging
import time

from dotenv import load_dotenv

from ...caches.rawg_cache_mapping import LLMCacheMapper
from ...utils.providers_helpers import parse_rawg_game, resolve_filters
from backend.app.caches.rawg_metadata_cache import RAWGMetadataCache
import asyncio, os, httpx
from typing import Any, Optional
from ...models.game_filter import GameFilter
from ...models.game_info import GameInfo
from ...models.provider_response import ProviderResponse
from .base import GameProvider

load_dotenv()

RAWG_API_KEY = os.getenv("RAWG_API_KEY")
BASE_URL = "https://api.rawg.io/api/games"

logger = logging.getLogger(__name__)

if not RAWG_API_KEY:
    raise RuntimeError("RAWG_API_KEY environment variable is not set.")
print(f"RAWG_API_KEY: {RAWG_API_KEY}")

async def _fetch_rawg_page(params: dict, metadata_cache: RAWGMetadataCache) -> ProviderResponse:
    """Fetch a RAWG summary page, then enrich each game with full details using metadata cache."""
    start_time = time.perf_counter()  # start timer

    async with httpx.AsyncClient() as client:
        logger.debug("Fetching RAWG page with params: %s", params)
        resp = await client.get(BASE_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
        logger.debug("Fetched page with %d games, total count: %d",
                     len(data.get("results", [])), data.get("count", 0))

    # Fetch full details concurrently
    async def fetch_details(game_id: str) -> GameInfo:
        url = f"{BASE_URL}/{game_id}"
        async with httpx.AsyncClient() as detail_client:
            detail_resp = await detail_client.get(url, params={"key": RAWG_API_KEY})
            detail_resp.raise_for_status()
            game_info = parse_rawg_game(detail_resp.json(), metadata_cache)

            # Log unresolved IDs per game
            unknown_genres = [g for g in game_info.genres if g not in metadata_cache.genre_map.values()]
            unknown_platforms = [p for p in game_info.platforms if p not in metadata_cache.platform_map.values()]
            unknown_tags = []  # Can be added if you parse tags per game
            if unknown_genres or unknown_platforms or unknown_tags:
                logger.warning(
                    "Game ID %s has unresolved IDs → genres: %s, platforms: %s, tags: %s",
                    game_id, unknown_genres, unknown_platforms, unknown_tags
                )

            return game_info

    tasks = [fetch_details(str(game["id"])) for game in data.get("results", [])]
    results = tuple(await asyncio.gather(*tasks))

    logger.debug("Completed enrichment for %d games", len(results))
    end_time = time.perf_counter()  # end timer
    elapsed = end_time - start_time
    logger.info("Fetched RAWG page in %.3f seconds", elapsed)

    return ProviderResponse(results=results, total=data.get("count", 0))

class RAWGProvider(GameProvider):
    """RAWG API provider with eager pre-fetch metadata and async support."""

    def __init__(self):
        self.metadata_cache: RAWGMetadataCache | None = None
        self.llm_cache: LLMCacheMapper | None = None

    @classmethod
    async def create(cls):
        """Factory to asynchronously initialise metadata cache."""
        self = cls()
        self.metadata_cache = RAWGMetadataCache()
        await self.metadata_cache.load_or_fetch()  # async pre-fetch
        self.llm_cache = LLMCacheMapper()
        logger.debug(
            "Provider created with metadata → %d genres, %d platforms, %d tags",
            len(self.metadata_cache.genres),
            len(self.metadata_cache.platforms),
            len(self.metadata_cache.tags),
        )
        return self

    async def search_games(self, filters: GameFilter, total_limit: int = 10, offset: int = 0) -> ProviderResponse:
        """
        Search games using RAWG API, resolving filter names to IDs
        via metadata cache with support for pagination.
        `offset` allows skipping previous results for backend pagination.
        """
        page_size = 20
        start_page = offset // page_size + 1
        end_page = (offset + total_limit + page_size - 1) // page_size
        tasks = []

        # Resolve filters with centralized helper
        resolved_ids, still_missing = await resolve_filters(
            self.metadata_cache,
            {"genres": filters.genres, "platforms": filters.platforms, "tags": filters.tags},
            self.llm_cache
        )

        # Log unresolved filters
        for key, missing in still_missing.items():
            if missing:
                logger.warning("Unknown %s skipped: %s", key, missing)

        genre_ids = resolved_ids["genres"]
        platform_ids = resolved_ids["platforms"]
        tag_ids = resolved_ids["tags"]

        # Build query params for each page
        for page in range(start_page, end_page + 1):
            params = {
                "key": RAWG_API_KEY,
                "page": page,
                "page_size": page_size,
                "search": filters.query or None,
                "dates": f"{filters.release_date_from},{filters.release_date_to}"
                         if filters.release_date_from and filters.release_date_to else None,
                "platforms": ",".join(map(str, platform_ids)) if platform_ids else None,
                "genres": ",".join(map(str, genre_ids)) if genre_ids else None,
                "tags": ",".join(map(str, tag_ids)) if tag_ids else None,
            }
            #logger.debug("RAWG request params (page %d): %s", page, params)
            tasks.append(_fetch_rawg_page(params, self.metadata_cache))

        pages_results = await asyncio.gather(*tasks)

        # Flatten results and enforce total_limit
        all_results = tuple(game for page in pages_results for game in page.results)[:total_limit]

        # Apply offset slice for partial page
        start_index = offset % page_size
        final_results = all_results[start_index: start_index + total_limit]

        logger.debug("Returning %d games after applying offset/limit", len(final_results))
        return ProviderResponse(results=final_results, total=len(all_results))

    async def get_game_details(self, game_id: str) -> Optional[GameInfo]:
        """Fetch detailed game info by ID."""
        url = f"{BASE_URL}/{game_id}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params={"key": RAWG_API_KEY})
            resp.raise_for_status()
            data = resp.json()

        logger.debug("Fetched game details for ID %s", game_id)
        return parse_rawg_game(data, self.metadata_cache)

    async def get_game_price(self, game_id: str, currency: str) -> Any:
        pass

    async def get_game_screenshots(self, game_id: str) -> tuple[str, ...]:
        pass

    async def get_trending_games(self, limit: int = 10) -> ProviderResponse:
        pass

    async def get_recommendations(self, seed_game_id: str) -> ProviderResponse:
        pass

    async def check_health(self) -> bool:
        pass

    async def supports_feature(self, feature: str) -> bool:
        pass

    async def autocomplete(self, query: str) -> tuple[str, ...]:
        pass

    async def raw_provider_data(self, game_id: str) -> Any:
        pass