from ..caches.rawg_cache_mapping import LLMCacheMapper
from ..utils.nl_parser_helpers import preprocess_constraints, resolve_with_llm
from ..caches.rawg_metadata_cache import RAWGMetadataCache
import subprocess, json, logging, re, json5
from datetime import date
from ..models.game_filter import GameFilter

logger = logging.getLogger(__name__)

class NLQueryParser:
    def __init__(self, metadata_cache: RAWGMetadataCache, model: str = "llama3:8b"):
        self.model = model
        self.metadata_cache = metadata_cache
        self.llm_cache = LLMCacheMapper()

    def _run_ollama(self, user_input: str) -> dict:
        """
        Run Ollama LLM to extract structured metadata from a free-text game query.
        Returns a dict with keys: query, genres, platforms, tags.
        Autocorrects minor JSON formatting errors.
        """
        safe_input = user_input.replace('"', '\\"')
        prompt = f"""
You are a metadata extractor for a game recommendation system.
Given a user query about video games, return **only valid JSON** with these keys:
- "query": string, the cleaned query text
- "genres": list of strings, game genres mentioned
- "platforms": list of strings, platforms mentioned
- "tags": list of strings, tags/features mentioned (like multiplayer, co-op, crafting)

If a field is missing in the query, return an empty list or empty string.
Do not include any text outside the JSON.

Examples:
Input: "Looking for a multiplayer RPG on PC with crafting and exploration"
Output:
{{
  "query": "multiplayer RPG game with crafting and exploration",
  "genres": ["RPG"],
  "platforms": ["PC"],
  "tags": ["multiplayer", "crafting", "exploration"]
}}

Input: "Indie co-op farming game on Xbox, price under $50"
Output:
{{
  "query": "Indie co-op farming game",
  "genres": ["Indie"],
  "platforms": ["Xbox"],
  "tags": ["co-op", "farming"]
}}

Now extract JSON from this user input:
"{safe_input}"
"""

        try:
            result = subprocess.run(
                ["ollama", "run", self.model],
                input=prompt.encode("utf-8"),
                capture_output=True,
                check=True,
                timeout=30
            )
            raw_output = result.stdout.decode("utf-8").strip()

            # Extract JSON block
            match = re.search(r"\{.*}", raw_output, re.DOTALL)
            json_str = match.group(0) if match else raw_output

            # Try strict JSON first, fallback to JSON5
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                logger.warning("Strict JSON parsing failed, trying lenient JSON5 for Ollama output")
                try:
                    return json5.loads(json_str)
                except Exception as e2:
                    logger.warning("Lenient JSON parsing also failed: %s", e2)
                    return {"query": user_input, "genres": [], "platforms": [], "tags": []}

        except subprocess.TimeoutExpired:
            logger.warning("Ollama timed out for query: %s", user_input)
            return {"query": user_input, "genres": [], "platforms": [], "tags": []}
        except Exception as e:
            logger.warning("Ollama parsing failed: %s", e)
            logger.debug("Raw output: %s", raw_output)
            return {"query": user_input, "genres": [], "platforms": [], "tags": []}

    async def parse(self, user_input: str) -> tuple[GameFilter, dict]:
        """
        Parse a natural-language query into a GameFilter, returning the GameFilter
        and leftover/unresolved metadata.
        """
        # 1. Extract numeric/date constraints
        constraints = preprocess_constraints(user_input)

        # 2. Get structured metadata from LLM
        llm_data = self._run_ollama(user_input)

        # 3. Resolve genres/platforms/tags against metadata cache and LLM cache
        genres, leftover_genres = await resolve_with_llm(llm_data.get(
            "genres", []),
            self.metadata_cache,
            self.llm_cache,
            "genres"
        )

        platforms, leftover_platforms = await resolve_with_llm(
            llm_data.get("platforms", []),
            self.metadata_cache,
            self.llm_cache,
            "platforms"
        )

        tags, leftover_tags = await resolve_with_llm(
            llm_data.get("tags", []),
            self.metadata_cache,
            self.llm_cache,
            "tags"
        )

        # Step 4: Merge tags into genres if multiple genres exist
        if len(genres) > 1:
            # Only add tags that are not already in genres
            extra_genres = [t for t in tags if t not in genres]
            genres.extend(extra_genres)

        game_filter = GameFilter(
            genres=genres,
            platforms=platforms,
            tags=tags,
            min_price=constraints.get("min_price"),
            max_price=constraints.get("max_price"),
            release_date_from=constraints.get("release_date_from", date(1970, 1, 1)),
            release_date_to=constraints.get("release_date_to", date.today()),
        )

        leftover_metadata = {
            "genres": list(leftover_genres),
            "platforms": list(leftover_platforms),
            "tags": list(leftover_tags),
        }

        return game_filter, leftover_metadata