from dotenv import load_dotenv
load_dotenv()

import os, httpx
from typing import Any, Dict, List
from backend.app.services.providers.base import GameProvider
from backend.app.models.game_info import GameInfo

RAWG_API_KEY = os.getenv("RAWG_API_KEY")
BASE_URL = "https://api.rawg.io/api/games"

class RAWGProvider(GameProvider):
    async def search_games(self, filters: Dict) -> List[GameInfo]:
        params = {
            "key": RAWG_API_KEY,
            "page_size": filters.get("limit", 10),
            "search": filters.get("query", "")
        }

        # Map tags to RAWG genres
        if filters.get("tags"):
            genre_slugs = [t.lower().strip() for t in filters["tags"] if t]
            if genre_slugs:
                params["genres"] = ",".join(genre_slugs)

        # Optional date filters
        if filters.get("release_date_from") and filters.get("release_date_to"):
            params["dates"] = f"{filters['release_date_from']},{filters['release_date_to']}"

        async with httpx.AsyncClient() as client:
            resp = await client.get(BASE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        results: List[GameInfo] = []
        for game in data.get("results", []):
            results.append(GameInfo(
                id=str(game["id"]),
                name=game["name"],
                description=None,
                release_date=game.get("released"),
                platforms=[p["platform"]["name"] for p in game.get("platforms", [])],
                genres=[g["name"] for g in game.get("genres", [])],
                screenshots=[game.get("background_image")] if game.get("background_image") else [],
                store_url=None,
                price=None
            ))
        return results

    async def get_game_details(self, game_id: str) -> Dict[str, Any]:
        return {}

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