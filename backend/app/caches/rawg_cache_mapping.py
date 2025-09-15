import json, logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Use project root relative path, not absolute
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE_FILE = PROJECT_ROOT / "rawg_llm_mapping.json"

class LLMCacheMapper:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._mappings = {"genres": {}, "platforms": {}, "tags": {}}
            cls._instance._load()
        return cls._instance

    def _load(self):
        """Load existing cache from disk if available."""
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._mappings.update(data)
                logger.debug("Loaded LLM mapping cache from %s", CACHE_FILE)
            except Exception as e:
                logger.warning("Failed to load LLM mapping cache: %s", e)

    def _save(self):
        """Always overwrite cache file with latest mappings."""
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self._mappings, f, ensure_ascii=False, indent=2)
            logger.debug("Saved LLM mapping cache → %s", CACHE_FILE)
        except Exception as e:
            logger.error("Failed to save LLM mapping cache: %s", e)

    def add_mapping(self, category: str, synonym: str, canonical: str):
        """Add a mapping and persist immediately."""
        category = category.lower()
        if category not in self._mappings:
            self._mappings[category] = {}
        self._mappings[category][synonym.lower()] = canonical
        logger.info("Added LLM mapping → %s[%s] = %s", category, synonym, canonical)
        self._save()

    def resolve(self, category: str, synonym: str) -> str | None:
        """Return canonical mapping if exists, else None."""
        category = category.lower()
        return self._mappings.get(category, {}).get(synonym.lower())

    def all_mappings(self) -> dict:
        """Return all stored mappings."""
        return self._mappings