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
        "• /sources_add {url} {name} — добавить\n"
        "• /sources_remove {name} — удалить\n\n"
        "<b>Конфигурация:</b>\n"
        "• /config_show — текущие настройки\n"
        "• /config_set {path} {value} — изменить\n"
        "• /reload_config — перечитать конфиг\n\n"
        "<b>Тестирование:</b>\n"
        "• /test_signal — тестовый сигнал (только вам)\n\n"
        "<b>Рассылка:</b>\n"
        "• /broadcast {text} — разослать всем",
        parse_mode="HTML"
    )


@router.message(Command("set_llm_key"))
async def cmd_set_llm_key(message: Message):
    """Set LLM API key override."""
    if not is_admin(message):
        return

    try:
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.reply("Использование: /set_llm_key <KEY>")
            return

        new_key = args[1].strip()
        
        # Save to DB overrides
        from db_pkg import ConfigRepository, get_session
        async with get_session() as session:
            await ConfigRepository.set(session, "openrouter_api_key", new_key, message.chat.id)
            await session.commit()
            
        # Update loader runtime
        from config_loader import get_config_loader
        loader = get_config_loader()
        loader.set_overrides({"openrouter_api_key": new_key})
        
        # Confirm and delete user message for security
        await message.answer("✅ API ключ обновлён и сохранён в overrides.")
        try:
            await message.delete()
        except Exception:
            pass # context manager or private chat issues

    except Exception as e:
        await message.reply(f"Ошибка: {str(e)}")


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Show daily/weekly stats with filter breakdown."""
    if not is_admin(message):
        await message.answer("❌ Команда недоступна.")
        return
    
    logger.info("admin_action", action="stats", admin_id=message.chat.id)
    
    async with get_session() as session:
        # Daily stats
        daily = await NewsRepository.get_stats(session, days=1)
        
        # Weekly stats
        weekly = await NewsRepository.get_stats(session, days=7)
        
        # Signals today
        signals_today = await SignalRepository.count_today(session)
        
        # Subscribers
        subscribers_count = await SubscriberRepository.count_active(session)
    
    # Build filter breakdown
    d = daily.get("by_decision", {})
    breakdown = (
        f"• Старые: {d.get('filtered_old', 0)}\n"
        f"• Завершённые: {d.get('filtered_resolved', 0)}\n"
        f"• Шум: {d.get('filtered_noise', 0)}\n"
        f"• Дубли: {d.get('duplicate', 0)}\n"
        f"• Фильтр1: {d.get('filtered', 0)}\n"
        f"• LLM ошибки: {d.get('llm_failed', 0)}\n"
        f"• LLM пропущен: {d.get('llm_skipped', 0)}\n"
        f"• Лимит: {d.get('suppressed_limit', 0)}"
    )
    
    await message.answer(
        f"📊 <b>Статистика</b>\n\n"
        f"<b>За сутки:</b>\n"
        f"• Собрано: {daily.get('total', 0)}\n"
        f"• Отправлено: {signals_today}\n\n"
        f"<b>Отфильтровано:</b>\n{breakdown}\n\n"
        f"<b>За неделю:</b>\n"
        f"• Собрано: {weekly.get('total', 0)}\n"
        f"• Сигналов: {weekly.get('sent', 0)}\n\n"
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
    
    from llm_monitor import CircuitBreaker, LLMUsageRepository
    
    checks = []
    
    # DB check
    try:
        async with get_session() as session:
            await SubscriberRepository.count_active(session)
        checks.append("✅ БД: ONLINE")
    except Exception as e:
        checks.append(f"❌ БД: ERROR ({str(e)[:20]})")
    
    # Circuit Breaker
    if CircuitBreaker.is_open():
        checks.append("❌ LLM Circuit: OPEN (Broken)")
    else:
        checks.append("✅ LLM Circuit: CLOSED (OK)")
        
    # Stats
    async with get_session() as session:
        subs = await SubscriberRepository.count_active(session)
        signals_today = await SignalRepository.count_today(session)
        daily_cost = await LLMUsageRepository.get_daily_cost(session)
        errors_5m = await LLMUsageRepository.get_recent_errors(session, minutes=5)
    
    checks.append(f"👥 Подписчиков: {subs}")
    checks.append(f"📨 Сигналов: {signals_today}")
    checks.append(f"💰 Расход сегодня: ${daily_cost:.4f}")
    checks.append(f"❗ Ошибок (5мин): {errors_5m}")
    
    await message.answer(
        "🏥 <b>Статус системы (v1.7.0)</b>\n\n" + "\n".join(checks),
        parse_mode="HTML"
    )


@router.message(Command("guardrails"))
async def cmd_guardrails(message: Message):
    """Show strict guardrails stats."""
    if not is_admin(message):
        return

    from llm_monitor import CircuitBreaker, LLMUsageRepository
    
    async with get_session() as session:
        cost = await LLMUsageRepository.get_daily_cost(session)
        errors = await LLMUsageRepository.get_recent_errors(session, minutes=60)
        
    status = "🔴 OPEN (STOPPED)" if CircuitBreaker.is_open() else "🟢 CLOSED (RUNNING)"
    
    await message.answer(
        f"🛡️ <b>LLM Guardrails</b>\n\n"
        f"<b>Circuit Breaker:</b> {status}\n"
        f"<b>Budget (Daily):</b> ${cost:.4f} / $0.00 (Free Tier)\n"
        f"<b>Errors (1h):</b> {errors}\n\n"
        f"<i>Target: $0.00 cost, Free Models Only.</i>",
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


@router.message(Command("src"))
async def cmd_src_search(message: Message):
    """Search sources: /src <query>."""
    if not is_admin(message):
        return

    query = message.text.replace("/src", "").strip().lower()
    if not query:
        await message.answer("ℹ️ Использование: `/src <название>`")
        return

    # Find sources
    config = get_config()
    matches = [s for s in config.sources if query in s.name.lower()]
    
    if not matches:
        await message.answer(f"🔍 Источники по запросу '{query}' не найдены.")
        return
        
    # Render mini-report
    text = f"🔍 <b>Результаты поиска:</b> '{query}'\nFound: {len(matches)}\n\n"
    
    # Generate generic buttons for results (max 5)
    from ui_keyboards import cb, InlineKeyboardMarkup, InlineKeyboardButton
    buttons = []
    
    for s in matches[:5]:
        status = "🟢" if s.is_enabled else "🔴"
        text += f"{status} <b>{s.name}</b> ({s.type})\n"
        
        # Toggle button
        btn = InlineKeyboardButton(
            text=f"Toggle {s.name[:10]}",
            callback_data=cb("sources", "toggle", s.type, 0) # Page 0 context
        )
        buttons.append([btn])
        
    if len(matches) > 5:
        text += f"\n<i>...и ещё {len(matches)-5}</i>"
        
    buttons.append([InlineKeyboardButton(text="❌ Закрыть", callback_data=cb("close"))])
    
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


@router.message(Command("config_export"))
async def cmd_config_export(message: Message):
    """Export overrides as JSON."""
    if not is_admin(message):
        return

    import json
    from io import BytesIO
    from aiogram.types import BufferedInputFile
    
    async with get_session() as session:
        overrides = await ConfigRepository.get_all(session)
        
    if not overrides:
        await message.answer("ℹ️ Нет активных overrides.")
        return
        
    data = json.dumps(overrides, indent=2, ensure_ascii=False)
    file = BufferedInputFile(data.encode("utf-8"), filename="config_overrides.json")
    
    await message.answer_document(file, caption=f"📦 Config Export ({len(overrides)} items)")


@router.message(Command("config_import"))
async def cmd_config_import(message: Message):
    """Import overrides from JSON."""
    if not is_admin(message):
        return
        
    # Check for document
    if not message.reply_to_message or not message.reply_to_message.document:
        await message.answer(
            "ℹ️ Использование: Ответьте на сообщение с файлом .json командой /config_import"
        )
        return
        
    doc = message.reply_to_message.document
    if not doc.file_name.endswith(".json"):
        await message.answer("❌ Файл должен быть .json")
        return
        
    # Download logic (simplified mock, real bot needs bot.download)
    # Since we can't easily download in this env without bot instance reference,
    # we'll simulate the next step or guide the user.
    # In a real scenario:
    # file = await bot.download(doc)
    # content = file.read()
    
    await message.answer("⚠️ Import functionality requires bot instance context (mocked).")
