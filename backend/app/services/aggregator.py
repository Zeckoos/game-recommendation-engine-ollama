from typing import List
from difflib import get_close_matches
from backend.app.models.game_filter import GameFilter
from backend.app.models.game_info import GameInfo
from backend.app.services.providers.rawg import RAWGProvider
from backend.app.services.providers.steam import SteamProvider
import asyncio, httpx

class GameAggregator:
    def __init__(self):
        self.rawg = RAWGProvider()
        self.steam = SteamProvider()

    async def aggregate(self, filters: GameFilter, limit: int = 10) -> List[GameInfo]:
        # Convert Pydantic model to dict
        filters_dict = filters.model_dump()
        filters_dict["limit"] = limit

        # Step 1: Search RAWG by tags/genres
        rawg_results: List[GameInfo] = await self.rawg.search_games(filters_dict)

        # Step 2: Extract names/ids to enrich via Steam
        async def enrich_with_steam(game: GameInfo) -> GameInfo | None:
            try:
                steam_results = await self.steam.search_games(game.name)
                if not steam_results:
                    return game

                # Fuzzy match closest Steam game
                match_name = get_close_matches(game.name, [s.name for s in steam_results], n=1)
                if not match_name:
                    return game

                steam_game = next((s for s in steam_results if s.name == match_name[0]), None)
                if not steam_game:
                    return game

                # Update game info
                game.name = steam_game.name or game.name
                game.description = steam_game.description or game.description
                game.release_date = steam_game.release_date or game.release_date
                game.platforms = steam_game.platforms or game.platforms
                game.genres = steam_game.genres or game.genres
                game.developers = steam_game.developers or game.developers
                game.publishers = steam_game.publishers or game.publishers
                game.screenshots = steam_game.screenshots or game.screenshots
                game.price = steam_game.price or game.price
                game.store_url = steam_game.store_url or game.store_url

            except httpx.HTTPError as e:
                print(f"Steam enrichment error for {game.name}: {e}")
            return game

        enriched_results = await asyncio.gather(*[enrich_with_steam(g) for g in rawg_results])

        # Step 3: Filter by price
        min_price = filters.min_price or 0
        max_price = filters.max_price or float("inf")
        filtered_results = [
            g for g in enriched_results
            if g.price is None or (min_price <= g.price <= max_price)
        ]

        return filtered_results