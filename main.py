import asyncio
import logging
import sys
import signal
from news_collector import collector
from ai_filter import ai_filter  
from database import db
from telegram_bot import notifier
from models import NewsArticle
from config import config
from utils import setup_logging

logger = setup_logging()
manual_check_event = asyncio.Event()
shutdown_event = asyncio.Event()


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    logger.info("\n👋 Получен сигнал завершения, останавливаемся...")
    shutdown_event.set()


async def process_news_cycle():
    new_articles_count = 0
    relevant_events_count = 0
    sent_signals_count = 0
    
    try:
        logger.info("=" * 70)
        logger.info("🚀 STARTING NEWS PROCESSING CYCLE")
        logger.info("=" * 70)
        
        logger.info("")
        logger.info("📥 STEP 1/4: PARALLEL COLLECTION")
        logger.info("-" * 70)
        
        # Начальный прогресс - сбор новостей
        await notifier.update_progress(0, 100, "Сбор новостей")
        
        # Run blocking collection in executor
        loop = asyncio.get_running_loop()
        articles = await loop.run_in_executor(None, collector.collect_all_parallel)
        
        new_articles_count = len(articles)
        logger.info(f"✅ Collection complete: {new_articles_count} new articles")
        
        # Прогресс - сбор завершён
        await notifier.update_progress(100, 100, "Сбор завершён")
        
        if not articles:
            logger.info("ℹ️  No new articles to process")
            await notifier.send_check_results(0, 0, 0)
            return
        
        logger.info("")
        logger.info("📊 STEP 2/4: RETRIEVING UNPROCESSED ARTICLES")
        logger.info("-" * 70)
        unprocessed = db.get_unprocessed_articles(limit=config.MAX_ARTICLES_PER_CHECK)
        logger.info(f"✅ Found {len(unprocessed)} unprocessed articles")
        
        if not unprocessed:
            logger.info("ℹ️  No unprocessed articles")
            await notifier.send_check_results(new_articles_count, 0, 0)
            return
        
        articles_to_filter = []
        for article_dict in unprocessed:
            try:
                article = NewsArticle(**article_dict)
                articles_to_filter.append(article)
            except Exception as e:
                logger.error(f"Error converting article: {e}")
                continue
        
        logger.info("")
        logger.info(f"🤖 STEP 3/4: AI FILTERING ({len(articles_to_filter)} articles)")
        logger.info("-" * 70)
        total_articles = len(articles_to_filter)
        filtered_events = []
        
        for idx, article in enumerate(articles_to_filter, 1):
            try:
                progress_percent = int((idx / total_articles) * 100)
                filled = int(progress_percent / 10)
                bar = "█" * filled + "░" * (10 - filled)
                
                if idx == 1 or idx == total_articles or progress_percent % 10 == 0:
                    logger.info(f"[{bar}] {progress_percent}% - {idx}/{total_articles} articles")
                
                # Обновляем прогресс в Telegram
                if idx == 1 or idx % 5 == 0 or idx == total_articles:
                    await notifier.update_progress(idx, total_articles, "AI-анализ")
                
                # Run blocking AI filtering in executor
                event = await loop.run_in_executor(None, ai_filter.filter_article, article)
                
                if event:
                    filtered_events.append(event)
                    logger.info(f"  ✓ Relevant: {article.title[:60]}...")
                
                db.mark_article_processed(article.id)
            except Exception as e:
                logger.error(f"Error filtering article: {e}")
                continue

        
        relevant_events_count = len(filtered_events)
        logger.info(f"✅ AI filtering complete: {relevant_events_count} relevant events found")
        
        if not filtered_events:
            logger.info("ℹ️  No relevant events found")
            await notifier.send_check_results(new_articles_count, 0, 0)
            return
        
        logger.info("")
        logger.info(f"📱 STEP 4/4: SENDING NOTIFICATIONS ({len(filtered_events)} events)")
        logger.info("-" * 70)
        sent_count = 0
        
        for idx, event in enumerate(filtered_events, 1):
            try:
                progress_percent = int((idx / len(filtered_events)) * 100)
                filled = int(progress_percent / 10)
                bar = "█" * filled + "░" * (10 - filled)
                logger.info(f"[{bar}] {progress_percent}% - Sending {idx}/{len(filtered_events)}")
                
                if await notifier.send_event(event):
                    sent_count += 1
                    logger.info(f"  ✓ Sent: {event.title[:60]}...")
            except Exception as e:
                logger.error(f"Error sending event: {e}")
                continue
        
        sent_signals_count = sent_count
        logger.info(f"✅ Notifications sent: {sent_count}/{len(filtered_events)}")
        
        stats = db.get_stats()
        logger.info("")
        logger.info("=" * 70)
        logger.info("📊 CYCLE STATISTICS")
        logger.info("=" * 70)
        logger.info(f"  📰 Total articles: {stats['total_articles']}")
        logger.info(f"  ✅ Processed: {stats['processed_articles']}")
        logger.info(f"  🎯 Filtered events: {stats['filtered_events']}")
        logger.info(f"  📤 Sent signals: {stats['sent_signals']}")
        logger.info("=" * 70)
        
        await notifier.send_check_results(new_articles_count, relevant_events_count, sent_signals_count)
        
    except Exception as e:
        logger.error(f"Error in processing cycle: {e}", exc_info=True)
        await notifier.send_check_results(new_articles_count, relevant_events_count, sent_signals_count)


async def main_loop():
    logger.info("🤖 News Monitoring System Started")
    logger.info(f"⏱️  Check interval: {config.CHECK_INTERVAL_MINUTES} minutes")
    logger.info(f"🔍 Relevance threshold: {config.RELEVANCE_THRESHOLD}")
    logger.info(f"📡 Monitoring {len(config.RSS_SOURCES)} sources")
    logger.info("=" * 70)
    
    await notifier.start(manual_check_event)
    
    # Ждём первого пользователя или сигнала завершения
    logger.info("⏳ Waiting for first user to login...")
    while not notifier.has_authenticated_users() and not shutdown_event.is_set():
        await asyncio.sleep(0.5)
    
    if shutdown_event.is_set():
        await notifier.shutdown()
        return
    
    logger.info("✅ User authenticated! Starting news monitoring...")
    
    try:
        while not shutdown_event.is_set():
            await process_news_cycle()
            
            if shutdown_event.is_set():
                break
                
            interval_seconds = config.CHECK_INTERVAL_MINUTES * 60
            logger.info(f"\n⏳ Next check in {config.CHECK_INTERVAL_MINUTES} minutes...")
            
            # Ждём либо ручную проверку, либо таймаут, либо shutdown
            try:
                done, pending = await asyncio.wait(
                    [
                        asyncio.create_task(manual_check_event.wait()),
                        asyncio.create_task(shutdown_event.wait()),
                        asyncio.create_task(asyncio.sleep(interval_seconds))
                    ],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # Отменяем незавершённые задачи
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                
                if shutdown_event.is_set():
                    break
                    
                if manual_check_event.is_set():
                    manual_check_event.clear()
                    logger.info("🔔 Manual check triggered!")
                    
            except Exception as e:
                logger.error(f"Error in wait loop: {e}")
                break
                
    finally:
        await notifier.shutdown()
        logger.info("✅ Shutdown complete")


if __name__ == "__main__":
    # Устанавливаем обработчики сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        config.validate()
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
