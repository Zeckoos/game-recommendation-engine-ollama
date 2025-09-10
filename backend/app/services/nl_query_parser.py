from ..utils.nl_parser_helpers import preprocess_constraints, resolve_with_fallback
from ..utils.rawg_metadata_cache import RAWGMetadataCache
import subprocess, json, logging, re
from datetime import date
from ..models.game_filter import GameFilter

logger = logging.getLogger(__name__)

class NLQueryParser:
    def __init__(self, metadata_cache: RAWGMetadataCache, model: str = "llama3:8b"):
        self.model = model
        self.metadata_cache = metadata_cache

    def _run_ollama(self, user_input: str) -> dict:
        safe_input = user_input.replace('"', '\\"')
        prompt = f"""
    Return only valid JSON with keys: query, genres, platforms, tags.
    If a field is missing, return [] for lists or "" for query.

    User query: "{safe_input}"
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

            # Extract JSON block using regex
            match = re.search(r"\{.*}", raw_output, re.DOTALL)
            if match:
                json_str = match.group(0)
                return json.loads(json_str)
            else:
                logger.warning("No JSON found in Ollama output for query: %s", user_input)
                logger.debug("Raw output: %s", raw_output)
                return {"query": user_input, "genres": [], "platforms": [], "tags": []}

        except subprocess.TimeoutExpired:
            logger.warning("Ollama timed out for query: %s", user_input)
            return {"query": user_input, "genres": [], "platforms": [], "tags": []}
        except Exception as e:
            logger.warning("Ollama parsing failed: %s", e)
            logger.debug("Raw output: %s", raw_output)
            return {"query": user_input, "genres": [], "platforms": [], "tags": []}

    def parse(self, user_input: str) -> tuple[GameFilter, dict]:
        """
        Parse a natural-language query into a GameFilter, returning the GameFilter
        and leftover/unresolved metadata.
        """
        # Step 1. Preprocess numeric/date constraints
        constraints = preprocess_constraints(user_input)

        # Step 2. Use Ollama for query, genres, platforms, tags
        llm_data = self._run_ollama(user_input)

        # Step 3. Resolve against RAWG metadata
        genres, leftover_genres = resolve_with_fallback(llm_data.get("genres", []), self.metadata_cache, "genres")
        platforms, leftover_platforms = resolve_with_fallback(llm_data.get("platforms", []), self.metadata_cache, "platforms")
        tags, leftover_tags = resolve_with_fallback(llm_data.get("tags", []), self.metadata_cache, "tags")

        # Convert leftovers to lists for safe concatenation
        leftover_genres = list(leftover_genres)
        leftover_platforms = list(leftover_platforms)
        leftover_tags = list(leftover_tags)

        # Step 4. Push leftovers into query fallback
        extra_query = " ".join(leftover_genres + leftover_platforms + leftover_tags)
        final_query = " ".join(filter(None, [llm_data.get("query"), extra_query]))

        # Step 5. Construct GameFilter with defaults
        game_filter = GameFilter(
            query=final_query,
            genres=genres,
            platforms=platforms,
            tags=tags,
            min_price=constraints.get("min_price"),
            max_price=constraints.get("max_price"),
            release_date_from=constraints.get("release_date_from", date(1970, 1, 1)),
            release_date_to=constraints.get("release_date_to", date.today()),
        )

        # Step 6. Prepare leftover metadata for logging/debugging
        leftover_metadata = {
            "genres": leftover_genres,
            "platforms": leftover_platforms,
            "tags": leftover_tags,
        }

        return game_filter, leftover_metadata