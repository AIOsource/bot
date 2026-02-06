"""URL normalization utilities.

# Adapted from other/3/core/normalization.py - clean_url()
"""
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from typing import Set


# Default tracking parameters to remove
DEFAULT_PARAMS_TO_REMOVE: Set[str] = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "yclid", "gclid", "fbclid", "ref", "from", "source", "rss", "tg",
    "share", "partner", "erid", "ysclid", "rs", "_openstat"
}


def normalize_url(url: str, params_to_remove: Set[str] = None) -> str:
    """
    Normalize URL by removing tracking parameters.
    
    Args:
        url: Original URL
        params_to_remove: Set of query param names to remove (case-insensitive)
    
    Returns:
        Normalized URL without tracking params and fragment
    """
    if not url:
        return ""
    
    params_to_remove = params_to_remove or DEFAULT_PARAMS_TO_REMOVE
    params_lower = {p.lower() for p in params_to_remove}
    
    try:
        parsed = urlparse(url)
        
        # Parse query string
        query_params = parse_qs(parsed.query, keep_blank_values=False)
        
        # Filter out tracking params (case-insensitive)
        filtered_params = {
            k: v for k, v in query_params.items()
            if k.lower() not in params_lower
        }
        
        # Rebuild query string (sorted for consistency)
        new_query = urlencode(filtered_params, doseq=True) if filtered_params else ""
        
        # Rebuild URL without fragment
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc.lower(),  # Lowercase domain
            parsed.path.rstrip("/") if parsed.path != "/" else parsed.path,
            parsed.params,
            new_query,
            ""  # Remove fragment
        ))
        
        return normalized
    except Exception:
        # Return original if parsing fails
        return url


def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower()
    except Exception:
        return ""


def is_valid_url(url: str) -> bool:
    """Check if URL is valid."""
    if not url:
        return False
    try:
        parsed = urlparse(url)
        return bool(parsed.scheme and parsed.netloc)
    except Exception:
        return False
