import asyncio
from pathlib import Path
from dotenv import load_dotenv
import httpx, os, logging, json

load_dotenv()
RAWG_API_KEY = os.getenv("RAWG_API_KEY")
BASE_URL = "https://api.rawg.io/api"

# Use project root relative path, not absolute
CACHE_DIR = Path(__file__).resolve().parents[1].joinpath('caches', 'rawg_generated_caches')
GENRES_FILE = CACHE_DIR / "genres_cache.json"
TAGS_FILE = CACHE_DIR / "tags_cache.json"
PLATFORMS_FILE = CACHE_DIR / "platforms_cache.json"

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

async def fetch_all_pages(client, endpoint: str, params: dict, max_pages: int = 20) -> list[dict]:
    """
    Fetch all paginated results for a RAWG endpoint.
    Includes light throttling to avoid 429s.
    """
    page = 1
    results = []
    while True:
        resp = await client.get(
            f"{BASE_URL}/{endpoint}",
            params={**params, "page": page, "page_size": 50},
            timeout=30.0
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("results", [])
        if not items:
            break
        results.extend(items)
        logger.debug("%s: fetched page %d → %d items", endpoint, page, len(items))

        if not data.get("next") or page >= max_pages:
            break

        page += 1
        await asyncio.sleep(0.25)  # polite delay
    return results

class RAWGMetadataCache:
    _instance = None
    _session_refreshed = False # Track if we've refreshed metadata this session

    def __init__(self):
        self.tags = None
        self.platforms = None
        self.genres = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.genres = tuple()
            cls._instance.platforms = tuple()
            cls._instance.tags = tuple()
        return cls._instance

    @property
    def genre_map(self) -> dict[int, str]:
        """Return dict mapping genre ID → name for easy lookup."""
        return {int(row[0]): row[-1] for row in self.genres}

    @property
    def platform_map(self) -> dict[int, str]:
        """Return dict mapping platform ID → name for easy lookup."""
        return {int(row[0]): row[-1] for row in self.platforms}

    @property
    def tag_map(self) -> dict[int, str]:
        """Return dict mapping tag ID → name for easy lookup."""
        return {int(row[0]): row[-1] for row in self.tags}

    async def initialise(self):
        """Fetch metadata from RAWG API."""
        async with httpx.AsyncClient() as client:
            try:
                genres_data = await fetch_all_pages(client, "genres", {"key": RAWG_API_KEY})
                platforms_data = await fetch_all_pages(client, "platforms", {"key": RAWG_API_KEY})
                tags_data = await fetch_all_pages(client, "tags", {"key": RAWG_API_KEY})

                self.genres = tuple((g["id"], g["slug"], g["name"]) for g in genres_data)
                self.platforms = tuple((p["id"], p["slug"], p["name"]) for p in platforms_data)
                self.tags = tuple((t["id"], t["slug"], t["name"]) for t in tags_data)

                logger.debug(
                    "RAWG Metadata loaded → %d genres, %d platforms, %d tags",
                    len(self.genres), len(self.platforms), len(self.tags)
                )

                await self.save_to_disk()
                RAWGMetadataCache._session_refreshed = True

            except Exception as e:
                logger.error("Failed to fetch RAWG metadata: %s", e)
                raise

    async def refresh_if_needed(self):
        """Refresh the metadata once per session if not already done."""
        logger.debug("Refreshing RAWG metadata for this session")
        try:
            await self.initialise()
        except Exception:
            logger.warning("Metadata refresh failed, will retry on next access")

    async def load_or_fetch(self):
        """Load cache from disk or fetch from RAWG API."""
        if await self.load_from_disk():
            logger.debug("Loaded metadata from disk cache")
        else:
            logger.debug("Disk cache missing or invalid, fetching from RAWG API")
            await self.initialise()

    async def load_from_disk(self) -> bool:
        """Load metadata from JSON cache file."""
        try:
            # Helper for cleaner load
            def load_json(file_path: Path):
                if not file_path.exists():
                    return tuple()
                with open(file_path, "r", encoding="utf-8") as f:
                    return tuple(json.load(f))

            self.genres = load_json(GENRES_FILE)
            self.platforms = load_json(PLATFORMS_FILE)
            self.tags = load_json(TAGS_FILE)

            # Validate that at least one file has data
            if not any((self.genres, self.platforms, self.tags)):
                logger.debug("Cache files exist but are empty — refetching required")
                return False

            logger.debug(
                "Loaded metadata → %d genres, %d platforms, %d tags",
                len(self.genres), len(self.platforms), len(self.tags),
            )
            return True

        except Exception as e:
            logger.warning("Failed to load one or more cache files: %s", e)
            return False

    async def save_to_disk(self):
        """Save metadata to JSON cache file."""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)

            # Save each metadata category separately
            for name, file_path, data in [
                ("genres", GENRES_FILE, self.genres),
                ("platforms", PLATFORMS_FILE, self.platforms),
                ("tags", TAGS_FILE, self.tags),
            ]:
                temp_file = file_path.with_suffix(".temp")
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                os.replace(temp_file, file_path)
                logger.debug("Saved %s metadata → %s", name, file_path)

        except Exception as e:
            logger.error("Failed to save one or more metadata files: %s", e)

