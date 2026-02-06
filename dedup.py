"""Two-level deduplication: URL + Simhash.

# Adapted from other/3/core/normalization.py - simhash functions
"""
from typing import Optional, List, Tuple
import re

from logging_setup import get_logger

logger = get_logger("pipeline.dedup")


# Try to import simhash library
try:
    from simhash import Simhash
    HAS_SIMHASH = True
except ImportError:
    HAS_SIMHASH = False
    logger.warning("simhash_not_installed", msg="Using fallback hash")


def compute_simhash(text: str) -> str:
    """
    Compute simhash for text deduplication.
    
    Args:
        text: Text to hash (typically title + first 300-500 chars)
    
    Returns:
        Hex string of simhash value
    """
    if not text:
        return "0"
    
    # Clean text: remove punctuation, lowercase
    clean = re.sub(r'[^\w\s]', '', text.lower())
    words = [w for w in clean.split() if len(w) > 2]
    
    if not words:
        return "0"
    
    if HAS_SIMHASH:
        try:
            sh = Simhash(words)
            return hex(sh.value)[2:]  # Remove '0x' prefix
        except Exception:
            pass
    
    # Fallback: simple hash
    return hex(hash(" ".join(words)) & 0xFFFFFFFFFFFFFFFF)[2:]


def hamming_distance(hash1: str, hash2: str) -> int:
    """
    Calculate Hamming distance between two hex hashes.
    
    Args:
        hash1: First hex hash
        hash2: Second hex hash
    
    Returns:
        Number of differing bits (0-64)
    """
    try:
        v1 = int(hash1, 16) if hash1 else 0
        v2 = int(hash2, 16) if hash2 else 0
        
        # XOR to find different bits
        xor = (v1 ^ v2) & ((1 << 64) - 1)
        
        # Count set bits (Brian Kernighan's algorithm)
        distance = 0
        while xor:
            distance += 1
            xor &= xor - 1
        
        return distance
    except (ValueError, TypeError):
        return 99  # Far apart on error


def is_duplicate_by_simhash(
    new_hash: str,
    existing_hashes: List[Tuple[int, str]],
    threshold: int = 3
) -> Optional[int]:
    """
    Check if new hash is a duplicate of any existing hash.
    
    Args:
        new_hash: Simhash of new article
        existing_hashes: List of (news_id, simhash) tuples
        threshold: Max hamming distance to consider duplicate
    
    Returns:
        news_id of duplicate if found, None otherwise
    """
    if not new_hash or new_hash == "0":
        return None
    
    for news_id, existing_hash in existing_hashes:
        if not existing_hash or existing_hash == "0":
            continue
        
        distance = hamming_distance(new_hash, existing_hash)
        if distance <= threshold:
            logger.debug(
                "simhash_duplicate_found",
                new_hash=new_hash[:16],
                existing_hash=existing_hash[:16],
                distance=distance,
                duplicate_of=news_id
            )
            return news_id
    
    return None


def create_dedup_text(title: str, text: str, max_text_chars: int = 400) -> str:
    """
    Create text for simhash computation.
    
    Args:
        title: Article title
        text: Article text
        max_text_chars: Max chars from text to include
    
    Returns:
        Combined text for hashing
    """
    title = title or ""
    text = text or ""
    
    # Combine title + first N chars of text
    combined = f"{title} {text[:max_text_chars]}"
    return combined.strip()


class Deduplicator:
    """Deduplication service with caching."""
    
    def __init__(self, simhash_threshold: int = 3):
        self.threshold = simhash_threshold
        self._hash_cache: List[Tuple[int, str]] = []
    
    def set_existing_hashes(self, hashes: List[Tuple[int, str]]) -> None:
        """Set existing hashes from DB for comparison."""
        self._hash_cache = hashes
    
    def add_hash(self, news_id: int, simhash: str) -> None:
        """Add new hash to cache."""
        self._hash_cache.append((news_id, simhash))
    
    def check_duplicate(self, title: str, text: str) -> Optional[int]:
        """
        Check if article is duplicate.
        
        Returns:
            news_id of duplicate or None
        """
        dedup_text = create_dedup_text(title, text)
        new_hash = compute_simhash(dedup_text)
        
        return is_duplicate_by_simhash(
            new_hash,
            self._hash_cache,
            self.threshold
        )
    
    def compute_hash(self, title: str, text: str) -> str:
        """Compute simhash for an article."""
        dedup_text = create_dedup_text(title, text)
        return compute_simhash(dedup_text)
