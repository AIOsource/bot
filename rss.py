"""RSS and web source fetchers.

# Adapted from other/3/core/filters.py - Collector class
# Adapted from other/4/news_collector.py - feedparser pattern
"""
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus
import httpx
import feedparser
from tenacity import retry, stop_after_attempt, wait_exponential

from logging_setup import get_logger
from config_loader import SourceConfig
from time_utils import parse_rss_date, utcnow

logger = get_logger("sources.rss")


# User agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "PRSBOT/1.0 (News Aggregator)",
]


def get_user_agent(index: int = 0) -> str:
    """Get user agent by index (rotating)."""
    return USER_AGENTS[index % len(USER_AGENTS)]


class RSSFetcher:
    """Async RSS feed fetcher."""
    
    def __init__(self, timeout: int = 15, retries: int = 3):
        self.timeout = timeout
        self.retries = retries
    
    async def fetch(self, source: SourceConfig) -> List[Dict[str, Any]]:
        """
        Fetch items from a source (RSS, web, or Google News).
        
        Returns list of raw items with: source_id, source_name, url, title, 
        raw_html, published_at, region_hint
        """
        if source.type == "google_news_rss":
            return await self._fetch_google_news(source)
        elif source.type == "web":
            # Web scraping handled separately
            return []
        else:
            return await self._fetch_rss(source)
    
    async def _fetch_rss(self, source: SourceConfig) -> List[Dict[str, Any]]:
        """Fetch standard RSS feed."""
        items = []
        start_time = datetime.now()
        
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True
            ) as client:
                response = await client.get(
                    source.url,
                    headers={
                        "User-Agent": get_user_agent(hash(source.id) % len(USER_AGENTS)),
                        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                        "Accept": "application/rss+xml, application/xml, text/xml, */*"
                    }
                )
                
                if response.status_code != 200:
                    logger.warning(
                        "fetch_rss_error",
                        source=source.name,
                        status_code=response.status_code
                    )
                    return []
                
                # Parse feed
                feed = feedparser.parse(response.text)
                
                if not feed.entries:
                    logger.debug("fetch_rss_empty", source=source.name)
                    return []
                
                for entry in feed.entries:
                    item = self._parse_entry(entry, source)
                    if item:
                        items.append(item)
                
                duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                logger.info(
                    "fetch_rss_ok",
                    source=source.name,
                    items=len(items),
                    duration_ms=duration_ms
                )
                
        except httpx.TimeoutException:
            logger.warning("fetch_rss_timeout", source=source.name)
        except Exception as e:
            logger.error("fetch_rss_error", source=source.name, error=str(e))
        
        return items
    
    async def _fetch_google_news(self, source: SourceConfig) -> List[Dict[str, Any]]:
        """Fetch Google News RSS by query."""
        if not source.query:
            return []
        
        # Build Google News RSS URL
        encoded_query = quote_plus(source.query)
        url = (
            f"https://news.google.com/rss/search?"
            f"q={encoded_query}&hl={source.hl}&gl={source.gl}&ceid={source.ceid}"
        )
        
        # Create temporary source with URL
        temp_source = SourceConfig(
            id=source.id,
            type="rss",
            name=source.name,
            url=url,
            region_hint=source.region_hint
        )
        
        return await self._fetch_rss(temp_source)
    
    def _parse_entry(self, entry, source: SourceConfig) -> Optional[Dict[str, Any]]:
        """Parse RSS entry to standard format."""
        try:
            url = getattr(entry, "link", None)
            title = getattr(entry, "title", None)
            
            if not url or not title:
                return None
            
            # Get content/summary
            raw_html = ""
            if hasattr(entry, "summary"):
                raw_html = entry.summary
            elif hasattr(entry, "description"):
                raw_html = entry.description
            elif hasattr(entry, "content") and entry.content:
                raw_html = entry.content[0].get("value", "")
            
            # Parse date
            published_at = None
            if hasattr(entry, "published"):
                published_at = parse_rss_date(entry.published)
            elif hasattr(entry, "updated"):
                published_at = parse_rss_date(entry.updated)
            
            return {
                "source_id": source.id,
                "source_name": source.name,
                "url": url,
                "title": title.strip() if title else "",
                "raw_html": raw_html,
                "published_at": published_at,
                "region_hint": source.region_hint,
            }
        except Exception as e:
            logger.debug("parse_entry_error", error=str(e))
            return None
    
    async def fetch_all(
        self, 
        sources: List[SourceConfig],
        max_concurrent: int = 20
    ) -> List[Dict[str, Any]]:
        """Fetch all sources concurrently with limit."""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def fetch_with_semaphore(source: SourceConfig):
            async with semaphore:
                return await self.fetch(source)
        
        start_time = datetime.now()
        results = await asyncio.gather(
            *[fetch_with_semaphore(s) for s in sources],
            return_exceptions=True
        )
        
        # Flatten results, skip errors
        all_items = []
        for result in results:
            if isinstance(result, list):
                all_items.extend(result)
            elif isinstance(result, Exception):
                logger.error("fetch_all_error", error=str(result))
        
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        logger.info(
            "fetch_all_complete",
            sources=len(sources),
            items=len(all_items),
            duration_ms=duration_ms
        )
        
        return all_items
