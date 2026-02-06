"""Noise filter - reject death/crime/irrelevant news.

Pipeline position: after resolved filter, before filter1.
"""
from typing import List, Tuple
from dataclasses import dataclass

from logging_setup import get_logger

logger = get_logger("pipeline.noise")


@dataclass
class NoiseResult:
    """Result of noise check."""
    passed: bool
    decision_code: str
    matched_terms: List[str]
    exception_matched: bool


def check_noise(
    title: str,
    text: str,
    hard_negative_topics: List[str],
    domestic_noise: List[str],
    exception_infra_phrases: List[str],
    enabled: bool = True,
    trace_id: str = ""
) -> NoiseResult:
    """
    Check if news is noise (death/crime/domestic issues).
    
    Logic:
    1. Check for hard_negative_topics (death, crime)
    2. Check for domestic noise (apartment, neighbor)
    3. If found, check for infrastructure exceptions (авария на котельной)
    4. If exception found → PASS (legitimate infrastructure event)
    5. If no exception → BLOCK
    
    Args:
        title: Article title
        text: Article text  
        hard_negative_topics: Death/crime keywords
        domestic_noise: Household keywords
        exception_infra_phrases: Infrastructure phrases that override noise
        enabled: Whether filter is enabled
        trace_id: Trace ID for logging
    
    Returns:
        NoiseResult with passed status, decision code, matched terms
    """
    if not enabled:
        return NoiseResult(
            passed=True,
            decision_code="FILTER_DISABLED",
            matched_terms=[],
            exception_matched=False
        )
    
    combined = f"{title} {text}".lower()
    # Check title + first 800 chars of text
    check_text = f"{title.lower()} {text[:800].lower()}"
    
    matched_terms = []
    
    # Check hard negative topics
    for topic in hard_negative_topics:
        if topic.lower() in check_text:
            matched_terms.append(topic)
    
    # Check domestic noise
    for noise in domestic_noise:
        if noise.lower() in check_text:
            matched_terms.append(noise)
    
    if not matched_terms:
        return NoiseResult(
            passed=True,
            decision_code="PASSED",
            matched_terms=[],
            exception_matched=False
        )
    
    # Check for infrastructure exceptions (in full text)
    exception_matched = False
    for phrase in exception_infra_phrases:
        if phrase.lower() in combined:
            exception_matched = True
            break
    
    if exception_matched:
        logger.debug(
            "noise_exception_matched",
            trace_id=trace_id,
            noise_matched=matched_terms[:3],
            decision="pass_with_exception"
        )
        return NoiseResult(
            passed=True,
            decision_code="PASSED_WITH_EXCEPTION",
            matched_terms=matched_terms,
            exception_matched=True
        )
    
    # Block as noise
    logger.info(
        "noise_rejected",
        trace_id=trace_id,
        decision_code="NOISE_HARD_TOPIC",
        matched=matched_terms[:3]
    )
    return NoiseResult(
        passed=False,
        decision_code="NOISE_HARD_TOPIC",
        matched_terms=matched_terms,
        exception_matched=False
    )
