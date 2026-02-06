"""Database repository with all CRUD operations."""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from models import News, Signal, Subscriber, ConfigOverride, ProcessingLock
from engine import get_session


class NewsRepository:
    """Repository for news operations."""
    
    @staticmethod
    async def url_exists(session: AsyncSession, url_normalized: str) -> bool:
        """Check if normalized URL already exists."""
        result = await session.execute(
            select(News.id).where(News.url_normalized == url_normalized).limit(1)
        )
        return result.scalar() is not None
    
    @staticmethod
    async def simhash_exists(session: AsyncSession, simhash: str, threshold: int = 3) -> Optional[int]:
        """Check if similar simhash exists. Returns news_id if found."""
        # For exact match first (most common case)
        result = await session.execute(
            select(News.id).where(News.simhash == simhash).limit(1)
        )
        existing = result.scalar()
        if existing:
            return existing
        
        # Note: Real hamming distance check would require loading recent hashes
        # For SQLite, we do this in Python - see pipeline/dedup.py
        return None
    
    @staticmethod
    async def get_recent_simhashes(
        session: AsyncSession, 
        hours: int = 72
    ) -> List[tuple[int, str]]:
        """Get recent simhashes for dedup checking."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        result = await session.execute(
            select(News.id, News.simhash)
            .where(and_(
                News.simhash.isnot(None),
                News.collected_at >= cutoff
            ))
        )
        return result.all()
    
    @staticmethod
    async def create(session: AsyncSession, news_data: Dict[str, Any]) -> News:
        """Create a new news record."""
        news = News(**news_data)
        session.add(news)
        await session.flush()
        return news
    
    @staticmethod
    async def update_status(
        session: AsyncSession, 
        news_id: int, 
        status: str,
        llm_json: Optional[str] = None,  # Stored as TEXT per ТЗ
        llm_raw_response: Optional[str] = None,  # Raw LLM output for debugging
        filter1_score: Optional[int] = None
    ) -> None:
        """Update news status and optional fields."""
        values = {"status": status}
        if llm_json is not None:
            values["llm_json"] = llm_json
        if llm_raw_response is not None:
            values["llm_raw_response"] = llm_raw_response
        if filter1_score is not None:
            values["filter1_score"] = filter1_score
        
        await session.execute(
            update(News).where(News.id == news_id).values(**values)
        )
    
    @staticmethod
    async def get_by_id(session: AsyncSession, news_id: int) -> Optional[News]:
        """Get news by ID."""
        result = await session.execute(
            select(News).where(News.id == news_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_unprocessed(session: AsyncSession, limit: int = 100) -> List[News]:
        """Get unprocessed news items."""
        result = await session.execute(
            select(News)
            .where(News.status == "raw")
            .order_by(News.collected_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    @staticmethod
    async def get_stats(session: AsyncSession, days: int = 1) -> Dict[str, int]:
        """Get news statistics for the last N days."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        # Total collected
        total = await session.execute(
            select(func.count(News.id)).where(News.collected_at >= cutoff)
        )
        
        # By status
        by_status = await session.execute(
            select(News.status, func.count(News.id))
            .where(News.collected_at >= cutoff)
            .group_by(News.status)
        )
        
        stats = {"total": total.scalar() or 0}
        for status, count in by_status.all():
            stats[f"status_{status}"] = count
        
        return stats


class SignalRepository:
    """Repository for signal operations."""
    
    @staticmethod
    async def create(session: AsyncSession, signal_data: Dict[str, Any]) -> Signal:
        """Create a new signal record."""
        signal = Signal(**signal_data)
        session.add(signal)
        await session.flush()
        return signal
    
    @staticmethod
    async def count_today(session: AsyncSession, timezone_str: str = "UTC") -> int:
        """Count signals sent today (timezone-aware)."""
        import pytz
        tz = pytz.timezone(timezone_str)
        now = datetime.now(tz)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        # Convert to UTC for DB query
        today_start_utc = today_start.astimezone(pytz.UTC).replace(tzinfo=None)
        
        result = await session.execute(
            select(func.count(Signal.id)).where(Signal.sent_at >= today_start_utc)
        )
        return result.scalar() or 0
    
    @staticmethod
    async def try_create_if_under_limit(
        session: AsyncSession,
        signal_data: Dict[str, Any],
        max_per_day: int = 5,
        timezone_str: str = "UTC"
    ) -> Optional[Signal]:
        """
        Atomically create signal only if under daily limit.
        
        Uses APP_TIMEZONE for day boundary (not UTC).
        Returns Signal if created, None if limit reached.
        """
        import pytz
        tz = pytz.timezone(timezone_str)
        now = datetime.now(tz)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_start_utc = today_start.astimezone(pytz.UTC).replace(tzinfo=None)
        
        # Atomic count + insert in same transaction
        count_result = await session.execute(
            select(func.count(Signal.id)).where(Signal.sent_at >= today_start_utc)
        )
        current_count = count_result.scalar() or 0
        
        if current_count >= max_per_day:
            return None
        
        # Create signal
        signal = Signal(**signal_data)
        session.add(signal)
        await session.flush()
        return signal
    
    @staticmethod
    async def get_recent(session: AsyncSession, days: int = 7) -> List[Signal]:
        """Get signals from last N days."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        result = await session.execute(
            select(Signal)
            .where(Signal.sent_at >= cutoff)
            .order_by(Signal.sent_at.desc())
        )
        return result.scalars().all()


class SubscriberRepository:
    """Repository for subscriber operations.
    
    NOTE: Per ТЗ, we do NOT store personal data (username, first_name).
    """
    
    @staticmethod
    async def get_or_create(
        session: AsyncSession,
        chat_id: int
    ) -> tuple[Subscriber, bool]:
        """Get existing or create new subscriber. Returns (subscriber, created).
        
        Handles race condition when multiple /start commands arrive simultaneously.
        """
        from sqlalchemy.exc import IntegrityError
        
        # First try to find existing
        result = await session.execute(
            select(Subscriber).where(Subscriber.chat_id == chat_id)
        )
        subscriber = result.scalar_one_or_none()
        
        if subscriber:
            # Update last seen only
            subscriber.last_seen_at = datetime.utcnow()
            return subscriber, False
        
        # Try to create new - no personal data stored
        try:
            subscriber = Subscriber(
                chat_id=chat_id,
                is_active=True,
                last_seen_at=datetime.utcnow()
            )
            session.add(subscriber)
            await session.flush()
            return subscriber, True
        except IntegrityError:
            # Race condition - another request already created it
            await session.rollback()
            result = await session.execute(
                select(Subscriber).where(Subscriber.chat_id == chat_id)
            )
            subscriber = result.scalar_one_or_none()
            if subscriber:
                subscriber.last_seen_at = datetime.utcnow()
                return subscriber, False
            raise  # Should not happen
    
    @staticmethod
    async def set_active(session: AsyncSession, chat_id: int, is_active: bool) -> None:
        """Set subscriber active status."""
        await session.execute(
            update(Subscriber)
            .where(Subscriber.chat_id == chat_id)
            .values(is_active=is_active, last_seen_at=datetime.utcnow())
        )
    
    @staticmethod
    async def get_active(session: AsyncSession) -> List[Subscriber]:
        """Get all active subscribers."""
        result = await session.execute(
            select(Subscriber).where(Subscriber.is_active == True)
        )
        return result.scalars().all()
    
    @staticmethod
    async def count_active(session: AsyncSession) -> int:
        """Count active subscribers."""
        result = await session.execute(
            select(func.count(Subscriber.chat_id)).where(Subscriber.is_active == True)
        )
        return result.scalar() or 0


class ConfigRepository:
    """Repository for config override operations."""
    
    @staticmethod
    async def get_all(session: AsyncSession) -> Dict[str, str]:
        """Get all config overrides as dict."""
        result = await session.execute(select(ConfigOverride))
        return {co.key: co.value for co in result.scalars().all()}
    
    @staticmethod
    async def set(
        session: AsyncSession,
        key: str,
        value: str,
        updated_by: int
    ) -> None:
        """Set a config override."""
        existing = await session.execute(
            select(ConfigOverride).where(ConfigOverride.key == key)
        )
        override = existing.scalar_one_or_none()
        
        if override:
            override.value = value
            override.updated_by = updated_by
            override.updated_at = datetime.utcnow()
        else:
            session.add(ConfigOverride(
                key=key,
                value=value,
                updated_by=updated_by
            ))
    
    @staticmethod
    async def delete(session: AsyncSession, key: str) -> bool:
        """Delete a config override."""
        result = await session.execute(
            delete(ConfigOverride).where(ConfigOverride.key == key)
        )
        return result.rowcount > 0


class LockRepository:
    """Repository for processing lock operations."""
    
    @staticmethod
    async def acquire(
        session: AsyncSession,
        lock_name: str,
        duration_seconds: int = 300,
        instance_id: Optional[str] = None
    ) -> bool:
        """Try to acquire a lock. Returns True if acquired."""
        now = datetime.utcnow()
        
        # Check existing lock
        result = await session.execute(
            select(ProcessingLock).where(ProcessingLock.lock_name == lock_name)
        )
        lock = result.scalar_one_or_none()
        
        if lock:
            if lock.expires_at > now:
                # Lock still valid
                return False
            # Lock expired, update it
            lock.acquired_at = now
            lock.expires_at = now + timedelta(seconds=duration_seconds)
            lock.instance_id = instance_id
        else:
            # Create new lock
            session.add(ProcessingLock(
                lock_name=lock_name,
                acquired_at=now,
                expires_at=now + timedelta(seconds=duration_seconds),
                instance_id=instance_id
            ))
        
        await session.flush()
        return True
    
    @staticmethod
    async def release(session: AsyncSession, lock_name: str) -> None:
        """Release a lock."""
        await session.execute(
            delete(ProcessingLock).where(ProcessingLock.lock_name == lock_name)
        )
