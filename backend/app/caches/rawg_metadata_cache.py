from pathlib import Path
from dotenv import load_dotenv
import httpx, os, logging, json

load_dotenv()
RAWG_API_KEY = os.getenv("RAWG_API_KEY")
BASE_URL = "https://api.rawg.io/api"

# Use project root relative path, not absolute
CACHE_DIR = Path(__file__).resolve().parents[1].joinpath('caches')
CACHE_FILE = CACHE_DIR / "rawg_metadata_cache.json"

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

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
        return {int(id): name for id, name in self.genres}

    @property
    def platform_map(self) -> dict[int, str]:
        """Return dict mapping platform ID → name for easy lookup."""
        return {int(id): name for id, name in self.platforms}

    @property
    def tag_map(self) -> dict[int, str]:
        """Return dict mapping tag ID → name for easy lookup."""
        return {int(id): name for id, name in self.tags}

    async def initialise(self):
        """Fetch metadata from RAWG API."""
        async with httpx.AsyncClient() as client:
            try:
                genres_resp = await client.get(f"{BASE_URL}/genres", params={"key": RAWG_API_KEY})
                genres_resp.raise_for_status()
                self.genres = tuple((g["id"], g["name"]) for g in genres_resp.json().get("results", []))

                platforms_resp = await client.get(f"{BASE_URL}/platforms", params={"key": RAWG_API_KEY})
                platforms_resp.raise_for_status()
                self.platforms = tuple((p["id"], p["name"]) for p in platforms_resp.json().get("results", []))

                tags_resp = await client.get(f"{BASE_URL}/tags", params={"key": RAWG_API_KEY})
                tags_resp.raise_for_status()
                self.tags = tuple((t["id"], t["name"]) for t in tags_resp.json().get("results", []))

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
        if not os.path.exists(CACHE_FILE):
            return False
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.genres = tuple(data.get("genres", ()))
            self.platforms = tuple(data.get("platforms", ()))
            self.tags = tuple(data.get("tags", ()))
            return True
        except Exception as e:
            logger.warning("Failed to load cache from disk: %s", e)
            return False

    async def save_to_disk(self):
        """Save metadata to JSON cache file."""
        try:
            temp_file = CACHE_FILE.with_suffix(CACHE_FILE.name + ".temp")
            data = {
                "genres": self.genres,
                "platforms": self.platforms,
                "tags": self.tags,
            }
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(temp_file, CACHE_FILE)
            logger.debug("Saved metadata to disk cache")
        except Exception as e:
            logger.error("Failed to save cache to disk: %s", e)