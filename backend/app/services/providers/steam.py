import asyncio

import httpx
from typing import Any, Dict, List, Optional
from backend.app.models.game_info import GameInfo
from .base import GameProvider


def parse_price(details_data: dict) -> float | None:
    price_info = details_data.get("price_overview")
    if price_info and "final" in price_info:
        return price_info["final"] / 100  # convert cents to dollars
    if details_data.get("is_free"):
        return 0.0
    return None


class SteamProvider(GameProvider):
    BASE_SEARCH_URL = "https://store.steampowered.com/api/storesearch"
    BASE_APP_DETAILS_URL = "https://store.steampowered.com/api/appdetails"

    async def search_games(self, query: str) -> List[GameInfo]:
        results: List[GameInfo] = []

        async with httpx.AsyncClient() as client:
            try:
                # Step 1: Search Steam store
                search_resp = await client.get(
                    self.BASE_SEARCH_URL,
                    params={"term": query, "cc": "us", "l": "en"}
                )

                search_resp.raise_for_status()
                search_data = search_resp.json().get("items", [])

            except httpx.HTTPError as e:
                print(f"Steam search error: {e}")
                return results

        # Step 2: Fetch details concurrently
        async def fetch_details(app_id: str) -> Optional[GameInfo]:
            try:
                return await self.get_game_details(app_id)
            except httpx.HTTPError as e:
                print(f"Error fetching Steam details for {app_id}: {e}")
                return None

        tasks = [fetch_details(str(item.get("id"))) for item in search_data if item.get("id")]
        detailed_results = await asyncio.gather(*tasks)
        results.extend([g for g in detailed_results if g])
        return results

    async def get_game_details(self, app_id: str) -> Optional[GameInfo]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                self.BASE_APP_DETAILS_URL,
                params={"appids": app_id, "cc": "us", "l": "en"}
            )
            resp.raise_for_status()
            data = resp.json().get(str(app_id), {}).get("data", {})

        if not data:
            return None

        return GameInfo(
            id=str(app_id),
            name=data.get("name"),
            description=data.get("short_description"),
            release_date=data.get("release_date", {}).get("date"),
            developers=data.get("developers", []),
            publishers=data.get("publishers", []),
            genres=[g.get("description") for g in data.get("genres", [])],
            platforms=[k for k, v in data.get("platforms", {}).items() if v],
            screenshots=[sc.get("path_full") for sc in data.get("screenshots", [])],
            price=parse_price(data),
            store_url=f"https://store.steampowered.com/app/{app_id}"
        )

    async def get_game_price(self, game_id: str, currency: str) -> Dict[str, Any]:
        return {}

    async def get_game_screenshots(self, game_id: str) -> List[str]:
        return []

    async def get_trending_games(self, limit: int = 10) -> List[Dict[str, Any]]:
        return []

    async def get_recommendations(self, seed_game_id: str) -> List[Dict[str, Any]]:
        return []

    async def check_health(self) -> bool:
        return True

    async def supports_feature(self, feature: str) -> bool:
        return feature in ["search", "details", "price", "screenshots", "trending", "recommendations", "autocomplete"]

    async def autocomplete(self, query: str) -> List[str]:
        return []

    async def raw_provider_data(self, game_id: str) -> Dict[str, Any]:
        return {}