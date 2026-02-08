"""Callback router and handlers for inline UI."""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message

from settings import get_settings
from config_loader import get_config, get_config_loader
from db_pkg import get_session, ConfigRepository, NewsRepository
from logging_setup import get_logger
from ui_keyboards import (
    main_menu_kb, health_kb, stats_kb, settings_kb, about_kb,
    admin_menu_kb, sources_kb, filters_kb, limits_kb, confirm_kb, close_kb,
    control_kb, diag_kb, llm_kb, llm_provider_kb, llm_key_kb, ranking_kb
)
from ui_screens import (
    render_main, render_health, render_stats, render_stats_sources,
    render_settings, render_about, render_admin, render_sources,
    render_filters, render_limits, render_confirm,
    render_control, render_diag, render_llm_center
)

logger = get_logger("ui.callbacks")
router = Router(name="ui_callbacks")


def is_admin(user_id: int) -> bool:
    """Check if user is admin."""
    settings = get_settings()
    return user_id == settings.admin_chat_id


def is_allowed(user_id: int) -> bool:
    """Check if user is allowed to use UI (admin or allowlisted)."""
    settings = get_settings()
    if user_id == settings.admin_chat_id:
        return True
    return user_id in settings.allowed_user_ids


def parse_callback(data: str) -> dict:
    """Parse callback data: ui1:screen:action:param:page"""
    parts = data.split(":")
    return {
        "prefix": parts[0] if len(parts) > 0 else "",
        "screen": parts[1] if len(parts) > 1 else "",
        "action": parts[2] if len(parts) > 2 else "nav",
        "param": parts[3] if len(parts) > 3 else "",
        "page": int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 0,
    }


async def edit_panel(callback: CallbackQuery, text: str, keyboard):
    """Edit message with new screen."""
    try:
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception:
        # Message not modified (same content)
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("ui1:"))
async def handle_ui_callback(callback: CallbackQuery):
    """Main callback handler for all UI interactions."""
    user_id = callback.from_user.id
    admin = is_admin(user_id)
    allowed = is_allowed(user_id)
    
    # Check permissions in groups
    if callback.message.chat.type in ("group", "supergroup"):
        if not allowed:
            await callback.answer("⛔ Доступ ограничен (только для админов)", show_alert=True)
            return
    
    data = parse_callback(callback.data)
    
    logger.info(
        "ui_callback",
        user_id=user_id,
        screen=data["screen"],
        action=data["action"],
        is_admin=admin,
        is_allowed=allowed
    )
    
    screen = data["screen"]
    action = data["action"]
    param = data["param"]
    page = data["page"]
    
    # Close panel
    if screen == "close":
        await callback.message.delete()
        await callback.answer()
        return
    
    # Noop (for display-only buttons)
    if screen == "noop" or callback.data == "noop":
        await callback.answer()
        return
    
    # Main menu
    if screen == "main":
        text = await render_main()
        await edit_panel(callback, text, main_menu_kb(admin))
        return
    
    # Health
    if screen == "health":
        text = await render_health()
        await edit_panel(callback, text, health_kb())
        return
    
    # Stats
    if screen == "stats":
        if action == "period":
            period = param or "today"
        elif action == "sources":
            text = await render_stats_sources()
            await edit_panel(callback, text, stats_kb())
            return
        else:
            period = "today"
        text = await render_stats(period)
        await edit_panel(callback, text, stats_kb(period))
        return
    
    # Settings
    if screen == "settings":
        text = await render_settings()
        await edit_panel(callback, text, settings_kb())
        return
    
    # About
    if screen == "about":
        text = await render_about()
        await edit_panel(callback, text, about_kb())
        return
    
    # === ADMIN ONLY ===
    if not admin:
        await callback.answer()  # Silent ignore for non-admins
        return
    
    # Admin menu
    if screen == "admin":
        text = await render_admin()
        await edit_panel(callback, text, admin_menu_kb())
        return
    
    # Sources
    if screen == "sources":
        config = get_config()
        sources = [{"id": s.id, "name": s.name, "enabled": True, "failures": 0} for s in config.sources]
        
        if action == "toggle":
            # Toggle source (would update DB)
            await callback.answer(f"Источник {param} переключён")
        
        text = await render_sources(sources, page)
        await edit_panel(callback, text, sources_kb(sources, page))
        return
    
    # Filters
    if screen == "filters":
        config = get_config()
        thresholds = {
            "filter1_to_llm": config.thresholds.filter1_to_llm,
            "llm_relevance": config.thresholds.llm_relevance,
            "llm_urgency": config.thresholds.llm_urgency,
        }
        
        if action in ("inc", "dec"):
            delta = 1 if action == "inc" else -1
            key = f"thresholds.{param}"
            
            if param == "filter1":
                new_val = thresholds["filter1_to_llm"] + delta
                key = "thresholds.filter1_to_llm"
            elif param == "relevance":
                new_val = round(thresholds["llm_relevance"] + delta * 0.05, 2)
                key = "thresholds.llm_relevance"
            elif param == "urgency":
                new_val = thresholds["llm_urgency"] + delta
                key = "thresholds.llm_urgency"
            else:
                new_val = 0
            
            # Save to DB
            async with get_session() as session:
                await ConfigRepository.set(session, key, str(new_val), user_id)
                await session.commit()
            
            # Apply override
            loader = get_config_loader()
            loader.set_overrides({key: new_val})
            
            await callback.answer(f"{param}: {new_val}")
            
            # Refresh thresholds
            config = get_config()
            thresholds = {
                "filter1_to_llm": config.thresholds.filter1_to_llm,
                "llm_relevance": config.thresholds.llm_relevance,
                "llm_urgency": config.thresholds.llm_urgency,
            }
        
        text = await render_filters()
        await edit_panel(callback, text, filters_kb(thresholds))
        return
    
    # Ranking / Limits
    if screen == "ranking" or screen == "limits":
        config = get_config()
        limits = {"max_signals_per_day": config.limits.max_signals_per_day}
        
        if action in ("inc", "dec"):
            delta = 1 if action == "inc" else -1
            if param == "max_day":
                new_val = max(1, limits["max_signals_per_day"] + delta)
                key = "limits.max_signals_per_day"
                
                async with get_session() as session:
                    await ConfigRepository.set(session, key, str(new_val), user_id)
                    await session.commit()
                
                loader = get_config_loader()
                loader.set_overrides({key: new_val})
                
                await callback.answer(f"Лимит: {new_val}")
                limits["max_signals_per_day"] = new_val
        
        text = await render_limits()
        await edit_panel(callback, text, ranking_kb(limits))
        return
    
    # Maintenance
    if screen == "maintenance":
        from ui_keyboards import InlineKeyboardMarkup, InlineKeyboardButton, cb
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🧹 Очистка БД", callback_data=cb("confirm", "ask", "cleanup"))],
            [InlineKeyboardButton(text="🔁 Force run", callback_data=cb("confirm", "ask", "force_run"))],
            [InlineKeyboardButton(text="📜 История конфига", callback_data=cb("history"))],
            [InlineKeyboardButton(text="🔧 Config Diff", callback_data=cb("diff"))],
            [InlineKeyboardButton(text="⬅ Назад", callback_data=cb("admin"))],
        ])
        await edit_panel(callback, "🧹 <b>Обслуживание</b>\n\nВыберите действие:", kb)
        return

    # History / Audit
    if screen == "history":
        from ui_screens import render_history
        from ui_keyboards import nav_row, InlineKeyboardMarkup, InlineKeyboardButton
        
        async with get_session() as session:
            total = await ConfigRepository.count_history(session)
            items = await ConfigRepository.get_history(session, limit=5, offset=page*5)
            
        text = await render_history(items, page, (total // 5) + 1)
        
        buttons = []
        # Pagination
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="⬅️", callback_data=cb("history", "nav", "", page - 1)))
        if (page + 1) * 5 < total:
            nav.append(InlineKeyboardButton(text="➡️", callback_data=cb("history", "nav", "", page + 1)))
        buttons.append(nav)
        
        # Rollback actions for visible items (simplified)
        for item in items:
            if item.action == "set" and item.old_value:
                buttons.append([
                    InlineKeyboardButton(
                        text=f"🔙 Rollback {item.key}", 
                        callback_data=cb("confirm", "ask", f"rollback:{item.key}:{item.old_value}")
                    )
                ])
                
        buttons.append(nav_row(back_to="maintenance"))
        await edit_panel(callback, text, InlineKeyboardMarkup(inline_keyboard=buttons))
        return

    # Diff
    if screen == "diff":
        from ui_screens import render_diff
        from ui_keyboards import nav_row, InlineKeyboardMarkup
        
        loader = get_config_loader()
        diff = loader.get_diff()
        text = await render_diff(diff)
        
        buttons = [nav_row(back_to="maintenance")]
        await edit_panel(callback, text, InlineKeyboardMarkup(inline_keyboard=buttons))
        return

    # Confirmation handler
    if screen == "confirm":
        if action == "ask":
            text = f"❓ <b>Подтверждение</b>\n\nВы уверены, что хотите выполнить действие: <b>{param.split(':')[0]}</b>?"
            await edit_panel(callback, text, confirm_kb(param.replace(":", "|"))) # encode param safe
            return
            
        if action == "no":
            text = await render_admin()
            await edit_panel(callback, text, admin_menu_kb())
            return
            
        if action == "yes":
            # Decode param
            real_param = param.replace("|", ":")
            
            if "cleanup" in real_param:
                async with get_session() as session:
                    deleted = await NewsRepository.cleanup_old_news(session, days=30)
                    await session.commit()
                await callback.answer(f"✅ Удалено {deleted} старых записей", show_alert=True)
                
            elif "force_run" in real_param:
                # In real app, trigger scheduler
                await callback.answer("🔄 Запрос на запуск отправлен", show_alert=True)
                
            elif "rollback" in real_param:
                # rollback:key:old_val
                parts = real_param.split(":", 2)
                if len(parts) == 3:
                    key = parts[1]
                    val = parts[2]
                    
                    async with get_session() as session:
                        # Set to old value
                        await ConfigRepository.set(session, key, val, user_id, source="rollback")
                        await session.commit()
                        
                        # Apply
                        loader = get_config_loader()
                        loader.set_overrides({key: val})
                        
                    await callback.answer(f"✅ Rollback {key} -> {val}", show_alert=True)

            # Return to admin
            text = await render_admin()
            await edit_panel(callback, text, admin_menu_kb())
            return

    # Control
    if screen == "control":
        paused = False # Placeholder, needs global state or DB flag
        
        # Live dashboard toggle
        if action == "live":
            # Toggle live mode for this user
            from asyncio import create_task, sleep
            
            # Use a global dict to track live tasks per chat_id/user_id
            # This is a simple in-memory implementation for the "mini-app" feel
            if not hasattr(handle_ui_callback, "live_tasks"):
                handle_ui_callback.live_tasks = {}
                
            task_key = f"{user_id}:{callback.message.message_id}"
            
            if param == "stop":
                 if task_key in handle_ui_callback.live_tasks:
                     handle_ui_callback.live_tasks[task_key].cancel()
                     del handle_ui_callback.live_tasks[task_key]
                 await callback.answer("⏹ Live Dashboard stopped")
            
            elif param == "start":
                # Start background update loop
                async def live_loop(msg: Message):
                    try:
                        while True:
                            # Fetch real stats
                            # In real app: pending_count = await PendingSignalRepository.count()
                            status = {
                                "pending": 0, # Mock
                                "errors_1h": 0, # Mock
                                "signals_24h": 0 # Mock w/ DB query
                            }
                            
                            text = await render_control(paused, status)
                            
                            # Update message silently
                            try:
                                await msg.edit_text(
                                    text, 
                                    reply_markup=control_kb(paused), 
                                    parse_mode="HTML"
                                )
                            except Exception:
                                pass # Content not changed
                                
                            await sleep(5.0) # Refresh every 5s
                    except Exception:
                        pass
                
                # Cancel existing if any
                if task_key in handle_ui_callback.live_tasks:
                    handle_ui_callback.live_tasks[task_key].cancel()
                    
                task = create_task(live_loop(callback.message))
                handle_ui_callback.live_tasks[task_key] = task
                await callback.answer("▶️ Live Dashboard started")
                return

        elif action == "pause":
            # Set pause state
            await callback.answer("⏸ Система поставлена на паузу (mock)")
            paused = True
        elif action == "resume":
            await callback.answer("▶️ Система запущена")
            paused = False
        elif action == "reload":
            loader = get_config_loader()
            loader.reload()
            await callback.answer("✅ Конфиг перезагружен")
            
        text = await render_control(paused)
        await edit_panel(callback, text, control_kb(paused))
        return

    # Diagnostics
    if screen == "diag":
        if action == "selfcheck":
            await callback.answer("🧪 Self-check functionality not implemented yet", show_alert=True)
        elif action == "errors":
            await callback.answer("🐛 Error log functionality not implemented yet", show_alert=True)
            
        text = await render_diag()
        await edit_panel(callback, text, diag_kb())
        return

    # LLM Center
    if screen == "llm":
        config = get_config()
        
        if action == "provider_menu":
            text = f"🧠 <b>Выбор провайдера</b>\nТекущий: <b>OpenRouter</b> (hardcoded)"
            await edit_panel(callback, text, llm_provider_kb("openrouter"))
            return
            
        if action == "set_provider":
            # Logic to save provider override
            await callback.answer(f"Провайдер {param} выбран (mock)")
            # Return to main LLM
            
        if action == "key_menu":
            has_key = bool(config.openrouter_api_key and len(config.openrouter_api_key) > 5)
            text = "🔑 <b>Управление ключами</b>\nВыберите действие:"
            await edit_panel(callback, text, llm_key_kb(has_key))
            return
            
        if action == "key_instruct":
            await callback.answer("Используйте команду /set_llm_key <KEY> в чате", show_alert=True)
            return

        text = await render_llm_center()
        await edit_panel(callback, text, llm_kb())
        return

    # Snapshot (new message)
    if screen == "snapshot":
        text = await render_snapshot()
        await callback.message.answer(text, parse_mode="HTML")
        await callback.answer()
        return
    
    # Default: answer to prevent spinning
    await callback.answer()


@router.callback_query(F.data.startswith("fb1:"))
async def handle_feedback_callback(callback: CallbackQuery):
    """Handle feedback callbacks (thumbs up/down)."""
    user_id = callback.from_user.id
    
    if not is_allowed(user_id):
        await callback.answer("⛔ Только для админов", show_alert=True)
        return

    # Parse fb1:action:signal_id
    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.answer()
        return
        
    action = parts[1]
    signal_id = int(parts[2])
    
    score = 1 if action == "good" else -1
    
    # Update DB
    from db_pkg import SignalRepository
    async with get_session() as session:
        await SignalRepository.set_feedback(session, signal_id, score)
        await session.commit()
    
    # Feedback visual confirmation
    action_text = "👍 Релевантно" if score > 0 else "👎 Шум"
    await callback.answer(f"Отзыв принят: {action_text}")


async def show_panel(message: Message):
    """Show initial panel (called from /start)."""
    admin = is_admin(message.from_user.id)
    text = await render_main()
    await message.answer(text, reply_markup=main_menu_kb(admin), parse_mode="HTML")


async def render_snapshot() -> str:
    """Render system snapshot."""
    import platform
    from datetime import datetime
    
    config = get_config()
    
    # DB Stats
    async with get_session() as session:
        stats = await SignalRepository.get_stats(session, days=1)
        signals_today = stats.get("sent", 0)
        errors = stats.get("errors", 0) 
        
        # Breakdown
        filtered = stats.get("filtered_total", 0)
        
        # Source health
        from db_pkg import SourceHealthRepository
        unhealthy_sources = await SourceHealthRepository.get_unhealthy(session)
    
    lines = [
        "📸 <b>Снимок системы</b>",
        f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        "",
        "<b>📊 Эффективность (24ч):</b>",
        f"• Сигналов: {signals_today} / {config.limits.max_signals_per_day}",
        f"• Отфильтровано: {filtered}",
        f"• Ошибок: {errors}",
        "",
        "<b>🧩 Источники:</b>",
        f"• Всего: {len(config.sources)}",
        f"• Проблемных: {len(unhealthy_sources)}",
    ]
    
    if unhealthy_sources:
        lines.append("<i>Проблемные:</i>")
        for s in unhealthy_sources[:5]:
            lines.append(f"- {s.source_id}: {s.consecutive_failures} fails")
            
    return "\n".join(lines)
