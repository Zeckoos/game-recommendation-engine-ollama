import logging
import time

from dotenv import load_dotenv

from backend.app.services.providers.helpers import parse_rawg_game
from backend.app.utils.rawg_metadata_cache import RAWGMetadataCache
import asyncio, os, httpx
from typing import Any, Optional
from backend.app.models.game_filter import GameFilter
from backend.app.models.game_info import GameInfo
from backend.app.models.provider_response import ProviderResponse
from backend.app.services.providers.base import GameProvider

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
            logger.debug("Fetching details for game ID: %s", game_id)
            detail_resp = await detail_client.get(url, params={"key": RAWG_API_KEY})
            detail_resp.raise_for_status()
            game_info = parse_rawg_game(detail_resp.json(), metadata_cache)
            # logger.debug(
            #     "Fetched game details: ID=%s, Name=%s, Genres=%s, Platforms=%s, URL=%s",
            #     game_info.id, game_info.name, game_info.genres, game_info.platforms, game_info.store_url
            # )
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
        self.metadata_cache = None

    @classmethod
    async def create(cls):
        """Factory to asynchronously initialise metadata cache."""
        self = cls()
        self.metadata_cache = RAWGMetadataCache()
        await self.metadata_cache.load_or_fetch()  # async pre-fetch
        logger.debug(
            "Provider created with metadata → %d genres, %d platforms, %d tags",
            len(self.metadata_cache.genres),
            len(self.metadata_cache.platforms),
            len(self.metadata_cache.tags),
        )
        return self

    async def search_games(self, filters: GameFilter, total_limit: int = 15, offset: int = 0) -> ProviderResponse:
        """
        Search games using RAWG API, resolving filter names to IDs
        via metadata cache with support for pagination.
        `offset` allows skipping previous results for backend pagination.
        """
        page_size = 20
        start_page = offset // page_size + 1
        end_page = (offset + total_limit + page_size - 1) // page_size
        tasks = []

        # Build dicts for fast name → ID lookup
        genre_dict = {name.lower(): id for id, name in self.metadata_cache.genres}
        platform_dict = {name.lower(): id for id, name in self.metadata_cache.platforms}
        tag_dict = {name.lower(): id for id, name in self.metadata_cache.tags}

        # Resolve filters
        genre_ids = [genre_dict[g.lower()] for g in filters.genres if g.lower() in genre_dict]
        platform_ids = [platform_dict[p.lower()] for p in filters.platforms if p.lower() in platform_dict]
        tag_ids = [tag_dict[t.lower()] for t in filters.tags if t.lower() in tag_dict]

        # Log missing filters
        missing_genres = set(filters.genres) - set(genre_dict.keys())
        missing_platforms = set(filters.platforms) - set(platform_dict.keys())
        missing_tags = set(filters.tags) - set(tag_dict.keys())

        if missing_genres:
            logger.warning("Unknown genres skipped: %s", missing_genres)
        if missing_platforms:
            logger.warning("Unknown platforms skipped: %s", missing_platforms)
        if missing_tags:
            logger.warning("Unknown tags skipped: %s", missing_tags)

        logger.debug("Resolved filters → genres=%s, platforms=%s, tags=%s",
                     genre_ids, platform_ids, tag_ids)

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
            logger.debug("RAWG request params (page %d): %s", page, params)
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
        return parse_rawg_game(data)

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