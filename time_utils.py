"""Time utilities with timezone support.

# Adapted from other/4/utils.py - parse_rss_date()
"""
from datetime import datetime, timezone
from typing import Optional
from email.utils import parsedate_to_datetime
import re


# Common RSS date formats
RSS_DATE_FORMATS = [
    "%a, %d %b %Y %H:%M:%S %z",      # RFC 2822
    "%Y-%m-%dT%H:%M:%S%z",           # ISO 8601 with TZ
    "%Y-%m-%dT%H:%M:%SZ",            # ISO 8601 UTC
    "%Y-%m-%d %H:%M:%S",             # Simple datetime
    "%Y-%m-%d",                       # Date only
    "%d.%m.%Y %H:%M:%S",             # Russian format
    "%d.%m.%Y %H:%M",                # Russian short
    "%d.%m.%Y",                       # Russian date only
]


def parse_rss_date(date_str: str) -> Optional[datetime]:
    """
    Parse various RSS date formats.
    
    Args:
        date_str: Date string from RSS feed
    
    Returns:
        Parsed datetime or None
    """
    if not date_str:
        return None
    
    date_str = date_str.strip()
    
    # Try email.utils first (handles RFC 2822 well)
    try:
        return parsedate_to_datetime(date_str)
    except (ValueError, TypeError):
        pass
    
    # Try common formats
    for fmt in RSS_DATE_FORMATS:
        try:
            dt = datetime.strptime(date_str, fmt)
            # If no timezone, assume UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    
    return None


def utcnow() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


def format_datetime(dt: Optional[datetime], fmt: str = "%Y-%m-%d %H:%M") -> str:
    """Format datetime for display."""
    if not dt:
        return "N/A"
    return dt.strftime(fmt)


def get_timezone(tz_name: str = "Asia/Yekaterinburg"):
    """Get timezone object by name."""
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(tz_name)
    except ImportError:
        # Fallback for Python < 3.9
        return timezone.utc


def to_local(dt: datetime, tz_name: str = "Asia/Yekaterinburg") -> datetime:
    """Convert UTC datetime to local timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    tz = get_timezone(tz_name)
    return dt.astimezone(tz)
