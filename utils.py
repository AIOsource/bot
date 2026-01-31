import logging
import hashlib
from datetime import datetime
from typing import Optional
from config import config


def setup_logging():
    class StructuredFormatter(logging.Formatter):
        COLORS = {
            'PROGRESS': '\033[94m',
            'TELEGRAM': '\033[92m',
            'ERROR': '\033[91m',
            'WARNING': '\033[93m',
            'RESET': '\033[0m'
        }
        
        def format(self, record):
            msg = record.getMessage()
            if '📥' in msg or '📊' in msg or '🤖' in msg or '📤' in msg or '[' in msg and ']' in msg:
                prefix = f"{self.COLORS['PROGRESS']}[PROGRESS]{self.COLORS['RESET']}"
            elif '📱' in msg or 'Telegram' in msg or 'notification' in msg.lower():
                prefix = f"{self.COLORS['TELEGRAM']}[TELEGRAM]{self.COLORS['RESET']}"
            elif record.levelno >= logging.ERROR:
                prefix = f"{self.COLORS['ERROR']}[ERROR]{self.COLORS['RESET']}"
            elif record.levelno >= logging.WARNING:
                prefix = f"{self.COLORS['WARNING']}[WARNING]{self.COLORS['RESET']}"
            else:
                prefix = "[INFO]"
            timestamp = self.formatTime(record, '%H:%M:%S')
            return f"{timestamp} {prefix} {msg}"
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(StructuredFormatter())
    file_handler = logging.FileHandler(config.LOG_FILE, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logging.basicConfig(level=getattr(logging, config.LOG_LEVEL), handlers=[console_handler, file_handler])
    return logging.getLogger(__name__)


def generate_article_id(url: str) -> str:
    return hashlib.md5(url.encode('utf-8')).hexdigest()


def generate_content_hash(text: str) -> str:
    """Generate MD5 hash of the normalized content for deduplication"""
    if not text:
        return ""
    # Normalize: lower case, remove spaces
    normalized = "".join(text.lower().split())[:500] # Hash first 500 chars (approx 100 words) strictly
    return hashlib.md5(normalized.encode('utf-8')).hexdigest()


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = ' '.join(text.split())
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&quot;', '"')
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    return text.strip()


def truncate_text(text: str, max_length: int = 500) -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def format_datetime(dt: Optional[datetime]) -> str:
    if not dt:
        return "N/A"
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def parse_rss_date(date_str: str) -> Optional[datetime]:
    if not date_str:
        return None
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except (ValueError, TypeError):
            continue
    return None


logger = setup_logging()
