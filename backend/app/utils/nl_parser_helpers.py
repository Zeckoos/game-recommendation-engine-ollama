import re, logging, os, json, subprocess
from datetime import date
from difflib import get_close_matches

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

async def call_llm_for_canonical(category: str, value: str, allowed_values: list[str]) -> dict:
    """
    Map 'value' to a canonical term in 'allowed_values'.
    Resolution order:
      1. Exact match (case-insensitive)
      2. Fuzzy match (difflib)
      3. LLM canonicalisation as fallback
    Returns: {"canonical": <canonical_name>}
    """
    val_lower = value.lower()
    allowed_lower = [v.lower() for v in allowed_values]

    # 1. Exact match
    if val_lower in allowed_lower:
        canonical = allowed_values[allowed_lower.index(val_lower)]
        return {"canonical": canonical}

    # 2. Fuzzy match
    match = get_close_matches(val_lower, allowed_lower, n=1, cutoff=0.8)
    if match:
        canonical = allowed_values[allowed_lower.index(match[0])]
        logger.debug("Fuzzy matched '%s' → '%s'", value, canonical)
        return {"canonical": canonical}

    # 3. LLM fallback
    prompt = f"""
    You are a game taxonomy assistant.
    Category: {category}
    User input: "{value}"
    Allowed values: {allowed_values}

    Return only a JSON object with key "canonical" set to the best matching allowed value.
    If no match, return the input as canonical.
    """

    try:
        result = subprocess.run(
            ["ollama", "run", OLLAMA_MODEL],
            input=prompt.encode("utf-8"),
            capture_output=True,
            check=True,
            timeout=30
        )
        raw_output = result.stdout.decode("utf-8").strip()
        match = re.search(r"\{.*}", raw_output, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            return {"canonical": data.get("canonical", value)}
    except Exception as e:
        logger.warning("LLM canonicalization failed for '%s': %s", value, e)

    # Default fallback
    return {"canonical": value}

async def resolve_with_llm(raw_values: list[str], metadata_cache: RAWGMetadataCache,
                           llm_cache: LLMCacheMapper, category: str):
    """
    Resolve values using metadata cache and LLM cache mappings.
    Returns (resolved, leftovers)
    """
    # Build lowercase lookup from metadata cache
    if category == "genres":
        source_dict = {name.lower(): name for _, name in metadata_cache.genres}
    elif category == "platforms":
        source_dict = {name.lower(): name for _, name in metadata_cache.platforms}
    else:  # tags
        source_dict = {name.lower(): name for _, name in metadata_cache.tags}

    resolved, leftovers = [], []

    for val in raw_values:
        key = val.lower().strip()

        # 1. Check metadata cache
        if key in source_dict:
            resolved.append(source_dict[key])
            continue

        # 2. Check LLM mapping cache
        canonical = llm_cache.resolve(category, key)
        if canonical:
            resolved.append(canonical)
            continue

        # 3. Fuzzy match against metadata cache
        match = get_close_matches(key, list(source_dict.keys()), n=1, cutoff=0.85)
        if match:
            resolved.append(source_dict[match[0]])
            continue

        # 4. Still unresolved → call LLM for canonical mapping
        result = await call_llm_for_canonical(category, val, list(source_dict.values()))
        canonical_name = result["canonical"]
        resolved.append(canonical_name)
        # Save in LLM cache
        llm_cache.add_mapping(category, val, canonical_name)

    return tuple(resolved), tuple()
