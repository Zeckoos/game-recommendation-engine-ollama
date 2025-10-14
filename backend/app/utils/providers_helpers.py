from datetime import date, datetime
from typing import Any
from .nl_parser_helpers import resolve_with_llm
from ..models.game_info import GameInfo
from ..caches.rawg_metadata_cache import RAWGMetadataCache
from ..caches.rawg_cache_mapping import LLMCacheMapper
import logging

logger = logging.getLogger(__name__)

async def resolve_filters(metadata_cache: RAWGMetadataCache, filters: dict, llm_cache: LLMCacheMapper):
    """
    Resolve filter names → IDs using RAWG metadata, with LLM mapping fallback.
    Returns: (resolved_ids_dict, still_missing_dict)
    """
    # Build initial name → ID dicts
    genre_dict = {name.lower(): id for id, name in metadata_cache.genres}
    platform_dict = {name.lower(): id for id, name in metadata_cache.platforms}
    tag_dict = {name.lower(): id for id, name in metadata_cache.tags}

    async def resolve_category(category: str, values: list[str], source_dict: dict[str, Any]):
        # Skip tags entirely
        if category == "tags":
            return list(values), list()  # all values preserved, no leftovers

        # Use the shared LLM + metadata helper
        resolved_names, leftovers = await resolve_with_llm(values, metadata_cache, llm_cache, category)
        resolved_ids = [source_dict[name.lower()] for name in resolved_names if name.lower() in source_dict]
        return resolved_ids, leftovers

    genre_ids, missing_genres = await resolve_category("genres", filters.get("genres", []), genre_dict)
    platform_ids, missing_platforms = await resolve_category("platforms", filters.get("platforms", []), platform_dict)
    tag_ids, missing_tags = await resolve_category("tags", filters.get("tags", []), tag_dict)

    # Log any unresolved filters
    if missing_genres:
        logger.warning("Unresolved genres skipped: %s", missing_genres)
    if missing_platforms:
        logger.warning("Unresolved platforms skipped: %s", missing_platforms)
    if missing_tags:
        logger.warning("Unresolved tags skipped: %s", missing_tags)

    return (
        {"genres": genre_ids, "platforms": platform_ids, "tags": tag_ids},
        {"genres": missing_genres, "platforms": missing_platforms, "tags": missing_tags}
    )

def parse_rawg_game(data: dict, metadata_cache: RAWGMetadataCache) -> GameInfo:
    """Convert RAWG API game JSON into GameInfo, resolving IDs to names where possible."""
    genre_dict = {str(ID): name for ID, name in metadata_cache.genres}
    platform_dict = {str(ID): name for ID, name in metadata_cache.platforms}

    genres = []
    for g in data.get("genres", []):
        if isinstance(g, dict) and "name" in g:
            genres.append(g["name"])
        elif isinstance(g, (str, int)):
            genres.append(genre_dict.get(str(g), str(g)))
        else:
            continue # skips unknown structures

    platforms = []
    for p in data.get("platforms", []):
        if isinstance(p, dict) and "platform" in p and "name" in p["platform"]:
            platforms.append(p["platform"]["name"])
        elif isinstance(p, (str, int)):
            platforms.append(platform_dict.get(str(p), str(p)))
        else:
            continue

    screenshots = tuple(s.get("image") for s in data.get("short_screenshots", []) if s.get("image"))

    release_date = parse_release_date(data.get("released"))

    game_info = GameInfo(
        id=str(data.get("id")),
        name=data.get("name", "Unknown"),
        description=data.get("description_raw") or data.get("description"),
        release_date=release_date,
        developers=tuple(d.get("name") for d in data.get("developers", []) if "name" in d),
        publishers=tuple(p.get("name") for p in data.get("publishers", []) if "name" in p),
        genres=tuple(genres),
        platforms=tuple(platforms),
        screenshots=screenshots,
        price=None,
        store_url=f"https://rawg.io/games/{data.get('slug')}" if data.get("slug") else None,
    )

    is_free = (
            data.get("is_free") is True
            or any(g.lower() == "free to play" for g in game_info.genres)
            or "free" in (data.get("tags") or [])
    )
    if is_free:
        game_info.price = 0.0

    return game_info

def parse_release_date(raw_date: str | None) -> date | None:
    """Parse various release date formats into a date object."""
    if not raw_date:
        return None
    # Try ISO format first
    try:
        return date.fromisoformat(raw_date)
    except ValueError:
        pass
    # Try Steam formats
    for fmt in ("%b %d, %Y", "%d %b, %Y", "%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            dt = datetime.strptime(raw_date, fmt)
            return dt.date()
        except ValueError:
            continue
    return None

def parse_price(details_data: dict) -> float | None:
    """Extract price if available; return None otherwise."""
    price_info = details_data.get("price_overview")
    if price_info and "final" in price_info:
        return price_info["final"] / 100
    if details_data.get("is_free"):
        return 0.0
    return None