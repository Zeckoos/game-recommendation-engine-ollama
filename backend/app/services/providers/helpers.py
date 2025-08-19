from datetime import datetime, date
from typing import Optional
from backend.app.models.game_info import GameInfo
from backend.app.utils.rawg_metadata_cache import RAWGMetadataCache


def parse_rawg_game(game: dict, metadata_cache: Optional[RAWGMetadataCache] = None) -> GameInfo:
    """Convert RAWG API game dict to GameInfo, normalising IDs to names using metadata cache."""
    genres = []
    for g in game.get("genres", []):
        genre_id = int(g["id"]) if isinstance(g, dict) else int(g)
        genres.append(metadata_cache.genre_map.get(genre_id, str(genre_id)))

    platforms = []
    for p in game.get("platforms", []):
        platform_id = int(p["platform"]["id"]) if isinstance(p, dict) else int(p)
        platforms.append(metadata_cache.platform_map.get(platform_id, str(platform_id)))

    return GameInfo(
        id=str(game["id"]),
        name=game["name"],
        description=game.get("description_raw"),
        release_date=date.fromisoformat(game["released"]) if game.get("released") else None,
        genres=tuple(genres),
        platforms=tuple(platforms),
        developers=tuple(dev["name"] for dev in game.get("developers", [])) or tuple(),
        publishers=tuple(pub["name"] for pub in game.get("publishers", [])) or tuple(),
        screenshots=(game.get("background_image"),) if game.get("background_image") else tuple(),
        store_url=f"https://rawg.io/games/{game['slug']}" if game.get("slug") else None,
    )

def parse_release_date(steam_date: Optional[str]) -> Optional[date]:
    """Parse Steam's release date string into a date object."""
    if not steam_date:
        return None
    for fmt in ("%b %d, %Y", "%d %b, %Y"):  # Steam varies formats
        try:
            return datetime.strptime(steam_date, fmt).date()
        except ValueError:
            continue
    return None

def parse_price(details_data: dict) -> Optional[float]:
    """Extract price from Steam API data, return 0.0 for free games."""
    price_info = details_data.get("price_overview")

    if price_info and "final" in price_info:
        return price_info["final"] / 100  # cents → dollars

    if details_data.get("is_free"):
        return 0.0

    return None