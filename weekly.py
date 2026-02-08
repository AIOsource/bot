"""Weekly report generation."""
from datetime import datetime, timedelta
from typing import List, Dict, Any
from collections import Counter

from db_pkg import get_session, NewsRepository, SignalRepository
from models import Signal, News
from logging_setup import get_logger

logger = get_logger("reports.weekly")


async def generate_weekly_report() -> str:
    """
    Generate weekly report text for admin.
    
    Per ТЗ, includes:
    - Total processed
    - Passed filter1
    - Passed LLM
    - Sent signals
    - Top sources
    
    Returns:
        Formatted report text
    """
    from sqlalchemy import select, func
    
    async with get_session() as session:
        cutoff = datetime.utcnow() - timedelta(days=7)
        
        # Total collected
        total = await session.execute(
            select(func.count(News.id)).where(News.collected_at >= cutoff)
        )
        total_count = total.scalar() or 0
        
        # Passed filter1 (score >= threshold, sent to LLM)
        # Status: llm_passed, sent, llm_failed, suppressed_limit
        passed_filter1 = await session.execute(
            select(func.count(News.id)).where(
                News.collected_at >= cutoff,
                News.filter1_score >= 4  # Threshold
            )
        )
        filter1_count = passed_filter1.scalar() or 0
        
        # Passed LLM (llm_passed or sent status)
        passed_llm = await session.execute(
            select(func.count(News.id)).where(
                News.collected_at >= cutoff,
                News.status.in_(["llm_passed", "sent", "suppressed_limit"])
            )
        )
        llm_passed_count = passed_llm.scalar() or 0
        
        # Sent signals
        signals = await SignalRepository.get_recent(session, days=7)
        sent_count = len(signals)
        
        # Duplicates
        duplicates = await session.execute(
            select(func.count(News.id)).where(
                News.collected_at >= cutoff,
                News.status == "duplicate"
            )
        )
        duplicate_count = duplicates.scalar() or 0
        
        # Top sources for signals
        source_counts: Dict[str, int] = Counter()
        for signal in signals:
            # Get source from news
            news = await NewsRepository.get_by_id(session, signal.news_id)
            if news:
                source_counts[news.source] += 1
    
    # Group signals by day
    days_stats: Dict[str, int] = {}
    for signal in signals:
        day = signal.sent_at.strftime("%Y-%m-%d")
        days_stats[day] = days_stats.get(day, 0) + 1
    
    # Group by event type
    event_types: Dict[str, int] = Counter(s.event_type or "unknown" for s in signals)
    
    # Group by region
    regions: Dict[str, int] = Counter(s.region or "не определён" for s in signals)
    
    # Format report
    report_lines = [
        "📈 <b>НЕДЕЛЬНЫЙ ОТЧЁТ</b>",
        f"Период: {(datetime.now() - timedelta(days=7)).strftime('%d.%m')} - {datetime.now().strftime('%d.%m.%Y')}",
        "",
        "<b>📊 Воронка обработки:</b>",
        f"• Собрано новостей: {total_count}",
        f"• Дубликатов отброшено: {duplicate_count}",
        f"• Прошло filter1: {filter1_count}",
        f"• Прошло LLM: {llm_passed_count}",
        f"• Отправлено сигналов: {sent_count}",
    ]
    
    if source_counts:
        report_lines.extend([
            "",
            "<b>🏆 Топ источники сигналов:</b>",
        ])
        for source, count in source_counts.most_common(5):
            report_lines.append(f"• {source}: {count}")
    
    if days_stats:
        report_lines.extend([
            "",
            "<b>📅 По дням:</b>",
        ])
        for day, count in sorted(days_stats.items()):
            report_lines.append(f"• {day}: {count} сигнал(ов)")
    
    if event_types:
        report_lines.extend([
            "",
            "<b>🏷 По типам событий:</b>",
        ])
        for et, count in event_types.most_common():
            report_lines.append(f"• {et}: {count}")
    
    if regions:
        report_lines.extend([
            "",
            "<b>🗺 По регионам (топ-5):</b>",
        ])
        for region, count in regions.most_common(5):
            report_lines.append(f"• {region}: {count}")
    
    return "\n".join(report_lines)


async def get_daily_summary() -> Dict[str, Any]:
    """Get summary stats for the last 24 hours."""
    async with get_session() as session:
        stats = await NewsRepository.get_stats(session, days=1)
        signals_today = await SignalRepository.count_today(session)
    
    return {
        "collected": stats.get("total", 0),
        "signals": signals_today,
        "filtered": stats.get("status_filtered", 0),
        "errors": stats.get("status_error", 0) + stats.get("status_llm_failed", 0),
    }
