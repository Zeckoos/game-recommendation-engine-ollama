from ..caches.rawg_cache_mapping import LLMCacheMapper
from ..utils.nl_parser_helpers import preprocess_constraints, resolve_with_llm, filter_constraints_from_values
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
        You are a metadata extraction assistant for a video game recommendation system. 
        Your task is to extract **structured JSON** from a user's free-text query.
        
        Rules:
        1. Return only **valid JSON** with exactly these keys: 
           - "query": cleaned query text (can be empty)
           - "genres": list of genres mentioned (e.g., "RPG", "FPS", "Strategy")
           - "platforms": list of platforms mentioned (e.g., "PC", "Xbox", "PlayStation")
           - "tags": list of gameplay tags or features (e.g., "multiplayer", "co-op", "crafting")
        2. **Do not merge tags into genres**, even if they are similar.
        3. Ignore numbers, prices, or dates.
        4. Normalise common genre/platform synonyms where applicable.
        5. Include custom or new tags as long as they represent valid gameplay features, mechanics, or monetisation aspects.
        6. Avoid including vague or non-gameplay words in tags (e.g., "good", "fun", "game").
        7. Return empty lists if a field is missing.
        8. Output **strict JSON only**, with no extra commentary or formatting.
        
        Examples:
        
        Input: "Looking for a multiplayer RPG on PC with crafting and exploration"
        Output:
        {{
          "query": "",
          "genres": ["RPG"],
          "platforms": ["PC"],
          "tags": ["multiplayer", "crafting", "exploration"]
        }}
        
        Input: "Indie co-op farming game on Xbox, price under $50"
        Output:
        {{
          "query": "",
          "genres": ["Indie"],
          "platforms": ["Xbox"],
          "tags": ["co-op", "farming"]
        }}
        
        Input: "Free first-person shooter for PlayStation"
        Output:
        {{
          "query": "",
          "genres": ["FPS"],
          "platforms": ["PlayStation"],
          "tags": ["free", "first-person shooter"]
        }}
        
        Now extract JSON from this query: "{safe_input}"
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

        # 3. Resolve genres/platforms against metadata cache and LLM cache
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

        tags = filter_constraints_from_values(llm_data.get("tags", []))
        leftover_tags = [] # tags are free-form

        if constraints.get("max_price") == 0 and "free" not in tags:
            tags.append("free")

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
            "genres": leftover_genres,
            "platforms": leftover_platforms,
            "tags": leftover_tags
        }

        return game_filter, leftover_metadata