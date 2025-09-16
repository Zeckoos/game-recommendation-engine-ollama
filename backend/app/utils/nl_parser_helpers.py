import re, logging, os, json, subprocess
from datetime import date
from difflib import get_close_matches
from typing import List, Tuple

from ..caches.rawg_cache_mapping import LLMCacheMapper
from ..caches.rawg_metadata_cache import RAWGMetadataCache

logger = logging.getLogger(__name__)

OLLAMA_HOST = os.getenv("OLLAMA_HOST")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")

llm_cache = LLMCacheMapper()

# ---------- Regex Preprocessing ----------
def preprocess_constraints(user_input: str) -> dict:
    """Extract numeric and date constraints using regex. Returns dict with floats and date objects."""
    constraints = {}

    # --- Price handling ---
    price_match = re.search(r"(?:under|below|less than)\s*\$?(\d+)", user_input, re.I)
    if price_match:
        constraints["max_price"] = float(price_match.group(1))

    price_match = re.search(r"(?:over|above|more than)\s*\$?(\d+)", user_input, re.I)
    if price_match:
        constraints["min_price"] = float(price_match.group(1))

    between_match = re.search(r"between\s*\$?(\d+)\s*and\s*\$?(\d+)", user_input, re.I)
    if between_match:
        constraints["min_price"] = float(between_match.group(1))
        constraints["max_price"] = float(between_match.group(2))

    # --- Release year handling ---
    after_match = re.search(r"(?:after|since)\s*(\d{4})", user_input, re.I)
    if after_match:
        constraints["release_date_from"] = date(int(after_match.group(1)), 1, 1)

    before_match = re.search(r"(?:before|earlier than)\s*(\d{4})", user_input, re.I)
    if before_match:
        constraints["release_date_to"] = date(int(before_match.group(1)) - 1, 12, 31)

    between_years = re.search(r"between\s*(\d{4})\s*and\s*(\d{4})", user_input, re.I)
    if between_years:
        constraints["release_date_from"] = date(int(between_years.group(1)), 1, 1)
        constraints["release_date_to"] = date(int(between_years.group(2)), 12, 31)

    return constraints

def filter_constraints_from_values(values: List[str]) -> List[str]:
    """Remove numeric values, price constraints, or date-related strings."""
    pattern = re.compile(r"\b(?:under|over|between|less than|more than|\$?\d+|after|since|before|earlier than)\b", re.I)
    return [v for v in values if not pattern.search(v)]

async def call_llm_for_canonical(category: str, values: List[str], allowed_values: List[str]) -> dict:
    """
    Map multiple 'values' to a canonical term in 'allowed_values'.
    Returns: {"canonical": <canonical_name>} or None if uncertain
    """
    filtered_values = filter_constraints_from_values(values)
    if not filtered_values:
        return {v: None for v in values}

    user_values = json.dumps(values)
    allowed_values = json.dumps(allowed_values)

    # LLM fallback
    prompt = f"""
    You are a game taxonomy assistant. Your job is to map user input to canonical {category}.
    Ignore numeric values, price constraints, or dates. Map only valid {category} terms.
    User input: "{user_values}"
    Allowed values: {allowed_values}

    Rules:
    1. Match each input value to the allowed values as accurately as possible.
    2. Consider synonyms, abbreviations, and common misspellings.
    3. If you cannot confidently map a value, return null for it.
    4. Return **only JSON**: a dict mapping each input value to its canonical value or null.

    Example:
    Input values: ["first-person shooter", "rpg", "coop"]
    Allowed: ["FPS", "RPG", "Co-op"]
    Output:
    {{
      "first-person shooter": "FPS",
      "rpg": "RPG",
      "coop": "Co-op"
    }}
    """

    try:
        result = subprocess.run(
            ["ollama", "run", OLLAMA_MODEL],
            input=prompt.encode("utf-8"),
            capture_output=True,
            check=True,
            timeout=60
        )
        raw_output = result.stdout.decode("utf-8").strip()
        match = re.search(r"\{.*}", raw_output, re.DOTALL)
        json_str = match.group(0) if match else raw_output
        data = json.loads(json_str)

        return {k: v for k, v in data.items()}

    except Exception as e:
        logger.warning("LLM canonicalisation batch failed for category '%s': %s", category, e)

        return {v: None for v in values}

async def resolve_with_llm(raw_values: List[str], metadata_cache: RAWGMetadataCache,
                           llm_cache: LLMCacheMapper, category: str) -> Tuple[List[str], List[str]]:
    """
    Resolve values using metadata cache and LLM cache mappings, fuzzy matching and LLM fallback.
    Returns (resolved, leftovers)
    """
    if not raw_values:
        return [], []

    # Lowercase lookup for exact/fuzzy match
    source_dict = {name.lower(): name for _, name in getattr(metadata_cache, category)}

    resolved, leftovers = [], []

    # 1. Exact/fuzzy/LLM cache match
    unknown_values = []

    for val in raw_values:
        key = val.lower().strip()
        if key in source_dict:
            resolved.append(source_dict[key])

        elif cached := llm_cache.resolve(category, key):
            resolved.append(cached)

        else:
            match = get_close_matches(key, list(source_dict.keys()), n=1, cutoff=0.85)
            if match:
                resolved.append(source_dict[match[0]])

            else:
                unknown_values.append(val)

    # 2. Batch LLM for remaining unknown values
    if unknown_values:
        llm_results = await call_llm_for_canonical(category, unknown_values, list(source_dict.values()))
        for val in unknown_values:
            canonical = llm_results.get(val)
            if canonical is None:
                leftovers.append(val)

            else:
                resolved.append(canonical)
                llm_cache.add_mapping(category, val, canonical)

    return resolved, leftovers
