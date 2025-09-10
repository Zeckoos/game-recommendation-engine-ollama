import re
import logging
from difflib import get_close_matches
from datetime import date

logger = logging.getLogger(__name__)

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

# ---------- Metadata Resolution ----------
def resolve_with_fallback(raw_values: list[str], metadata_cache, category: str):
    """
    Resolve LLM outputs (tags/genres/platforms) to RAWG-supported ones.
    Returns (resolved, leftovers).
    """
    if category == "genres":
        source_dict = {name.lower(): name for _, name in metadata_cache.genres}
    elif category == "platforms":
        source_dict = {name.lower(): name for _, name in metadata_cache.platforms}
    else:  # tags
        source_dict = {name.lower(): name for _, name in metadata_cache.tags}

    resolved, leftovers = [], []
    for val in raw_values:
        key = val.lower().strip()
        if key in source_dict:
            resolved.append(source_dict[key])
        else:
            # Try fuzzy match
            match = get_close_matches(key, list(source_dict.keys()), n=1, cutoff=0.85)
            if match:
                resolved.append(source_dict[match[0]])
                logger.debug("Fuzzy resolved %s '%s' → '%s'", category, val, source_dict[match[0]])
            else:
                leftovers.append(val)

    if leftovers:
        logger.warning("Unresolved %s skipped: %s", category, leftovers)

    return tuple(resolved), tuple(leftovers)
