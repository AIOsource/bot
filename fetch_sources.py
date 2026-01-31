import requests
from bs4 import BeautifulSoup
import re
import json
import logging
import feedparser
from urllib.parse import urljoin, urlparse
import time
from typing import Set, List, Dict

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Catalogs to scrape
CATALOG_URLS = [
    "https://subscribe.ru/catalog?rss",
    "https://subscribe.ru/catalog/media?rss",
    # Add more pages/categories if needed
]

# Known good sources to always include (from original config)
DEFAULT_SOURCES = [
    {"name": "Google", "url": "https://news.yandex.ru/housing_and_public_utilities.rss", "category": "aggregator", "region": "Federal"},
    {"name": "Яндекс ЖКХ", "url": "https://news.yandex.ru/housing_and_public_utilities.rss", "category": "aggregator", "region": "Federal"},
    {"name": "Яндекс Происшествия", "url": "https://news.yandex.ru/incident.rss", "category": "aggregator", "region": "Federal"},
    {"name": "РИА Новости", "url": "https://ria.ru/export/rss2/archive/index.xml", "category": "federal", "region": "Federal"},
    {"name": "ТАСС", "url": "https://tass.ru/rss/v2.xml", "category": "federal", "region": "Federal"},
    {"name": "МЧС России", "url": "http://www.mchs.gov.ru/news/rss/", "category": "emergency", "region": "Federal"},
]

def extract_rss_from_subscribe(url: str) -> Set[str]:
    logger.info(f"Scraping {url}...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text("\n")

        rss_urls = set()
        # Look for pattern "Канал сайта: <site> <rss_url>"
        pattern = re.compile(r"Канал сайта:\s*(\S+)\s+(\S+)", re.MULTILINE)

        for match in pattern.finditer(text):
            site_url, rss_url = match.groups()
            if rss_url.startswith("http") and validate_domain(rss_url):
                rss_urls.add(rss_url)
        
        logger.info(f"Found {len(rss_urls)} potential RSS links on {url}")
        return rss_urls
    except Exception as e:
        logger.error(f"Error scraping {url}: {e}")
        return set()

def validate_domain(url: str) -> bool:
    # Filter for RU domain mostly, or common variations
    try:
        domain = urlparse(url).netloc
        if domain.endswith('.ru') or domain.endswith('.su') or domain.endswith('.rf'):
            return True
        return False # Strict filter for now
    except:
        return False

def validate_feed(url: str) -> bool:
    try:
        # Fast check with HEAD or short timeout GET
        # Using feedparser directly is safer
        logger.info(f"Validating {url}...")
        feed = feedparser.parse(url)
        if feed.entries and len(feed.entries) > 0:
            return True
        return False
    except:
        return False

def generate_source_config(rss_urls: Set[str]) -> List[Dict]:
    sources = []
    # Add defaults first
    sources.extend(DEFAULT_SOURCES)
    
    seen_urls = {s['url'] for s in sources}
    
    validated_count = 0
    for url in rss_urls:
        if url in seen_urls:
            continue
            
        if validate_feed(url):
            # Try to extract name from feed or url
            try:
                feed = feedparser.parse(url)
                title = feed.feed.get('title', urlparse(url).netloc)
            except:
                title = urlparse(url).netloc
                
            sources.append({
                "name": title[:50], # Limit name length
                "url": url,
                "category": "regional", # Assume regional/general for scraped
                "region": "Unknown" # Hard to determine automatically without more complex logic
            })
            seen_urls.add(url)
            validated_count += 1
            print(f"✅ Added: {title}")
        else:
            print(f"❌ Invalid/Empty: {url}")
            
    logger.info(f"Total valid sources: {len(sources)}")
    return sources

def main():
    all_rss = set()
    for url in CATALOG_URLS:
        all_rss |= extract_rss_from_subscribe(url)
    
    logger.info(f"Total unique RSS candidates: {len(all_rss)}")
    
    final_config = generate_source_config(all_rss)
    
    # Save to JSON
    with open('sources.json', 'w', encoding='utf-8') as f:
        json.dump(final_config, f, ensure_ascii=False, indent=2)
    
    logger.info("Saved to sources.json")

if __name__ == "__main__":
    main()
