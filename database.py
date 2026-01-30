import sqlite3
from datetime import datetime
from typing import Optional, List
from contextlib import contextmanager
from config import config
import logging

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DB_PATH
        self._init_db()
    
    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()
    
    def _init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS articles (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    content TEXT,
                    source TEXT,
                    category TEXT,
                    published_at TEXT,
                    collected_at TEXT NOT NULL,
                    processed BOOLEAN DEFAULT 0
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS filtered_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article_id TEXT NOT NULL,
                    relevance_score REAL NOT NULL,
                    key_points TEXT,
                    reasoning TEXT,
                    filtered_at TEXT NOT NULL,
                    FOREIGN KEY (article_id) REFERENCES articles (id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sent_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    url TEXT NOT NULL,
                    priority TEXT,
                    sent_at TEXT NOT NULL,
                    FOREIGN KEY (event_id) REFERENCES filtered_events (id)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_processed ON articles(processed)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_collected ON articles(collected_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_score ON filtered_events(relevance_score)")
            # Таблица для авторизованных пользователей (персистентная авторизация)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS authenticated_users (
                    user_id INTEGER PRIMARY KEY,
                    first_name TEXT,
                    authenticated_at TEXT NOT NULL
                )
            """)
            logger.info("Database initialized successfully")
    
    def article_exists(self, article_id: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM articles WHERE id = ?", (article_id,))
            return cursor.fetchone() is not None
    
    def save_article(self, article: dict) -> bool:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO articles (id, title, url, content, source, category, published_at, collected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    article['id'], article['title'], article['url'], article['content'],
                    article['source'], article['category'], article.get('published_at'), article['collected_at']
                ))
                return True
        except sqlite3.IntegrityError:
            logger.debug(f"Article already exists: {article['url']}")
            return False
    
    def get_unprocessed_articles(self, limit: int = 100) -> List[dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM articles WHERE processed = 0 ORDER BY collected_at DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def mark_article_processed(self, article_id: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE articles SET processed = 1 WHERE id = ?", (article_id,))
    
    def save_filtered_event(self, event: dict) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO filtered_events (article_id, relevance_score, key_points, reasoning, filtered_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                event['article_id'], event['relevance_score'],
                '|'.join(event.get('key_points', [])), event['reasoning'], event['filtered_at']
            ))
            return cursor.lastrowid
    
    def save_sent_signal(self, signal: dict):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sent_signals (event_id, title, message, url, priority, sent_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                signal['event_id'], signal['title'], signal['message'],
                signal['url'], signal['priority'], signal['sent_at']
            ))
    
    def get_stats(self) -> dict:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM articles")
            total_articles = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM articles WHERE processed = 1")
            processed_articles = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM filtered_events")
            total_events = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM sent_signals")
            total_signals = cursor.fetchone()[0]
            return {
                'total_articles': total_articles,
                'processed_articles': processed_articles,
                'unprocessed_articles': total_articles - processed_articles,
                'filtered_events': total_events,
                'sent_signals': total_signals
            }


db = Database()
