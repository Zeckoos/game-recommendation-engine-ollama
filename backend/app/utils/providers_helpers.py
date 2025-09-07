from datetime import datetime, date
from typing import Optional
from ..models.game_info import GameInfo
from .rawg_metadata_cache import RAWGMetadataCache
import logging

logger = logging.getLogger(__name__)

async def resolve_filters(metadata_cache: RAWGMetadataCache, filters: dict):
    """
    Resolve filter names → IDs.
    Refresh metadata once per session if unknown filters exist.
    Returns: (resolved_ids_dict, still_missing_dict)
    """
    # Initial name → ID dicts
    genre_dict = {name.lower(): id for id, name in metadata_cache.genres}
    platform_dict = {name.lower(): id for id, name in metadata_cache.platforms}
    tag_dict = {name.lower(): id for id, name in metadata_cache.tags}

    # Attempt initial resolution
    missing_genres = set(filters.get("genres", [])) - set(name.lower() for name in genre_dict.keys())
    missing_platforms = set(filters.get("platforms", [])) - set(name.lower() for name in platform_dict.keys())
    missing_tags = set(filters.get("tags", [])) - set(name.lower() for name in tag_dict.keys())

    # Refresh metadata once if needed
    if (missing_genres or missing_platforms or missing_tags) and not metadata_cache._session_refreshed:
        logger.debug("Refreshing RAWG metadata due to unknown filters")
        await metadata_cache.refresh_if_needed()
        # Rebuild dicts after refresh
        genre_dict = {name.lower(): id for id, name in metadata_cache.genres}
        platform_dict = {name.lower(): id for id, name in metadata_cache.platforms}
        tag_dict = {name.lower(): id for id, name in metadata_cache.tags}

    # Resolve again
    genre_ids = [genre_dict[g.lower()] for g in filters.get("genres", []) if g.lower() in genre_dict]
    platform_ids = [platform_dict[p.lower()] for p in filters.get("platforms", []) if p.lower() in platform_dict]
    tag_ids = [tag_dict[t.lower()] for t in filters.get("tags", []) if t.lower() in tag_dict]

    # Identify still missing filters
    still_missing_genres = set(filters.get("genres", [])) - set(name.lower() for name in genre_dict.keys())
    still_missing_platforms = set(filters.get("platforms", [])) - set(name.lower() for name in platform_dict.keys())
    still_missing_tags = set(filters.get("tags", [])) - set(name.lower() for name in tag_dict.keys())

    return (
        {"genres": genre_ids, "platforms": platform_ids, "tags": tag_ids},
        {"genres": still_missing_genres, "platforms": still_missing_platforms, "tags": still_missing_tags}
    )

def parse_rawg_game(data: dict, metadata_cache: RAWGMetadataCache) -> GameInfo:
    """Convert RAWG API game JSON into GameInfo, resolving IDs to names where possible."""

    # Build lookup dicts once from cache
    genre_dict = {str(id): name for id, name in metadata_cache.genres}
    platform_dict = {str(id): name for id, name in metadata_cache.platforms}

    # Resolve genres: prefer names, fallback to IDs as string
    genres = []
    for g in data.get("genres", []):
        if isinstance(g, dict) and "name" in g:
            genres.append(g["name"])
        elif isinstance(g, (str, int)):
            genres.append(genre_dict.get(str(g), str(g)))

    # Resolve platforms: prefer names, fallback to IDs as string
    platforms = []
    for p in data.get("platforms", []):
        if isinstance(p, dict) and "platform" in p and "name" in p["platform"]:
            platforms.append(p["platform"]["name"])
        elif isinstance(p, (str, int)):
            platforms.append(platform_dict.get(str(p), str(p)))

    screenshots = tuple(s.get("image") for s in data.get("short_screenshots", []) if s.get("image"))

    return GameInfo(
        id=str(data.get("id")),
        name=data.get("name", "Unknown"),
        description=data.get("description_raw") or data.get("description"),
        release_date=data.get("released"),
        developers=tuple(d.get("name") for d in data.get("developers", []) if "name" in d),
        publishers=tuple(p.get("name") for p in data.get("publishers", []) if "name" in p),
        genres=tuple(genres),
        platforms=tuple(platforms),
        screenshots=screenshots,
        price=None,
        store_url=f"https://rawg.io/games/{data.get('slug')}" if data.get("slug") else None,
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