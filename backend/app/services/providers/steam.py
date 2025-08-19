import asyncio

import httpx
from typing import Any, Optional
from backend.app.models.game_info import GameInfo
from .base import GameProvider
from ...models.provider_response import ProviderResponse
from backend.app.services.providers.helpers import parse_release_date,parse_price

class SteamProvider(GameProvider):
    BASE_SEARCH_URL = "https://store.steampowered.com/api/storesearch"
    BASE_APP_DETAILS_URL = "https://store.steampowered.com/api/appdetails"

    async def search_games(self, query: str) -> ProviderResponse:
        """Search Steam store by query and return ProviderResponse."""
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(self.BASE_SEARCH_URL, params={"term": query, "cc": "us", "l": "en"})
                resp.raise_for_status()
                items = resp.json().get("items", [])
            except httpx.HTTPError:
                items = []

        # Fetch detailed info concurrently for all results
        async def fetch_details(app_id: str) -> Optional[GameInfo]:
            try:
                return await self.get_game_details(app_id)
            except httpx.HTTPError:
                return None

        tasks = [fetch_details(str(item.get("id"))) for item in items if item.get("id")]
        results_list = await asyncio.gather(*tasks)

        # Filter out failed fetches
        results = tuple(g for g in results_list if g)
        return ProviderResponse(results=results, total=len(results))

    async def get_game_details(self, app_id: str) -> Optional[GameInfo]:
        """Fetch detailed game info and convert to GameInfo."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.BASE_APP_DETAILS_URL, params={"appids": app_id, "cc": "us", "l": "en"})
            resp.raise_for_status()
            data = resp.json().get(str(app_id), {}).get("data", {})

        if not data:
            return None

        return GameInfo(
            id=str(app_id),
            name=data.get("name"),
            description=data.get("short_description"),
            release_date=parse_release_date(data.get("release_date", {}).get("date")),
            developers=tuple(data.get("developers", [])) or tuple(),
            publishers=tuple(data.get("publishers", [])) or tuple(),
            genres=tuple(g.get("description") for g in data.get("genres", [])) or tuple(),
            platforms=tuple(k for k, v in data.get("platforms", {}).items() if v) or tuple(),
            screenshots=tuple(sc.get("path_full") for sc in data.get("screenshots", [])) or tuple(),
            price=parse_price(data),
            store_url=f"https://store.steampowered.com/app/{app_id}"
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