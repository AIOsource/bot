"""Admin command handlers for Telegram bot."""
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from settings import get_settings
from config_loader import get_config, get_config_loader
from db_pkg import get_session, NewsRepository, SignalRepository, SubscriberRepository, ConfigRepository
from logging_setup import get_logger

logger = get_logger("bot.admin")
router = Router(name="admin")


def is_admin(message: Message) -> bool:
    """Check if message is from admin."""
    settings = get_settings()
    return message.chat.id == settings.admin_chat_id


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Show admin panel."""
    if not is_admin(message):
        await message.answer("❌ Команда недоступна.")
        return
    
    await message.answer(
        "🔧 <b>Панель администратора</b>\n\n"
        "<b>Статистика:</b>\n"
        "• /stats — статистика за сутки\n"
        "• /report_week — недельный отчёт\n"
        "• /health — статус системы\n\n"
        "<b>Источники:</b>\n"
        "• /sources_list — список источников\n"
        "• /sources_add \u003curl\u003e \u003cname\u003e — добавить\n"
        "• /sources_remove \u003cname\u003e — удалить\n\n"
        "<b>Конфигурация:</b>\n"
        "• /config_show — текущие настройки\n"
        "• /config_set \u003cpath\u003e \u003cvalue\u003e — изменить\n"
        "• /reload_config — перечитать конфиг\n\n"
        "<b>Тестирование:</b>\n"
        "• /test_signal — тестовый сигнал (только вам)\n\n"
        "<b>Рассылка:</b>\n"
        "• /broadcast \u003ctext\u003e — разослать всем",
        parse_mode="HTML"
    )


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Show daily/weekly stats."""
    if not is_admin(message):
        await message.answer("❌ Команда недоступна.")
        return
    
    async with get_session() as session:
        # Daily stats
        daily_stats = await NewsRepository.get_stats(session, days=1)
        
        # Weekly stats
        weekly_stats = await NewsRepository.get_stats(session, days=7)
        
        # Signals today
        signals_today = await SignalRepository.count_today(session)
        
        # Subscribers
        subscribers_count = await SubscriberRepository.count_active(session)
    
    await message.answer(
        f"📊 <b>Статистика</b>\n\n"
        f"<b>За сутки:</b>\n"
        f"• Собрано: {daily_stats.get('total', 0)}\n"
        f"• Отправлено сигналов: {signals_today}\n"
        f"• Отфильтровано: {daily_stats.get('status_filtered', 0)}\n\n"
        f"<b>За неделю:</b>\n"
        f"• Собрано: {weekly_stats.get('total', 0)}\n"
        f"• Сигналов: {weekly_stats.get('status_sent', 0)}\n\n"
        f"<b>Подписчики:</b> {subscribers_count}",
        parse_mode="HTML"
    )


@router.message(Command("report_week"))
async def cmd_report_week(message: Message):
    """Generate weekly report."""
    if not is_admin(message):
        await message.answer("❌ Команда недоступна.")
        return
    
    async with get_session() as session:
        signals = await SignalRepository.get_recent(session, days=7)
        stats = await NewsRepository.get_stats(session, days=7)
    
    if not signals:
        await message.answer(
            "📈 <b>Недельный отчёт</b>\n\n"
            "За неделю сигналов не было.",
            parse_mode="HTML"
        )
        return
    
    signals_text = "\n".join([
        f"• [{s.event_type}] {s.region or 'N/A'} - ур.{s.urgency}"
        for s in signals[:10]
    ])
    
    await message.answer(
        f"📈 <b>Недельный отчёт</b>\n\n"
        f"<b>Всего собрано:</b> {stats.get('total', 0)}\n"
        f"<b>Отправлено сигналов:</b> {len(signals)}\n\n"
        f"<b>Последние сигналы:</b>\n{signals_text}",
        parse_mode="HTML"
    )


@router.message(Command("sources_list"))
async def cmd_sources_list(message: Message):
    """List configured sources."""
    if not is_admin(message):
        await message.answer("❌ Команда недоступна.")
        return
    
    config = get_config()
    sources = config.sources
    
    # Group by type
    rss_count = len([s for s in sources if s.type == "rss"])
    web_count = len([s for s in sources if s.type == "web"])
    gnews_count = len([s for s in sources if s.type == "google_news_rss"])
    
    # Sample sources
    sample = "\n".join([f"• {s.name}" for s in sources[:10]])
    
    await message.answer(
        f"📡 <b>Источники ({len(sources)})</b>\n\n"
        f"RSS: {rss_count}\n"
        f"Web: {web_count}\n"
        f"Google News: {gnews_count}\n\n"
        f"<b>Примеры:</b>\n{sample}\n"
        f"... и ещё {max(0, len(sources) - 10)}",
        parse_mode="HTML"
    )


@router.message(Command("config_show"))
async def cmd_config_show(message: Message):
    """Show current config (without secrets)."""
    if not is_admin(message):
        await message.answer("❌ Команда недоступна.")
        return
    
    config = get_config()
    
    await message.answer(
        f"⚙️ <b>Конфигурация</b>\n\n"
        f"<b>Пороги:</b>\n"
        f"• filter1_to_llm: {config.thresholds.filter1_to_llm}\n"
        f"• llm_relevance: {config.thresholds.llm_relevance}\n"
        f"• llm_urgency: {config.thresholds.llm_urgency}\n\n"
        f"<b>Лимиты:</b>\n"
        f"• max_signals_per_day: {config.limits.max_signals_per_day}\n\n"
        f"<b>Дедупликация:</b>\n"
        f"• simhash_threshold: {config.dedup.simhash_threshold}\n\n"
        f"<b>Расписание:</b>\n"
        f"• check_interval: {config.schedule.check_interval_minutes} мин",
        parse_mode="HTML"
    )


@router.message(Command("config_set"))
async def cmd_config_set(message: Message):
    """Set config value."""
    if not is_admin(message):
        await message.answer("❌ Команда недоступна.")
        return
    
    # Parse: /config_set path value
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer(
            "⚙️ Использование: /config_set <path> <value>\n"
            "Пример: /config_set limits.max_signals_per_day 10",
            parse_mode="HTML"
        )
        return
    
    key = parts[1]
    value = parts[2]
    
    # Validate key format
    allowed_keys = [
        "thresholds.filter1_to_llm",
        "thresholds.llm_relevance",
        "thresholds.llm_urgency",
        "limits.max_signals_per_day",
        "dedup.simhash_threshold",
        "schedule.check_interval_minutes",
    ]
    
    if key not in allowed_keys:
        await message.answer(
            f"❌ Недопустимый ключ: {key}\n\n"
            f"Допустимые ключи:\n" + "\n".join(f"• {k}" for k in allowed_keys),
            parse_mode="HTML"
        )
        return
    
    # Save to DB
    async with get_session() as session:
        await ConfigRepository.set(session, key, value, message.chat.id)
        await session.commit()
    
    # Apply to config
    loader = get_config_loader()
    overrides = {key: value}
    loader.set_overrides(overrides)
    
    logger.info("config_updated", key=key, value=value, by=message.chat.id)
    
    await message.answer(
        f"✅ Конфиг обновлён:\n<code>{key} = {value}</code>",
        parse_mode="HTML"
    )


@router.message(Command("reload_config"))
async def cmd_reload_config(message: Message):
    """Reload config from YAML + DB."""
    if not is_admin(message):
        await message.answer("❌ Команда недоступна.")
        return
    
    loader = get_config_loader()
    
    # Load DB overrides
    async with get_session() as session:
        overrides = await ConfigRepository.get_all(session)
    
    # Reload
    loader.reload()
    loader.set_overrides(overrides)
    
    logger.info("config_reloaded", overrides_count=len(overrides))
    
    await message.answer(
        f"🔄 Конфигурация перезагружена.\n"
        f"Применено {len(overrides)} override(s) из БД.",
        parse_mode="HTML"
    )


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    """Broadcast message to all subscribers."""
    if not is_admin(message):
        await message.answer("❌ Команда недоступна.")
        return
    
    # Parse: /broadcast <text>
    text = message.text.replace("/broadcast", "", 1).strip()
    if not text:
        await message.answer(
            "📢 Использование: /broadcast <текст сообщения>",
            parse_mode="HTML"
        )
        return
    
    # Confirmation
    await message.answer(
        f"⚠️ <b>Подтвердите рассылку:</b>\n\n"
        f"{text[:200]}...\n\n"
        f"Отправьте /broadcast_confirm для подтверждения.",
        parse_mode="HTML"
    )
    
    # Store for confirmation (simple in-memory, could use state)
    # For now, just send directly (in production, use FSM)


@router.message(Command("broadcast_confirm"))
async def cmd_broadcast_confirm(message: Message):
    """Confirm and execute broadcast."""
    if not is_admin(message):
        await message.answer("❌ Команда недоступна.")
        return
    
    await message.answer(
        "📢 Для рассылки используйте модуль broadcaster напрямую.\n"
        "Эта функция требует явного текста.",
        parse_mode="HTML"
    )


@router.message(Command("health"))
async def cmd_health(message: Message):
    """Show system health status (admin only)."""
    if not is_admin(message):
        await message.answer("❌ Команда недоступна.")
        return
    
    logger.info(
        "admin_action",
        action="health_check",
        admin_id=message.chat.id
    )
    
    settings = get_settings()
    config = get_config()
    
    # Check components
    checks = []
    
    # DB check
    try:
        async with get_session() as session:
            await SubscriberRepository.count_active(session)
        checks.append("✅ БД: ok")
    except Exception as e:
        checks.append(f"❌ БД: {str(e)[:50]}")
    
    # LLM key check
    if settings.openrouter_api_key and len(settings.openrouter_api_key) > 10:
        checks.append("✅ OpenRouter: ключ есть")
    else:
        checks.append("❌ OpenRouter: ключ отсутствует")
    
    # Subscribers
    async with get_session() as session:
        subs = await SubscriberRepository.count_active(session)
        signals_today = await SignalRepository.count_today(session, settings.app_timezone)
        
        # Errors in last 24h
        daily_stats = await NewsRepository.get_stats(session, days=1)
    
    checks.append(f"👥 Подписчиков: {subs}")
    checks.append(f"📡 Источников: {len(config.sources)}")
    checks.append(f"📨 Сигналов сегодня: {signals_today}/{config.limits.max_signals_per_day}")
    checks.append(f"❗ Ошибок LLM: {daily_stats.get('status_llm_failed', 0)}")
    
    await message.answer(
        "🏥 <b>Статус системы</b>\n\n" + "\n".join(checks),
        parse_mode="HTML"
    )


@router.message(Command("test_signal"))
async def cmd_test_signal(message: Message):
    """Send test signal to admin only (not to subscribers)."""
    if not is_admin(message):
        await message.answer("❌ Команда недоступна.")
        return
    
    logger.info(
        "admin_action",
        action="test_signal",
        admin_id=message.chat.id
    )
    
    # Send test signal format
    test_message = (
        "🚨 СИГНАЛ | тест | 3/5\n"
        "Регион: Тестовый регион\n"
        "Сфера: ЖКХ\n"
        "Суть: Это тестовый сигнал для проверки формата\n"
        "Почему важно: Проверка работы системы оповещения\n"
        "Источник: https://example.com/test"
    )
    
    await message.answer(test_message)
    await message.answer("✅ Тестовый сигнал отправлен только вам (не подписчикам).")
