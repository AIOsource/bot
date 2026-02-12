"""Freshness filter - reject old news.

Pipeline position: after normalize, before simhash dedup.
"""
from datetime import datetime, timedelta
from typing import Optional, Tuple
from dataclasses import dataclass

from logging_setup import get_logger

logger = get_logger("pipeline.freshness")


@dataclass
class FreshnessResult:
    """Result of freshness check."""
    passed: bool
    decision_code: str
    age_days: Optional[float] = None


def check_freshness(
    published_at: Optional[datetime],
    collected_at: datetime,
    max_age_days: int = 2,
    allow_missing_published_at: bool = True,
    fallback_to_collected_at: bool = True,
    trace_id: str = ""
) -> FreshnessResult:
    """
    Check if news item is fresh enough to process.
    
    Args:
        published_at: When the article was published (may be None)
        collected_at: When we collected the article
        max_age_days: Maximum age in days
        allow_missing_published_at: Allow items without published_at
        fallback_to_collected_at: Use collected_at if published_at missing
        trace_id: Trace ID for logging
    
    Returns:
        FreshnessResult with passed status and decision code
    
    Decision codes:
        - PASSED: Fresh enough
        - STALE_NEWS: Too old
        - MISSING_PUBLISHED_AT: No date and not allowed
    """
    now = datetime.utcnow()
    max_age = timedelta(days=max_age_days)
    
    # Determine which date to use
    check_date: Optional[datetime] = None
    
    if published_at:
        check_date = published_at
    elif allow_missing_published_at and fallback_to_collected_at:
        check_date = collected_at
    elif not allow_missing_published_at:
        logger.info(
            "freshness_rejected",
            trace_id=trace_id,
            decision_code="MISSING_PUBLISHED_AT",
            reason="no_published_at"
        )
        return FreshnessResult(
            passed=False,
            decision_code="MISSING_PUBLISHED_AT",
            age_days=None
        )
    
    if check_date is None:
        # Fallback: assume it's fresh if we can't determine
        return FreshnessResult(passed=True, decision_code="PASSED", age_days=0)
    
    # Calculate age — strip timezone to avoid naive/aware mismatch
    # RSS feeds return tz-aware dates, but we use naive UTC internally
    if check_date.tzinfo is not None:
        check_date = check_date.replace(tzinfo=None)
    age = now - check_date
    age_days = age.total_seconds() / 86400
    
    if age > max_age:
        logger.info(
            "freshness_rejected",
            trace_id=trace_id,
            decision_code="STALE_NEWS",
            age_days=round(age_days, 1),
            max_age_days=max_age_days
        )
        return FreshnessResult(
            passed=False,
            decision_code="STALE_NEWS",
            age_days=age_days
        )
    
    return FreshnessResult(
        passed=True,
        decision_code="PASSED",
        age_days=age_days
    )
