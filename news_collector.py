import feedparser
import requests
import random
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime
import logging
from models import NewsArticle
from config import config
from utils import generate_article_id, clean_text, parse_rss_date
from database import db

logger = logging.getLogger(__name__)

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Android 14; Mobile; rv:109.0) Gecko/121.0 Firefox/121.0',
]


class NewsCollector:
    def __init__(self):
        self.sources = config.RSS_SOURCES
        self.session = requests.Session()
    
    def _get_random_user_agent(self) -> str:
        return random.choice(USER_AGENTS)
    
    def collect_all(self) -> List[NewsArticle]:
        return self.collect_all_parallel()
    
    def collect_all_parallel(self) -> List[NewsArticle]:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import time
        
        all_articles = []
        total = len(self.sources)
        completed = 0
        start_time = time.time()
        
        logger.info(f"🚀 Collection from {total} sources (20 workers)...")
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            future_to_source = {executor.submit(self.collect_from_rss, source): source for source in self.sources}
            
            for future in as_completed(future_to_source):
                source = future_to_source[future]
                completed += 1
                progress = int((completed / total) * 100)
                
                try:
                    articles = future.result(timeout=15)
                    all_articles.extend(articles)
                    if articles:
                        logger.info(f"[{progress}%] ✓ {source['name']}: {len(articles)}")
                except Exception as e:
                    logger.debug(f"[{progress}%] ✗ {source['name']}: {str(e)[:40]}")
        
        elapsed = time.time() - start_time
        logger.info(f"⚡ DONE: {len(all_articles)} articles in {elapsed:.1f}s")
        return all_articles
    
    def collect_from_rss(self, source: Dict) -> List[NewsArticle]:
        articles = []
        try:
            user_agent = self._get_random_user_agent()
            feedparser.USER_AGENT = user_agent
            
            import socket
            original_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(10)
            
            try:
                feed = feedparser.parse(source['url'])
                if not feed.entries:
                    logger.warning(f"No entries found in {source['name']}")
                    return articles
                
                for entry in feed.entries[:config.MAX_ARTICLES_PER_CHECK]:
                    try:
                        article = self._parse_rss_entry(entry, source)
                        if article:
                            articles.append(article)
                    except Exception as e:
                        logger.error(f"Error parsing entry from {source['name']}: {e}")
                        continue
            except socket.timeout:
                logger.warning(f"⏱️ Timeout: {source['name']}")
                return articles
            finally:
                socket.setdefaulttimeout(original_timeout)
        except Exception as e:
            logger.error(f"Error fetching RSS from {source['name']}: {e}")
        return articles
    
    def _parse_rss_entry(self, entry, source: Dict) -> Optional[NewsArticle]:
        try:
            title = clean_text(entry.get('title', ''))
            url = entry.get('link', '')
            
            if not title or not url:
                return None
            
            # Level 1 Dedup: URL
            article_id = generate_article_id(url)
            if db.article_exists(article_id):
                return None
            
            content = ''
            if 'summary' in entry:
                content = clean_text(entry.summary)
            elif 'description' in entry:
                content = clean_text(entry.description)
            
            if content:
                soup = BeautifulSoup(content, 'html.parser')
                content = soup.get_text()
                
            # Level 2 Dedup: Content Hash
            # Using Title + First 200 chars of content for robust deduplication
            from utils import generate_content_hash # delayed import to avoid circular if any
            dedup_text = title + " " + (content[:200] if content else "")
            content_hash = generate_content_hash(dedup_text)
            
            if db.article_hash_exists(content_hash):
                # logger.debug(f"Duplicate content found: {title}")
                return None
            
            published_at = None
            if 'published' in entry:
                published_at = parse_rss_date(entry.published)
            elif 'updated' in entry:
                published_at = parse_rss_date(entry.updated)
            
            article = NewsArticle(
                id=article_id,
                title=title,
                url=url,
                content=content or title,
                source=source['name'],
                category=source['category'],
                published_at=published_at,
                collected_at=datetime.now(),
                content_hash=content_hash
            )
            
            article_dict = article.model_dump()
            article_dict['published_at'] = article_dict['published_at'].isoformat() if article_dict['published_at'] else None
            article_dict['collected_at'] = article_dict['collected_at'].isoformat()
            
            if db.save_article(article_dict):
                return article
            return None
        except Exception as e:
            logger.error(f"Error parsing RSS entry: {e}")
            return None
    
    def add_source(self, name: str, url: str, category: str = "general"):
        new_source = {"name": name, "url": url, "category": category}
        self.sources.append(new_source)
        logger.info(f"Added new source: {name}")
    
    def get_source_count(self) -> int:
        return len(self.sources)


collector = NewsCollector()
