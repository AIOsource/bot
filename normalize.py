"""Text normalization pipeline step."""
from typing import Dict, Any
from text import clean_html, extract_sentences, normalize_whitespace
from urlnorm import normalize_url
from logging_setup import get_logger

logger = get_logger("pipeline.normalize")


def normalize_news_item(
    item: Dict[str, Any],
    url_params_to_remove: list[str] = None
) -> Dict[str, Any]:
    """
    Normalize a raw news item.
    
    Transforms raw RSS/web item into normalized format for DB.
    
    Args:
        item: Raw item with url, title, raw_html, etc.
        url_params_to_remove: List of URL params to strip
    
    Returns:
        Normalized item ready for DB insertion
    """
    # Normalize URL
    url = item.get("url", "")
    params_set = set(url_params_to_remove) if url_params_to_remove else None
    url_normalized = normalize_url(url, params_set)
    
    # Clean title
    title = item.get("title", "")
    title = normalize_whitespace(title)
    
    # Clean HTML to text
    raw_html = item.get("raw_html", "")
    text = clean_html(raw_html)
    
    # If text is too short, use title
    if len(text) < 50:
        text = title
    
    return {
        "title": title[:1000],  # Limit title length
        "text": text,
        "source": item.get("source_name", "unknown"),
        "url": url,
        "url_normalized": url_normalized,
        "published_at": item.get("published_at"),
        "region": item.get("region_hint"),  # Initial region from source
        "status": "raw",
    }


def prepare_for_llm(
    title: str,
    text: str,
    max_sentences: int = 10,
    max_chars: int = 1500
) -> str:
    """
    Prepare text for LLM input (without using LLM for summarization).
    
    Args:
        title: Article title
        text: Full text
        max_sentences: Max sentences to include
        max_chars: Max total characters
    
    Returns:
        Prepared text for LLM
    """
    # Extract first N sentences
    summary = extract_sentences(text, max_sentences)
    
    # Truncate if still too long
    if len(summary) > max_chars:
        summary = summary[:max_chars - 3] + "..."
    
    return summary
