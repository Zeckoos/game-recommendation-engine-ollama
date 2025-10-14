import asyncio, httpx, logging
from typing import Any, Optional
from ...models.game_info import GameInfo
from .base import GameProvider
from ...models.provider_response import ProviderResponse
from ...utils.providers_helpers import parse_release_date,parse_price

logger = logging.getLogger(__name__)

class SteamProvider(GameProvider):
    BASE_SEARCH_URL = "https://store.steampowered.com/api/storesearch"
    BASE_APP_DETAILS_URL = "https://store.steampowered.com/api/appdetails"

    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self.client = client
        self.semaphore = asyncio.Semaphore(10)

    @classmethod
    async def create(cls):
        """Async factory for SteamProvider with persistent HTTP client."""
        client = httpx.AsyncClient(
            timeout=15,
            limits=httpx.Limits(max_connections=50),
            http2=True,
            headers={"User-Agent": "GameRecEngine/1.0"},
        )
        return cls(client=client)

    async def close(self):
        if self.client:
            await self.client.aclose()
            self.client = None

    async def search_games(self, query: str) -> ProviderResponse:
        """Search Steam store by query and return ProviderResponse."""
        try:
            resp = await self.client.get(self.BASE_SEARCH_URL, params={"term": query, "cc": "us", "l": "en"})
            resp.raise_for_status()
            items = resp.json().get("items", [])
        except httpx.HTTPError:
            items = []

        async def fetch_details(app_id: str) -> Optional[GameInfo]:
            async with self.semaphore:
                try:
                    return await self.get_game_details(app_id)
                except Exception:
                    return None

        tasks = [fetch_details(str(item.get("id"))) for item in items if item.get("id")]
        results_list = await asyncio.gather(*tasks)
        results = tuple(g for g in results_list if g)

        return ProviderResponse(results=results, total=len(results))

    async def get_game_details(self, app_id: str) -> Optional[GameInfo]:
        """Fetch detailed game info and convert to GameInfo."""
        resp = await self.client.get(self.BASE_APP_DETAILS_URL, params={"appids": app_id, "cc": "us", "l": "en"})
        resp.raise_for_status()
        data = resp.json().get(str(app_id), {}).get("data", {})

        if not data:
            logger.debug("Steam app %s has no data.", app_id)
            return None

        if data.get("type") != "game":
            logger.debug("Steam app %s skipped (type=%s).", app_id, data.get("type"))
            return None

        # noinspection PyTypeChecker
        return GameInfo(
            id=str(app_id),
            name=data.get("name"),
            description=data.get("short_description"),
            release_date=parse_release_date(data.get("release_date", {}).get("date")),
            developers=tuple(data.get("developers", [])),
            publishers=tuple(data.get("publishers", [])),
            genres=tuple(g.get("description") for g in data.get("genres", [])),
            platforms=tuple(k for k, v in data.get("platforms", {}).items() if v),
            screenshots=tuple(sc.get("path_full") for sc in data.get("screenshots", [])),
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
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(self.BASE_SEARCH_URL, params={"term": "Stardew Valley", "cc": "us", "l": "en"})
                return resp.status_code == 200
        except Exception:
            return False

    async def supports_feature(self, feature: str) -> bool:
        pass

    async def autocomplete(self, query: str) -> tuple[str, ...]:
        pass

    async def raw_provider_data(self, game_id: str) -> Any:
        pass