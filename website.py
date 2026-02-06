"""Web scraping for full text extraction."""
import asyncio
from typing import Optional, List, Dict, Any
import httpx

from logging_setup import get_logger
from config_loader import SourceConfig

logger = get_logger("sources.website")


# Try trafilatura for content extraction
try:
    import trafilatura
    HAS_TRAFILATURA = True
except ImportError:
    HAS_TRAFILATURA = False
    logger.warning("trafilatura_not_installed", msg="Full text extraction will be limited")


class WebsiteFetcher:
    """Fetch full text from web pages."""
    
    def __init__(self, timeout: int = 15):
        self.timeout = timeout
    
    async def fetch_full_text(self, url: str) -> Optional[str]:
        """
        Fetch and extract full text from a URL.
        
        Args:
            url: Page URL
        
        Returns:
            Extracted text or None
        """
        if not HAS_TRAFILATURA:
            return None
        
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True
            ) as client:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
                    }
                )
                
                if response.status_code != 200:
                    return None
                
                # Extract text with trafilatura (sync operation)
                text = await asyncio.to_thread(
                    trafilatura.extract,
                    response.text,
                    include_comments=False,
                    include_tables=False,
                    no_fallback=False
                )
                
                return text
                
        except Exception as e:
            logger.debug("fetch_full_text_error", url=url[:100], error=str(e))
            return None
    
    async def fetch_news_list(self, source: SourceConfig) -> List[Dict[str, Any]]:
        """
        Scrape news list from a web page (for official sites without RSS).
        
        Note: This is a simplified implementation. Each official site
        may need custom selectors.
        """
        if source.type != "web":
            return []
        
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True
            ) as client:
                response = await client.get(
                    source.url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
                    }
                )
                
                if response.status_code != 200:
                    logger.warning(
                        "fetch_web_error",
                        source=source.name,
                        status_code=response.status_code
                    )
                    return []
                
                # Extract links using trafilatura
                if HAS_TRAFILATURA:
                    from trafilatura import extract_metadata
                    # Get main links - simplified approach
                    # In production, each site needs custom parsing
                    
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(response.text, "html.parser")
                    
                    items = []
                    # Find news links (common patterns)
                    for link in soup.find_all("a", href=True)[:50]:
                        href = link.get("href", "")
                        text = link.get_text(strip=True)
                        
                        # Filter for news-like links
                        if (
                            text and len(text) > 20 and
                            ("/news/" in href or "/press/" in href or "/novosti/" in href)
                        ):
                            # Make absolute URL if relative
                            if href.startswith("/"):
                                from urllib.parse import urlparse
                                parsed = urlparse(source.url)
                                href = f"{parsed.scheme}://{parsed.netloc}{href}"
                            
                            items.append({
                                "source_id": source.id,
                                "source_name": source.name,
                                "url": href,
                                "title": text,
                                "raw_html": "",
                                "published_at": None,
                                "region_hint": source.region_hint,
                            })
                    
                    logger.info("fetch_web_ok", source=source.name, items=len(items))
                    return items[:20]  # Limit to 20 items
                
                return []
                
        except Exception as e:
            logger.error("fetch_web_error", source=source.name, error=str(e))
            return []
