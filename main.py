"""Main entry point for PRSBOT."""
import asyncio
import uuid
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from settings import get_settings
from config_loader import get_config_loader, get_config
from logging_setup import setup_logging, get_logger
from db_pkg import init_database, get_session, NewsRepository, SignalRepository, LockRepository
from sources_pkg import RSSFetcher, WebsiteFetcher
from pipeline_pkg import (
    normalize_news_item, prepare_for_llm, Deduplicator, compute_simhash,
    KeywordFilter, detect_region, LLMClient, LLMResponse,
    decide, get_status_from_decision, create_signal_from_llm,
    check_freshness, check_resolved, check_noise
)
from bot_pkg import create_bot, Broadcaster


logger = None  # Will be initialized in main()


async def process_news_cycle(broadcaster: Optional[Broadcaster] = None):
    """
    Main news processing cycle.
    
    Steps:
    1. Fetch from all sources
    2. Normalize and deduplicate
    3. Apply filter1
    4. Send to LLM if passed
    5. Decide and send signals
    """
    global logger
    if logger is None:
        logger = get_logger("main")
    
    settings = get_settings()
    config = get_config()
    
    # Acquire processing lock
    instance_id = str(uuid.uuid4())[:8]
    async with get_session() as session:
        acquired = await LockRepository.acquire(
            session, "processing", duration_seconds=600, instance_id=instance_id
        )
        await session.commit()
    
    if not acquired:
        logger.info("processing_skipped", reason="lock_held")
        return
    
    try:
        start_time = datetime.now()
        
        # 1. Fetch from sources
        rss_fetcher = RSSFetcher(
            timeout=config.http.timeout,
            retries=config.http.retries
        )
        
        # Filter to RSS and Google News sources only
        rss_sources = [s for s in config.sources if s.type in ("rss", "google_news_rss")]
        
        logger.info("fetch_start", sources_count=len(rss_sources))
        raw_items = await rss_fetcher.fetch_all(rss_sources)
        
        # 2. Also fetch from web sources
        web_sources = [s for s in config.sources if s.type == "web"]
        if web_sources:
            web_fetcher = WebsiteFetcher(timeout=config.http.timeout)
            for source in web_sources:
                web_items = await web_fetcher.fetch_news_list(source)
                raw_items.extend(web_items)
        
        logger.info("fetch_complete", items=len(raw_items))
        
        if not raw_items:
            logger.info("processing_complete", new_items=0, signals=0)
            return
        
        # 3. Normalize and check duplicates
        deduplicator = Deduplicator(simhash_threshold=config.dedup.simhash_threshold)
        
        # Load recent simhashes
        async with get_session() as session:
            recent_hashes = await NewsRepository.get_recent_simhashes(session, hours=72)
            deduplicator.set_existing_hashes(recent_hashes)
        
        # Counters for cycle stats
        stats = {
            "filtered_old": 0,
            "filtered_resolved": 0, 
            "filtered_noise": 0,
            "filtered_combo": 0,
            "filtered_score": 0,
            "llm_failed": 0,
            "llm_skipped": 0,
            "sent": 0
        }
        
        new_items = []
        url_params = set(config.dedup.url_params_to_remove)
        
        for item in raw_items:
            normalized = normalize_news_item(item, list(url_params))
            
            # URL dedup
            async with get_session() as session:
                existing = await NewsRepository.url_exists(session, normalized["url_normalized"])
                if existing:
                    logger.debug("dedup_url_skip", url=normalized["url_normalized"][:60])
                    continue
            
            # Freshness check (BEFORE simhash to avoid computing hash for stale news)
            freshness_result = check_freshness(
                published_at=normalized.get("published_at"),
                collected_at=datetime.utcnow(),
                max_age_days=config.freshness.max_age_days,
                allow_missing_published_at=config.freshness.allow_missing_published_at,
                fallback_to_collected_at=config.freshness.fallback_to_collected_at,
                trace_id=f"pre-{normalized['url_normalized'][:30]}"
            )
            
            if not freshness_result.passed:
                stats["filtered_old"] += 1
                logger.info(
                    "freshness_rejected",
                    decision_code=freshness_result.decision_code,
                    age_days=freshness_result.age_days
                )
                continue
            
            # Simhash dedup
            duplicate_of = deduplicator.check_duplicate(
                normalized["title"],
                normalized["text"]
            )
            
            # Compute simhash for storage
            normalized["simhash"] = deduplicator.compute_hash(
                normalized["title"],
                normalized["text"]
            )
            
            if duplicate_of:
                # Save as duplicate with canonical reference (per ТЗ)
                async with get_session() as session:
                    await NewsRepository.create(session, {
                        "title": normalized["title"],
                        "text": normalized["text"],
                        "source": normalized["source"],
                        "url": normalized["url"],
                        "url_normalized": normalized["url_normalized"],
                        "published_at": normalized.get("published_at"),
                        "collected_at": datetime.utcnow(),
                        "simhash": normalized["simhash"],
                        "canonical_news_id": duplicate_of,
                        "status": "duplicate",
                    })
                    await session.commit()
                logger.debug("dedup_simhash_saved", canonical_id=duplicate_of)
                continue
            
            # Detect region
            if not normalized.get("region"):
                normalized["region"] = detect_region(
                    normalized["text"],
                    normalized["title"],
                    item.get("region_hint")
                )
            
            new_items.append(normalized)
        
        logger.info("dedup_complete", new_items=len(new_items), raw_items=len(raw_items))
        
        if not new_items:
            logger.info("processing_complete", new_items=0, signals=0)
            return
        
        # Apply backpressure limit
        if len(new_items) > config.limits.max_processing_batch:
            logger.warning(
                "backpressure_active",
                total_items=len(new_items),
                limit=config.limits.max_processing_batch,
                dropped=len(new_items) - config.limits.max_processing_batch
            )
            new_items = new_items[:config.limits.max_processing_batch]
        
        # 4. Save new items and process
        keyword_filter = KeywordFilter(
            keywords=config.keywords,
            weights=config.weights,
            threshold=config.thresholds.filter1_to_llm
        )
        
        llm_client = LLMClient(settings)
        # LLMClient handles internal defaults, config overrides can be applied if needed
        # We can implement specific throttle override methods in LLMClient if config requires it
        # For now, relying on LLMClient defaults for Simplicity in v1.7.0 logic
        
        signals_sent = 0
        
        for item in new_items:
            # Generate trace_id
            trace_id = str(uuid.uuid4())[:8]
            
            # Save to DB
            async with get_session() as session:
                news = await NewsRepository.create(session, {
                    "title": item["title"],
                    "text": item["text"],
                    "source": item["source"],
                    "url": item["url"],
                    "url_normalized": item["url_normalized"],
                    "published_at": item.get("published_at"),
                    "collected_at": datetime.utcnow(),
                    "region": item.get("region"),
                    "simhash": item.get("simhash"),
                    "status": "raw",
                })
                await session.commit()
                news_id = news.id
                
                # Add to deduplicator cache
                deduplicator.add_hash(news_id, item.get("simhash", ""))
            
            # Resolved filter
            if config.resolved_filter.enabled:
                resolved_result = check_resolved(
                    title=item["title"],
                    text=item["text"],
                    hard_resolved_phrases=config.resolved_filter.hard_resolved_phrases,
                    soft_resolved_words=config.resolved_filter.soft_resolved_words,
                    allow_if_still_ongoing_words=config.resolved_filter.allow_if_still_ongoing_words,
                    enabled=True,
                    trace_id=trace_id
                )
                
                if not resolved_result.passed:
                    stats["filtered_resolved"] += 1
                    async with get_session() as session:
                        await NewsRepository.update_status(
                            session, news_id, "filtered_resolved",
                            decision_code=resolved_result.decision_code
                        )
                        await session.commit()
                    continue
            
            # Noise filter
            if config.noise_filter.enabled:
                noise_result = check_noise(
                    title=item["title"],
                    text=item["text"],
                    hard_negative_topics=config.noise_filter.hard_negative_topics,
                    domestic_noise=config.noise_filter.бытовое_шум,
                    exception_infra_phrases=config.noise_filter.exception_infra_phrases,
                    enabled=True,
                    trace_id=trace_id
                )
                
                if not noise_result.passed:
                    stats["filtered_noise"] += 1
                    async with get_session() as session:
                        await NewsRepository.update_status(
                            session, news_id, "filtered_noise",
                            decision_code=noise_result.decision_code
                        )
                        await session.commit()
                    continue
            
            # Filter 1 with combo rules + strong event override
            passed, filter_result, decision_code = keyword_filter.should_send_to_llm(
                item["title"],
                item["text"],
                require_combo=config.filter1_gate.require_combo_to_llm,
                event_categories=config.filter1_gate.event_categories_required,
                object_categories=config.filter1_gate.object_categories_required,
                strong_event_override_enabled=config.filter1_gate.strong_event_override_enabled,
                strong_event_override_phrases=config.filter1_gate.strong_event_override_phrases,
                trace_id=trace_id
            )
            
            logger.info(
                "filter1_scored",
                trace_id=trace_id,
                news_id=news_id,
                score=filter_result.score,
                matched=filter_result.positive_matches[:5],
                decision_code=decision_code,
                passed_to_llm=passed
            )
            
            if not passed:
                if decision_code == "COMBO_RULE_FAILED":
                    stats["filtered_combo"] += 1
                else:
                    stats["filtered_score"] += 1
                async with get_session() as session:
                    await NewsRepository.update_status(
                        session, news_id, "filtered",
                        filter1_score=filter_result.score,
                        decision_code=decision_code
                    )
                    await session.commit()
                continue
            
            # Check if LLM is available
            llm_available, llm_skip_reason = llm_client.is_available()
            if not llm_available:
                stats["llm_skipped"] += 1
                logger.warning("llm_unavailable", trace_id=trace_id, reason=llm_skip_reason)
                async with get_session() as session:
                    await NewsRepository.update_status(
                        session, news_id, "llm_skipped",
                        filter1_score=filter_result.score,
                        decision_code=llm_skip_reason
                    )
                    await session.commit()
                continue
            
            # Filter 2 (LLM)
            llm_text = prepare_for_llm(item["title"], item["text"])
            llm_response, llm_raw, llm_error = await llm_client.analyze(
                title=item["title"],
                text=llm_text,
                region=item.get("region"),
                source=item["source"],
                trace_id=trace_id
            )
            
            if llm_response:
                logger.info(
                    "llm_classified",
                    trace_id=trace_id,
                    news_id=news_id,
                    relevance=llm_response.relevance,
                    urgency=llm_response.urgency,
                    action=llm_response.action
                )
            else:
                stats["llm_failed"] += 1
                logger.warning("llm_failed", trace_id=trace_id, news_id=news_id, error_code=llm_error)
            
            # Decision
            async with get_session() as session:
                signals_today = await SignalRepository.count_today(session)
            
            decision = decide(
                llm_response=llm_response,
                filter1_score=filter_result.score,
                filter1_passed=True,
                signals_today=signals_today,
                max_signals_per_day=config.limits.max_signals_per_day,
                relevance_threshold=config.thresholds.llm_relevance,
                urgency_threshold=config.thresholds.llm_urgency
            )
            
            status = get_status_from_decision(decision, llm_failed=(llm_response is None))
            
            # Update news status with llm_json as TEXT string (per ТЗ)
            import json as json_module
            async with get_session() as session:
                await NewsRepository.update_status(
                    session, news_id, status,
                    filter1_score=filter_result.score,
                    llm_json=json_module.dumps(llm_response.model_dump(), ensure_ascii=False) if llm_response else None,
                    llm_raw_response=llm_raw  # Store raw LLM output
                )
                await session.commit()
            
            # Send signal if approved (with atomic limit check)
            if decision.should_send and broadcaster and llm_response:
                signal_data = create_signal_from_llm(
                    llm_response,
                    title=item["title"],
                    url=item["url"],
                    region=item.get("region")
                )
                
                # Atomic signal creation with limit check (per ТЗ)
                async with get_session() as session:
                    # Check for similar recent signal (suppression)
                    similar = await SignalRepository.find_similar_recent(
                        session,
                        event_type=signal_data["event_type"],
                        region=signal_data["region"],
                        object_type=signal_data["object_type"],
                        hours=24
                    )
                    
                    if similar:
                        # Suppress
                        await NewsRepository.update_status(session, news_id, "suppressed_similar")
                        await session.commit()
                        logger.info("signal_suppressed_similar", news_id=news_id, similar_to=similar.id)
                        continue
                    
                    signal = await SignalRepository.try_create_if_under_limit(
                        session,
                        {
                            "news_id": news_id,
                            "sent_at": datetime.utcnow(),
                            "event_type": signal_data["event_type"],
                            "urgency": signal_data["urgency"],
                            "object_type": signal_data["object_type"],
                            "sphere": signal_data["sphere"],
                            "region": signal_data["region"],
                            "why": signal_data["why"],
                            "message_text": signal_data["message_text"],
                            "recipients_count": 0,
                        },
                        max_per_day=config.limits.max_signals_per_day,
                        timezone_str=settings.app_timezone  # Per ТЗ: APP_TIMEZONE for limits
                    )
                    
                    if signal is None:
                        # Limit reached atomically - update status
                        await NewsRepository.update_status(session, news_id, "suppressed_limit")
                        await session.commit()
                        logger.info("signal_limit_reached_atomic", news_id=news_id)
                        continue
                    
                    signal_id = signal.id
                    await session.commit()
                
                # Broadcast
                recipients = await broadcaster.send_signal(
                    signal_data["message_text"],
                    signal_id=signal_id
                )
                
                # Update recipients count
                async with get_session() as session:
                    from sqlalchemy import update
                    from db_pkg.models import Signal
                    await session.execute(
                        update(Signal).where(Signal.id == signal_id).values(recipients_count=recipients)
                    )
                    await session.commit()
                
                signals_sent += 1
                
                logger.info(
                    "signal_sent",
                    news_id=news_id,
                    signal_id=signal_id,
                    recipients=recipients
                )
        
        stats["sent"] = signals_sent
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        logger.info(
            "cycle_complete",
            new_items=len(new_items),
            signals=signals_sent,
            duration_ms=duration_ms,
            filtered_old=stats["filtered_old"],
            filtered_resolved=stats["filtered_resolved"],
            filtered_noise=stats["filtered_noise"],
            filtered_combo=stats["filtered_combo"],
            filtered_score=stats["filtered_score"],
            llm_failed=stats["llm_failed"],
            llm_skipped=stats["llm_skipped"]
        )
        
    finally:
        # Release lock
        async with get_session() as session:
            await LockRepository.release(session, "processing")
            await session.commit()


# Global state for first start trigger
_first_search_triggered = False
_broadcaster_ref = None
_scheduler_ref = None


async def trigger_first_search():
    """Trigger the first search after /start."""
    global _first_search_triggered
    if _first_search_triggered:
        return False
    _first_search_triggered = True
    
    if _broadcaster_ref:
        logger.info("first_search_triggered")
        await process_news_cycle(_broadcaster_ref)
    return True


def is_first_search_done():
    """Check if first search was triggered."""
    return _first_search_triggered


async def main():
    """Main entry point."""
    global logger, _broadcaster_ref, _scheduler_ref
    
    # Load settings
    settings = get_settings()
    
    # Setup logging
    setup_logging(settings.log_level)
    logger = get_logger("main")
    
    logger.info("prsbot_starting", version="1.0.0")
    
    # Load config
    config_loader = get_config_loader()
    config = config_loader.load()
    logger.info("config_loaded", sources=len(config.sources))
    
    # Initialize database
    await init_database(settings.database_url)
    
    # Initialize monitor DB
    from llm_monitor import init_monitor_db
    await init_monitor_db()
    
    logger.info("database_initialized")
    
    # Initialize Ops Server (Health/Metrics)
    from ops_http import OpsServer
    # Allows env var override or config
    ops_port = 8080
    ops_server = OpsServer(port=ops_port)
    await ops_server.start()
    
    # Create bot
    bot, dp = await create_bot(settings.telegram_bot_token)
    broadcaster = Broadcaster(bot)
    _broadcaster_ref = broadcaster
    logger.info("bot_created")
    
    # Setup scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        process_news_cycle,
        trigger=IntervalTrigger(minutes=config.schedule.check_interval_minutes),
        args=[broadcaster],
        id="news_cycle",
        name="News Processing Cycle",
        replace_existing=True,
    )
    
    # Auto-Heal Job (Runs every 30 mins)
    async def auto_heal_job():
        """Try to re-enable disabled sources."""
        from db_pkg import SourceHealthRepository
        from datetime import datetime, timedelta
        
        cooldown = timedelta(minutes=60) # Default cooldown
        
        async with get_session() as session:
            summary = await SourceHealthRepository.get_health_summary(session)
            
            for s in summary:
                if s["is_disabled"]:
                    # Check cooldown
                    if s.get("disabled_at") and (datetime.utcnow() - s["disabled_at"] > cooldown):
                        await SourceHealthRepository.enable_source(session, s["source_id"])
                        logger.info("source_auto_healed", source_id=s["source_id"])
                        # Only heal one per cycle to be safe
                        break
            await session.commit()

    scheduler.add_job(
        auto_heal_job,
        trigger=IntervalTrigger(minutes=30),
        id="auto_heal",
        name="Source Auto-Heal",
        replace_existing=True
    )
    
    # Retention Job (Daily at 03:00)
    async def retention_job():
        """Clean old data."""
        async with get_session() as session:
            # 1. News (30 days)
            deleted_news = await NewsRepository.cleanup_old_news(session, days=30)
            
            # 2. LLM Usage (30 days)
            from sqlalchemy import delete
            from models import LLMUsage, Incident, WatchlistItem
            
            cutoff = datetime.utcnow() - timedelta(days=30)
            
            # LLM Usage
            res_llm = await session.execute(
                delete(LLMUsage).where(LLMUsage.timestamp < cutoff)
            )
            deleted_llm = res_llm.rowcount
            
            # Watchlist (30 days)
            res_watch = await session.execute(
                delete(WatchlistItem).where(WatchlistItem.created_at < cutoff)
            )
            deleted_watch = res_watch.rowcount
            
            # Incidents (60 days - keep longer)
            cutoff_incidents = datetime.utcnow() - timedelta(days=60)
            res_inc = await session.execute(
                delete(Incident).where(Incident.updated_at < cutoff_incidents)
            )
            deleted_inc = res_inc.rowcount
            
            await session.commit()
            
            logger.info(
                "retention_complete", 
                news=deleted_news, 
                llm=deleted_llm, 
                watchlist=deleted_watch,
                incidents=deleted_inc
            )
            
            # Vacuum periodically
            await session.commit() # ensure transaction closed
            # TODO: Run vacuum if on SQLite (requires separate connection logic usually)
    
    scheduler.add_job(
        retention_job,
        trigger="cron",
        hour=3,
        minute=0,
        id="retention",
        name="Daily Retention",
        replace_existing=True,
    )
    _scheduler_ref = scheduler
    
    # Wait for first /start to trigger initial search
    logger.info("waiting_for_first_start", message="Bot ready, waiting for first /start command")
    
    # Start bot polling
    logger.info("bot_polling_start")
    try:
        # Start scheduler after bot starts (will run on interval)
        scheduler.start()
        logger.info("scheduler_started", interval_minutes=config.schedule.check_interval_minutes)
        
        await dp.start_polling(bot, drop_pending_updates=True)
    finally:
        await ops_server.stop()
        scheduler.shutdown()
        await bot.session.close()
        logger.info("prsbot_shutdown")


def sigterm_handler(_signum, _frame):
    """Handle SIGTERM/SIGINT for graceful shutdown (Docker)."""
    import sys
    # logger might not be init if early crash, but mostly ok
    print("SIGTERM received, shutting down...")
    sys.exit(0)


if __name__ == "__main__":
    import signal
    import sys
    
    # Register signal handlers
    signal.signal(signal.SIGTERM, sigterm_handler)
    signal.signal(signal.SIGINT, sigterm_handler)
    
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass  # Graceful exit handled in main() finally block logic if needed
    except Exception as e:
        print(f"Critical error: {e}")
        import traceback
        traceback.print_exc()
