"""SQLAlchemy 2.0 async database models.

# Adapted from other/3/db/models.py - async engine pattern
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, Integer, BigInteger, String, Float, DateTime, 
    Text, Boolean, ForeignKey, Index
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class News(Base):
    """Collected news articles."""
    __tablename__ = "news"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(1000), nullable=False)
    text = Column(Text, nullable=True)
    source = Column(String(100), nullable=False, index=True)
    url = Column(String(2000), nullable=False)
    url_normalized = Column(String(2000), nullable=False, unique=True, index=True)
    published_at = Column(DateTime, nullable=True)
    collected_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    region = Column(String(200), nullable=True)
    filter1_score = Column(Integer, default=0)
    simhash = Column(String(32), nullable=True, index=True)
    # Dedup: if this is a duplicate, points to the canonical news_id
    canonical_news_id = Column(Integer, ForeignKey("news.id"), nullable=True)
    status = Column(String(50), default="raw", index=True)
    # Status values: raw, duplicate, filtered, llm_passed, sent, llm_failed, suppressed_limit
    # llm_json stored as TEXT for SQLite compatibility, parse with json.loads()
    llm_json = Column(Text, nullable=True)
    llm_raw_response = Column(Text, nullable=True)  # Raw LLM output for debugging
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship to signal
    signal = relationship("Signal", back_populates="news", uselist=False)
    
    __table_args__ = (
        Index("ix_news_collected_at", "collected_at"),
        Index("ix_news_status_collected", "status", "collected_at"),
    )


class Signal(Base):
    """Sent Telegram signals."""
    __tablename__ = "signals"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    news_id = Column(Integer, ForeignKey("news.id"), unique=True, nullable=False)
    sent_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    event_type = Column(String(50), nullable=True)
    urgency = Column(Integer, nullable=True)
    object_type = Column(String(50), nullable=True)
    sphere = Column(String(50), nullable=True)  # ЖКХ or промышленность
    region = Column(String(200), nullable=True)
    why = Column(Text, nullable=True)
    message_text = Column(Text, nullable=False)
    recipients_count = Column(Integer, default=0)
    
    # Relationship to news
    news = relationship("News", back_populates="signal")


class Subscriber(Base):
    """Telegram bot subscribers.
    
    NOTE: Per ТЗ, personal data (username, first_name) is NOT stored.
    Only chat_id for delivery, is_active for subscription, timestamps.
    """
    __tablename__ = "subscribers"
    
    chat_id = Column(BigInteger, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True, index=True)
    last_seen_at = Column(DateTime, nullable=True)


class ConfigOverride(Base):
    """Admin configuration overrides stored in DB."""
    __tablename__ = "config_overrides"
    
    key = Column(String(200), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(BigInteger, nullable=True)  # Admin chat_id


class ProcessingLock(Base):
    """Simple locks to prevent duplicate processing."""
    __tablename__ = "processing_locks"
    
    lock_name = Column(String(100), primary_key=True)
    acquired_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    instance_id = Column(String(100), nullable=True)
