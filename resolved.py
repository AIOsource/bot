"""Resolved filter - reject news about already-fixed events.

Pipeline position: after freshness, before noise filter.
"""
from typing import List, Tuple
from dataclasses import dataclass

from logging_setup import get_logger

logger = get_logger("pipeline.resolved")


@dataclass
class ResolvedResult:
    """Result of resolved check."""
    passed: bool
    decision_code: str
    matched_phrases: List[str]
    ongoing_detected: bool


def check_resolved(
    title: str,
    text: str,
    hard_resolved_phrases: List[str],
    soft_resolved_words: List[str],
    allow_if_still_ongoing_words: List[str],
    enabled: bool = True,
    trace_id: str = ""
) -> ResolvedResult:
    """
    Check if news describes an already-resolved event.
    
    Logic:
    1. If hard_resolved_phrases found AND no ongoing indicators → BLOCK
    2. If soft_resolved_words found AND no ongoing indicators → BLOCK
    3. If ongoing indicators present → PASS (event still active)
    
    Args:
        title: Article title
        text: Article text
        hard_resolved_phrases: Exact phrases indicating resolved ("авария устранена")
        soft_resolved_words: Single words indicating resolved ("устранили")
        allow_if_still_ongoing_words: Words indicating event still ongoing ("устраняют", "без воды")
        enabled: Whether filter is enabled
        trace_id: Trace ID for logging
    
    Returns:
        ResolvedResult with passed status, decision code, matched phrases, ongoing flag
    """
    if not enabled:
        return ResolvedResult(
            passed=True,
            decision_code="FILTER_DISABLED",
            matched_phrases=[],
            ongoing_detected=False
        )
    
    combined = f"{title} {text}".lower()
    # Check first 1500 chars for efficiency
    check_text = combined[:1500]
    
    matched_phrases = []
    ongoing_detected = False
    
    # Check for ongoing indicators first
    for word in allow_if_still_ongoing_words:
        if word.lower() in check_text:
            ongoing_detected = True
            break
    
    # Check hard resolved phrases
    for phrase in hard_resolved_phrases:
        if phrase.lower() in check_text:
            matched_phrases.append(phrase)
    
    # Check soft resolved words (only if no hard matches yet)
    if not matched_phrases:
        for word in soft_resolved_words:
            if word.lower() in check_text:
                matched_phrases.append(word)
    
    # Decision logic
    if matched_phrases and not ongoing_detected:
        logger.info(
            "resolved_rejected",
            trace_id=trace_id,
            decision_code="RESOLVED_EVENT",
            matched=matched_phrases[:3],
            ongoing_detected=ongoing_detected
        )
        return ResolvedResult(
            passed=False,
            decision_code="RESOLVED_EVENT",
            matched_phrases=matched_phrases,
            ongoing_detected=False
        )
    
    return ResolvedResult(
        passed=True,
        decision_code="PASSED",
        matched_phrases=matched_phrases,
        ongoing_detected=ongoing_detected
    )
