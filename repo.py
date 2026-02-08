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
    async def get_stats(session: AsyncSession, days: int = 1) -> Dict[str, Any]:
        """Get comprehensive news statistics for the last N days."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        # Total collected
        total = await session.execute(
            select(func.count(News.id)).where(News.collected_at >= cutoff)
        )
        
        # By status - detailed breakdown
        by_status = await session.execute(
            select(News.status, func.count(News.id))
            .where(News.collected_at >= cutoff)
            .group_by(News.status)
        )
        
        stats = {
            "total": total.scalar() or 0,
            "by_status": {},
            "by_decision": {}
        }
        
        for status, count in by_status.all():
            stats["by_status"][status or "unknown"] = count
        
        # Top decision codes (for filtered items)
        # Note: decision_code is stored in llm_raw_response for filtered items
        # For simplicity, count status types as decision indicators
        filtered_statuses = [
            "filtered", "filtered_old", "filtered_resolved", 
            "filtered_noise", "duplicate", "llm_failed", 
            "llm_skipped", "suppressed_limit"
        ]
        
        for status in filtered_statuses:
            stats["by_decision"][status] = stats["by_status"].get(status, 0)
        
        # Sent signals count
        stats["sent"] = stats["by_status"].get("sent", 0)
        
        return stats
    
    @staticmethod
    async def cleanup_old_news(session: AsyncSession, days: int = 30) -> int:
        """Delete raw news older than N days (DB retention).
        
        Only deletes news with status='raw' or 'filtered' that haven't
        been processed into signals.
        
        Returns:
            Number of deleted records
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        # Don't delete news that became signals
        result = await session.execute(
            delete(News).where(
                News.collected_at < cutoff,
                News.status.in_(["raw", "filtered", "duplicate", "filtered_old", 
                                "filtered_resolved", "filtered_noise", "llm_failed", 
                                "llm_skipped"])
            ).returning(News.id)
        )
        
        deleted_ids = result.fetchall()
        return len(deleted_ids)
    
    @staticmethod
    async def vacuum_db(session: AsyncSession) -> None:
        """Run VACUUM on SQLite database (call outside transaction)."""
        # Note: VACUUM must be run outside of a transaction
        # This is a placeholder - actual VACUUM requires raw connection
        pass


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
    
    @staticmethod
    async def set_feedback(session: AsyncSession, signal_id: int, score: int, comment: str = None) -> None:
        """Set feedback score for a signal."""
        await session.execute(
            update(Signal)
            .where(Signal.id == signal_id)
            .values(feedback_score=score, feedback_comment=comment)
        )
    
    @staticmethod
    async def find_similar_recent(
        session: AsyncSession,
        event_type: str,
        region: str,
        object_type: Optional[str],
        hours: int = 24
    ) -> Optional[Signal]:
        """Find similar signal sent recently."""
        if not event_type:
            return None
            
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        # Build query
        conditions = [
            Signal.sent_at >= cutoff,
            Signal.event_type == event_type
        ]
        
        if region:
            conditions.append(Signal.region == region)
        if object_type:
            conditions.append(Signal.object_type == object_type)
            
        result = await session.execute(
            select(Signal)
            .where(and_(*conditions))
            .order_by(Signal.sent_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


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
        updated_by: int,
        source: str = "ui"
    ) -> None:
        """Set a config override and log audit."""
        from models import ConfigAudit
        
        # Get old value
        existing = await session.execute(
            select(ConfigOverride).where(ConfigOverride.key == key)
        )
        override = existing.scalar_one_or_none()
        old_value = override.value if override else None
        
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
            
        # Log audit
        if old_value != value:
            session.add(ConfigAudit(
                user_id=updated_by,
                action="set",
                key=key,
                old_value=old_value,
                new_value=value,
                source=source
            ))

    @staticmethod
    async def log_audit(
        session: AsyncSession,
        user_id: int,
        action: str,
        key: str,
        old_value: Optional[str],
        new_value: Optional[str],
        source: str = "ui"
    ) -> None:
        """Manually log an audit entry (e.g. for imports)."""
        from models import ConfigAudit
        session.add(ConfigAudit(
            user_id=user_id,
            action=action,
            key=key,
            old_value=old_value,
            new_value=new_value,
            source=source
        ))

    @staticmethod
    async def get_history(
        session: AsyncSession, 
        limit: int = 20, 
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get audit history."""
        from models import ConfigAudit
        result = await session.execute(
            select(ConfigAudit)
            .order_by(ConfigAudit.timestamp.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    @staticmethod
    async def count_history(session: AsyncSession) -> int:
        """Count total audit entries."""
        from models import ConfigAudit
        result = await session.execute(select(func.count(ConfigAudit.id)))
        return result.scalar() or 0

    @staticmethod
    async def delete(session: AsyncSession, key: str, user_id: int = 0) -> bool:
        """Delete a config override."""
        # Get old value for audit
        existing = await session.execute(
            select(ConfigOverride).where(ConfigOverride.key == key)
        )
        override = existing.scalar_one_or_none()
        
        if override:
            # Audit log
            from models import ConfigAudit
            session.add(ConfigAudit(
                user_id=user_id,
                action="delete",
                key=key,
                old_value=override.value,
                new_value=None,
                source="ui"
            ))
            
            await session.delete(override)
            return True
        return False


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


class SourceHealthRepository:
    """Repository for source health monitoring."""
    
    AUTO_DISABLE_THRESHOLD = 10  # Disable after N consecutive failures
    
    @staticmethod
    async def record_success(session: AsyncSession, source_id: str) -> None:
        """Record successful fetch."""
        from models import SourceHealth
        
        result = await session.execute(
            select(SourceHealth).where(SourceHealth.source_id == source_id)
        )
        health = result.scalar_one_or_none()
        
        now = datetime.utcnow()
        if health:
            health.consecutive_failures = 0
            health.total_fetches += 1
            health.last_ok_at = now
        else:
            session.add(SourceHealth(
                source_id=source_id,
                consecutive_failures=0,
                total_fetches=1,
                last_ok_at=now
            ))
    
    @staticmethod
    async def record_failure(
        session: AsyncSession, 
        source_id: str,
        status_code: int = None,
        error_message: str = None
    ) -> bool:
        """Record failed fetch. Returns True if source should be disabled."""
        from models import SourceHealth
        
        result = await session.execute(
            select(SourceHealth).where(SourceHealth.source_id == source_id)
        )
        health = result.scalar_one_or_none()
        
        now = datetime.utcnow()
        if health:
            health.consecutive_failures += 1
            health.total_failures += 1
            health.total_fetches += 1
            health.last_error_at = now
            health.last_status_code = status_code
            health.last_error_message = (error_message or "")[:500]
            
            # Auto-disable check
            if health.consecutive_failures >= SourceHealthRepository.AUTO_DISABLE_THRESHOLD:
                health.is_disabled = True
                health.disabled_at = now
                health.disabled_reason = f"Auto-disabled after {health.consecutive_failures} consecutive failures"
                return True
        else:
            session.add(SourceHealth(
                source_id=source_id,
                consecutive_failures=1,
                total_fetches=1,
                total_failures=1,
                last_error_at=now,
                last_status_code=status_code,
                last_error_message=(error_message or "")[:500]
            ))
        
        return False
    
    @staticmethod
    async def is_disabled(session: AsyncSession, source_id: str) -> bool:
        """Check if source is disabled."""
        from models import SourceHealth
        
        result = await session.execute(
            select(SourceHealth.is_disabled).where(SourceHealth.source_id == source_id)
        )
        is_disabled = result.scalar()
        return is_disabled or False
    
    @staticmethod
    async def enable_source(session: AsyncSession, source_id: str) -> None:
        """Re-enable a disabled source."""
        from models import SourceHealth
        
        await session.execute(
            update(SourceHealth)
            .where(SourceHealth.source_id == source_id)
            .values(is_disabled=False, consecutive_failures=0, disabled_at=None, disabled_reason=None)
        )
    
    @staticmethod
    async def get_health_summary(session: AsyncSession) -> List[Dict[str, Any]]:
        """Get health summary for all sources."""
        from models import SourceHealth
        
        result = await session.execute(
            select(SourceHealth).order_by(SourceHealth.consecutive_failures.desc())
        )
        
        return [
            {
                "source_id": h.source_id,
                "consecutive_failures": h.consecutive_failures,
                "is_disabled": h.is_disabled,
                "last_ok_at": h.last_ok_at,
                "last_status_code": h.last_status_code
            }
            for h in result.scalars().all()
        ]


class PendingSignalRepository:
    """Repository for managing pending signal candidates."""
    
    @staticmethod
    def calculate_priority_score(
        urgency: int,
        relevance: float,
        filter1_score: int,
        urgency_weight: float = 0.4,
        relevance_weight: float = 0.4,
        filter1_weight: float = 0.2,
        filter1_max: int = 100
    ) -> float:
        """Calculate priority score for ranking candidates.
        
        Formula: urgency_weighted + relevance_weighted + filter1_weighted
        All components normalized to 0-1 range.
        """
        urgency_norm = (urgency - 1) / 4.0  # 1-5 -> 0-1
        filter1_norm = min(filter1_score / filter1_max, 1.0)  # cap at max
        
        return (
            urgency_norm * urgency_weight +
            relevance * relevance_weight +
            filter1_norm * filter1_weight
        )
    
    @staticmethod
    async def add_candidate(
        session: AsyncSession,
        news_id: int,
        urgency: int,
        relevance: float,
        filter1_score: int,
        event_type: str,
        object_type: str,
        message_text: str,
        region: str,
        why: str,
        cycle_date: str,
        priority_config: Dict[str, float] = None
    ) -> None:
        """Add a candidate to pending signals."""
        from models import PendingSignal
        
        cfg = priority_config or {}
        priority_score = PendingSignalRepository.calculate_priority_score(
            urgency=urgency,
            relevance=relevance,
            filter1_score=filter1_score,
            urgency_weight=cfg.get("urgency_weight", 0.4),
            relevance_weight=cfg.get("relevance_weight", 0.4),
            filter1_weight=cfg.get("filter1_weight", 0.2)
        )
        
        session.add(PendingSignal(
            news_id=news_id,
            priority_score=priority_score,
            relevance=relevance,
            urgency=urgency,
            event_type=event_type,
            object_type=object_type,
            message_text=message_text,
            region=region,
            why=why,
            cycle_date=cycle_date,
            status="pending"
        ))
    
    @staticmethod
    async def get_top_candidates(
        session: AsyncSession,
        cycle_date: str,
        limit: int = 5
    ) -> List[Any]:
        """Get top N candidates by priority_score for the cycle."""
        from models import PendingSignal
        
        result = await session.execute(
            select(PendingSignal)
            .where(PendingSignal.cycle_date == cycle_date)
            .where(PendingSignal.status == "pending")
            .order_by(PendingSignal.priority_score.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    @staticmethod
    async def mark_sent(session: AsyncSession, pending_id: int) -> None:
        """Mark a pending signal as sent."""
        from models import PendingSignal
        
        await session.execute(
            update(PendingSignal)
            .where(PendingSignal.id == pending_id)
            .values(status="sent")
        )
    
    @staticmethod
    async def mark_skipped(session: AsyncSession, cycle_date: str) -> None:
        """Mark all remaining pending signals as skipped (not in top-N)."""
        from models import PendingSignal
        
        await session.execute(
            update(PendingSignal)
            .where(PendingSignal.cycle_date == cycle_date)
            .where(PendingSignal.status == "pending")
            .values(status="skipped")
        )
    
    @staticmethod
    async def count_pending(session: AsyncSession, cycle_date: str) -> int:
        """Count pending candidates for the cycle."""
        from models import PendingSignal
        
        result = await session.execute(
            select(func.count(PendingSignal.id))
            .where(PendingSignal.cycle_date == cycle_date)
            .where(PendingSignal.status == "pending")
        )
    @staticmethod
    async def count_pending(session: AsyncSession, cycle_date: str) -> int:
        """Count pending candidates for the cycle."""
        from models import PendingSignal
        
        result = await session.execute(
            select(func.count(PendingSignal.id))
            .where(PendingSignal.cycle_date == cycle_date)
            .where(PendingSignal.status == "pending")
        )
        return result.scalar() or 0


class LLMUsageRepository:
    """Repository for LLM usage tracking."""
    
    @staticmethod
    async def track(session: AsyncSession, stats: Dict[str, Any]) -> None:
        """Track LLM usage."""
        from models import LLMUsage
        session.add(LLMUsage(**stats))
        
    @staticmethod
    async def get_daily_cost(session: AsyncSession, timezone_str: str = "UTC") -> float:
        """Get total cost for today."""
        from models import LLMUsage
        import pytz
        
        tz = pytz.timezone(timezone_str)
        now = datetime.now(tz)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_start_utc = today_start.astimezone(pytz.UTC).replace(tzinfo=None)
        
        result = await session.execute(
            select(func.sum(LLMUsage.total_cost))
            .where(LLMUsage.timestamp >= today_start_utc)
        )
        return result.scalar() or 0.0

    @staticmethod
    async def get_recent_errors(session: AsyncSession, minutes: int = 5) -> int:
        """Count errors in the last N minutes."""
        from models import LLMUsage
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        
        result = await session.execute(
            select(func.count(LLMUsage.id))
            .where(LLMUsage.timestamp >= cutoff)
            .where(LLMUsage.http_status != 200)
        )
        return result.scalar() or 0


class IncidentRepository:
    """Repository for incident clustering."""
    
    @staticmethod
    async def find_open_similar(
        session: AsyncSession, 
        region: str,
        event_type: str,
        hours: int = 24
    ) -> Optional[Any]:
        """Find an open incident matching parameters."""
        from models import Incident
        
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        # Simple clustering: Same region + Same event type + Open
        result = await session.execute(
            select(Incident)
            .where(Incident.status == "open")
            .where(Incident.region == region)
            .where(Incident.event_type == event_type)
            .where(Incident.updated_at >= cutoff)
            .order_by(Incident.updated_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
        
    @staticmethod
    async def create(session: AsyncSession, title: str, region: str, event_type: str) -> Any:
        """Create new incident."""
        from models import Incident
        incident = Incident(
            title=title,
            region=region,
            event_type=event_type,
            status="open",
            signals_count=1
        )
        session.add(incident)
        await session.flush()
        return incident
        
    @staticmethod
    async def increment_signal(session: AsyncSession, incident_id: int) -> None:
        """Increment signal count for incident."""
        from models import Incident
        await session.execute(
            update(Incident)
            .where(Incident.id == incident_id)
            .values(
                signals_count=Incident.signals_count + 1, 
                updated_at=datetime.utcnow()
            )
        )


class WatchlistRepository:
    """Repository for watchlist items."""
    
    @staticmethod
    async def add(
        session: AsyncSession, 
        news_id: int, 
        reason: str, 
        score: float = 0.0
    ) -> None:
        """Add item to watchlist."""
        from models import WatchlistItem
        session.add(WatchlistItem(
            news_id=news_id,
            reason=reason,
            score=score
        ))

    @staticmethod
    async def get_recent(session: AsyncSession, limit: int = 20) -> List[Any]:
        """Get recent watchlist items."""
        from models import WatchlistItem
        from sqlalchemy.orm import selectinload
        
        result = await session.execute(
            select(WatchlistItem)
            .options(selectinload(WatchlistItem.news))
            .order_by(WatchlistItem.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
