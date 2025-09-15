import re

def normalise_title(title: str) -> str:
    """Normalize game titles by removing platform suffixes or extra descriptors."""
    title = re.sub(r'([:\-(]).*$', '', title, flags=re.IGNORECASE)
    return title.strip().lower()