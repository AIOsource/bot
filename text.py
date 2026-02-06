"""Text processing utilities.

# Adapted from other/4/utils.py - clean_text(), truncate_text()
"""
import re
from typing import List
from bs4 import BeautifulSoup


def clean_html(html: str) -> str:
    """
    Remove HTML tags and normalize whitespace.
    
    Args:
        html: Raw HTML content
    
    Returns:
        Clean text without HTML
    """
    if not html:
        return ""
    
    try:
        soup = BeautifulSoup(html, "html.parser")
        
        # Remove script and style elements
        for element in soup(["script", "style", "noscript"]):
            element.decompose()
        
        # Get text with space separator
        text = soup.get_text(separator=" ")
        
        # Normalize whitespace
        text = " ".join(text.split())
        
        # Decode HTML entities
        text = text.replace("&nbsp;", " ")
        text = text.replace("&quot;", '"')
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        
        return text.strip()
    except Exception:
        return html


def truncate_text(text: str, max_length: int = 500) -> str:
    """Truncate text to max length with ellipsis."""
    if not text or len(text) <= max_length:
        return text or ""
    return text[:max_length - 3] + "..."


def extract_sentences(text: str, max_sentences: int = 10) -> str:
    """
    Extract first N sentences from text.
    Used for LLM summarization without external LLM call.
    
    Args:
        text: Full text
        max_sentences: Maximum number of sentences to extract
    
    Returns:
        First N sentences
    """
    if not text:
        return ""
    
    # Split by sentence-ending punctuation
    # Handle Russian and English sentence endings
    sentence_pattern = r'(?<=[.!?])\s+'
    sentences = re.split(sentence_pattern, text)
    
    # Take first N non-empty sentences
    result = []
    for sent in sentences:
        sent = sent.strip()
        if sent and len(sent) > 10:  # Skip very short fragments
            result.append(sent)
            if len(result) >= max_sentences:
                break
    
    return " ".join(result)


def normalize_whitespace(text: str) -> str:
    """Normalize all whitespace to single spaces."""
    if not text:
        return ""
    return " ".join(text.split())


def extract_first_paragraph(text: str, min_length: int = 100) -> str:
    """Extract first meaningful paragraph."""
    if not text:
        return ""
    
    # Split by double newlines or similar paragraph markers
    paragraphs = re.split(r'\n\s*\n|\r\n\s*\r\n', text)
    
    for p in paragraphs:
        p = normalize_whitespace(p)
        if len(p) >= min_length:
            return p
    
    # If no long paragraph, return first 300 chars
    return truncate_text(normalize_whitespace(text), 300)
