"""Shared query-time ranking and bounded shortlist policy; no index changes."""

DEFAULT_MODE = "combined"
MAX_LIMIT = 40
RRF_K = 60
RRF_WEIGHTS = {
    "combined": {"image": 3, "keyword": 1, "description": 1},
    "keyword_description": {"keyword": 1, "description": 1},
}


def search_character_cap(limit):
    """6,000 for compact requests; 2,000 overhead + 1,000 per candidate."""
    return 6000 if limit <= 5 else 2000 + 1000 * limit
