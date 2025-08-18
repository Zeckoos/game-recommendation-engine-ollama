from dotenv import load_dotenv
load_dotenv()

import asyncio, os, httpx
from typing import Any, Optional
from datetime import date
from backend.app.models.game_filter import GameFilter
from backend.app.models.game_info import GameInfo
from backend.app.models.provider_response import ProviderResponse
from backend.app.services.providers.base import GameProvider

RAWG_API_KEY = os.getenv("RAWG_API_KEY")
if not RAWG_API_KEY:
    raise RuntimeError("RAWG_API_KEY environment variable is not set.")

BASE_URL = "https://api.rawg.io/api/games"


async def _fetch_rawg_page(params: dict) -> ProviderResponse:
    """Fetch a single RAWG page and return results as a ProviderResponse."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(BASE_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    results = tuple(
        GameInfo(
            id=str(game["id"]),
            name=game["name"],
            release_date=date.fromisoformat(game["released"]) if game.get("released") else None,
            genres=tuple(g["id"] for g in game.get("genres", [])) or tuple(),
            platforms=tuple(p["platform"]["id"] for p in game.get("platforms", [])) or tuple(),
            screenshots=(game["background_image"],) if game.get("background_image") else tuple(),
            store_url=f"https://rawg.io/games/{game['slug']}" if game.get("slug") else None,
        )
        for game in data.get("results", [])
    )

    return ProviderResponse(results=results, total=data.get("count", 0))


class RAWGProvider(GameProvider):
    async def search_games(self, filters: GameFilter, total_limit: int = 20) -> ProviderResponse:
        """
        Fetch multiple RAWG pages asynchronously via RAWG API using tags, genres, and dates.
        Returns a ProviderResponse with results as tuples.
        """
        page_size = 20
        # Compute total pages needed (ceil)
        total_pages = (total_limit + page_size - 1) // page_size
        tasks = []

        # Build query params, skipping empty filters
        for page in range(1, total_pages + 1):
            params = {
                "key": RAWG_API_KEY,
                "page": page,
                "page_size": page_size,
                "search": filters.query or None,
                "dates": f"{filters.release_date_from},{filters.release_date_to}"
                if filters.release_date_from and filters.release_date_to else None,
                "platforms": ",".join(filters.platforms) if filters.platforms else None,
                "genres": ",".join(filters.genres) if filters.genres else None,
                "tags": ",".join(filters.tags) if filters.tags else None,
            }
            tasks.append(_fetch_rawg_page(params))

        # Execute all pages concurrently
        pages_results = await asyncio.gather(*tasks)

        # Flatten all pages and enforce total_limit
        all_results = tuple(game for page in pages_results for game in page.results)[:total_limit]

        return ProviderResponse(results=all_results, total=len(all_results))

    async def get_game_details(self, game_id: str) -> Optional[GameInfo]:
        """
        Fetch detailed game info for a single game ID.
        Populates description, developers, publishers, genres, platforms, and screenshots.
        """

        url = f"{BASE_URL}/{game_id}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params={"key": RAWG_API_KEY})
            resp.raise_for_status()
            data = resp.json()

        return GameInfo(
            id=str(data["id"]),
            name=data["name"],
            description=data.get("description_raw"),
            release_date=date.fromisoformat(data["released"]) if data.get("released") else None,
            genres=tuple(g["id"] for g in data.get("genres", [])) or tuple(),
            platforms=tuple(p["platform"]["id"] for p in data.get("platforms", [])) or tuple(),
            developers=tuple(dev["name"] for dev in data.get("developers", [])) or tuple(),
            publishers=tuple(pub["name"] for pub in data.get("publishers", [])) or tuple(),
            screenshots=tuple(img["image"] for img in data.get("short_screenshots", [])) or tuple(),
            store_url=f"https://rawg.io/games/{data['slug']}" if data.get("slug") else None
        )

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