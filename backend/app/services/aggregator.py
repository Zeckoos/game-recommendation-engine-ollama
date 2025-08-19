from difflib import get_close_matches
from backend.app.models.game_filter import GameFilter
from backend.app.models.game_info import GameInfo
from backend.app.models.provider_response import ProviderResponse
from backend.app.services.providers.rawg import RAWGProvider
from backend.app.services.providers.steam import SteamProvider
import asyncio, httpx, logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

class GameAggregator:
    """Aggregates games from RAWG and enriches them via Steam."""

    def __init__(self, rawg: RAWGProvider, steam: SteamProvider):
        self.rawg = rawg
        self.steam = steam

    @classmethod
    async def create(cls):
        """Factory method for async initialisation."""
        rawg = await RAWGProvider.create()
        steam = SteamProvider()
        return cls(rawg=rawg, steam=steam)

    async def aggregate(self, filters: GameFilter, limit: int = 15, page: int = 1) -> ProviderResponse:
        """
        Fetch games from RAWG, enrich via Steam, and apply price filtering.
        Supports pagination via `page` and `limit`.
        """
        # Step 1: Search RAWG by filters
        offset = (page - 1) * limit
        rawg_resp: ProviderResponse = await self.rawg.search_games(filters, total_limit=limit, offset=offset)
        rawg_games = rawg_resp.results
        logger.debug("RAWG returned %d games", len(rawg_games))

        # Step 2: Enrich game info via Steam
        async def enrich_with_steam(game: GameInfo) -> GameInfo:
            try:
                steam_resp: ProviderResponse = await self.steam.search_games(game.name)
                if not steam_resp.results:
                    return game

                # Fuzzy match the closest Steam game
                match_name = get_close_matches(game.name, [s.name for s in steam_resp.results], n=1)
                if not match_name:
                    return game

                steam_game = next((s for s in steam_resp.results if s.name == match_name[0]), None)
                if not steam_game:
                    return game

                # Merge fields (prefer Steam if available)
                game.name = steam_game.name or game.name
                game.description = steam_game.description or game.description
                game.release_date = steam_game.release_date or game.release_date
                game.platforms = steam_game.platforms or game.platforms
                game.genres = steam_game.genres or game.genres
                game.developers = steam_game.developers or game.developers
                game.publishers = steam_game.publishers or game.publishers
                game.screenshots = steam_game.screenshots or game.screenshots
                game.price = steam_game.price if steam_game.price is not None else game.price
                game.store_url = steam_game.store_url or game.store_url

                # Inject Free To Play tag if price is 0
                if game.price == 0.0 and "Free To Play" not in game.genres:
                    game.genres += ("Free To Play",)

            except httpx.HTTPError as e:
                logger.warning("Steam enrichment failed for '%s': %s", game.name, e)

            return game

        enriched_games = await asyncio.gather(*[enrich_with_steam(g) for g in rawg_games])

        # Step 3: Filter by price
        min_price = filters.min_price or 0
        max_price = filters.max_price or float("inf")
        filtered_games = tuple(
            g for g in enriched_games if g.price is None or (min_price <= g.price <= max_price)
        )

        logger.debug("Filtered to %d games after price filter", len(filtered_games))
        return ProviderResponse(results=filtered_games, total=len(filtered_games))