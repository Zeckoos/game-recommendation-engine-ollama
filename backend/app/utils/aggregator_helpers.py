import re, unicodedata

def normalise_title(title: str) -> str:
    """
    Normalise game titles for comparison/search:
    - Lowercase
    - Strip accents/diacritics
    - Remove punctuation
    - Remove edition/extra qualifiers like 'PC Edition', 'Remastered', 'Definitive Edition'
    - Collapse multiple spaces
    """
    # Lowercase + remove accents
    text = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("utf-8").lower()

    # Common edition/variant keywords to strip
    patterns = [
        r"\bpc edition\b",
        r"\bvr edition\b",
        r"\bgame of the year\b",
        r"\bgoty\b",
        r"\bremastered\b",
        r"\bdefinitive edition\b",
        r"\bcomplete edition\b",
        r"\bultimate edition\b",
    ]
    for pat in patterns:
        text = re.sub(pat, "", text)

    # Remove punctuation
    text = re.sub(r"[^\w\s]", " ", text)

    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text).strip()

    return text