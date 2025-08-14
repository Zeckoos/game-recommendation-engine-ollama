from abc import ABC, abstractmethod
from typing import Any, List, Dict

from backend.app.models.game_info import GameInfo


class GameProvider(ABC):
    @abstractmethod
    async def search_games(self, filters: Dict) -> List[GameInfo]:
        """Search games by filters (tags, platforms, price, etc.)"""
        pass

    @abstractmethod
    async def get_game_details(self, game_id: str) -> Dict[str, Any]:
        """Fetch detailed info for a specific game by ID"""
        pass

    @abstractmethod
    async def get_game_price(self, game_id: str, currency: str) -> Dict[str, Any]:
        """Fetch pricing info for a game in a specified currency"""
        pass

    @abstractmethod
    async def get_game_screenshots(self, game_id: str) -> List[str]:
        """Fetch screenshots or media URLs for a game"""
        pass

    @abstractmethod
    async def get_trending_games(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetch trending or popular games"""
        pass

    @abstractmethod
    async def get_recommendations(self, seed_game_id: str) -> List[Dict[str, Any]]:
        """Get recommended games based on a seed game"""
        pass

    @abstractmethod
    async def check_health(self) -> bool:
        """Check if provider API is reachable and healthy"""
        pass

    @abstractmethod
    async def supports_feature(self, feature: str) -> bool:
        """Return whether a feature (e.g., multi-currency pricing) is supported"""
        pass

    @abstractmethod
    async def autocomplete(self, query: str) -> List[str]:
        """Provide autocomplete suggestions for user input"""
        pass

    @abstractmethod
    async def raw_provider_data(self, game_id: str) -> Dict[str, Any]:
        """Return raw data from the provider API for AI processing or debugging"""
        pass