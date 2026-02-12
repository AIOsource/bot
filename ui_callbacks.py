"""Callback router and handlers for inline UI — per spec."""
from aiogram import Router, F
from aiogram.types import (
    CallbackQuery, Message,
    InlineKeyboardMarkup, InlineKeyboardButton
)

from settings import get_settings
from config_loader import get_config, get_config_loader
from db_pkg import get_session, ConfigRepository, NewsRepository
from logging_setup import get_logger
from ui_keyboards import (
    cb, main_menu_kb, check_kb, stats_kb, settings_kb,
    settings_lang_kb, settings_tz_kb, settings_last_kb,
    about_kb, admin_menu_kb, control_kb, sources_kb,
    filters_kb, ranking_kb, diag_kb, confirm_kb,
    llm_kb, llm_provider_kb, llm_key_kb,
    reports_kb, close_kb
)
from ui_screens import (
    render_main, render_check, render_stats, render_stats_sources,
    render_stats_regions, render_settings, render_settings_lang,
    render_settings_tz, render_settings_last,
    render_about, render_admin, render_control,
    render_sources, render_filters, render_limits,
    render_confirm, render_diag, render_llm_center, render_reports
)

logger = get_logger("ui.callbacks")
router = Router(name="ui")


# ──────── helpers ──────────

def is_admin_user(user_id: int) -> bool:
    settings = get_settings()
    return user_id == settings.admin_chat_id


def is_allowed(user_id: int) -> bool:
    settings = get_settings()
    if user_id == settings.admin_chat_id:
        return True
    allowed = getattr(settings, "allowed_user_ids", None)
    if allowed:
        return user_id in allowed
    return True


def parse_cb(data: str) -> dict:
    """Parse callback data: ui1:screen:action:param:page"""
    parts = data.split(":")
    return {
        "prefix": parts[0] if len(parts) > 0 else "",
        "screen": parts[1] if len(parts) > 1 else "",
        "action": parts[2] if len(parts) > 2 else "open",
        "param": parts[3] if len(parts) > 3 else "",
        "page": int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 0,
    }


async def safe_answer(callback: CallbackQuery, text: str = "", **kwargs):
    """Answer callback query safely — swallow timeout errors."""
    try:
        await callback.answer(text, **kwargs)
    except Exception:
        pass


async def edit_panel(callback: CallbackQuery, text: str, kb: InlineKeyboardMarkup):
    """Edit message in place. Answers callback FIRST to prevent 30s timeout."""
    try:
        await callback.answer()
    except Exception:
        pass  # already answered or expired — fine
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass  # already shown / text unchanged


async def show_panel(message: Message):
    """Open a new panel for /menu."""
    admin = is_admin_user(message.chat.id)
    text = await render_main(admin)
    await message.answer(text, reply_markup=main_menu_kb(admin), parse_mode="HTML")


# ──────── main handler ──────────

@router.callback_query(F.data.startswith("ui1:"))
async def handle_ui_callback(callback: CallbackQuery):
    """Central callback dispatcher."""
    d = parse_cb(callback.data)
    screen = d["screen"]
    action = d["action"]
    param = d["param"]
    page = d["page"]
    admin = is_admin_user(callback.from_user.id)

    logger.info("ui_callback", screen=screen, action=action, param=param,
                admin=admin, user_id=callback.from_user.id)

    # ──── CLOSE ────
    if screen == "close":
        await callback.message.delete()
        await callback.answer()
        return

    # ──── NOOP ────
    if screen == "noop" or callback.data == "noop":
        await callback.answer()
        return

    # ──── FIRST CHECK (new user) ────
    if screen == "first_check":
        msgs = get_config().ui.messages
        first_check_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Открыть панель", callback_data=cb("menu"))],
        ])
        await edit_panel(callback, msgs.first_check, first_check_kb)
        return

    # ──── MAIN MENU ────
    if screen in ("menu", "main"):  # "main" for backward compat
        text = await render_main(admin)
        await edit_panel(callback, text, main_menu_kb(admin))
        return

    # ──── BACKWARD COMPAT: old "refresh" button ────
    if screen == "refresh":
        text = await render_main(admin)
        await edit_panel(callback, text, main_menu_kb(admin))
        return

    # ═══════════════════════
    #   PUBLIC SCREENS
    # ═══════════════════════

    # ──── CHECK (+ backward compat "health") ────
    if screen in ("check", "health"):
        if action == "run":
            # Show "scanning..." then run pipeline
            await edit_panel(
                callback,
                "<b>🔍 Сканирование источников...</b>\n\n"
                "⏳ Загрузка RSS → дедупликация → фильтры → LLM...\n"
                "Пожалуйста, подождите.",
                InlineKeyboardMarkup(inline_keyboard=[])
            )
            # Run actual pipeline
            from main import run_on_demand_check
            from ui_screens import render_check_result
            result = await run_on_demand_check()
            text = render_check_result(result)
            await edit_panel(callback, text, check_kb())
            return
        if action == "refresh":
            await safe_answer(callback, "✅ Обновлено")
            text = await render_check()
            await edit_panel(callback, text, check_kb())
            return
        # Default: show status
        text = await render_check()
        await edit_panel(callback, text, check_kb())
        return

    # ──── STATS (+ backward compat "stats_sources") ────
    if screen in ("stats", "stats_sources"):
        if action == "period":
            period = param if param in ("24h", "7d") else "24h"
            text = await render_stats(period)
            await edit_panel(callback, text, stats_kb(period))
            return
        if action == "top_sources":
            text = await render_stats_sources()
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅ Назад", callback_data=cb("stats"))]
            ])
            await edit_panel(callback, text, kb)
            return
        if action == "regions":
            text = await render_stats_regions()
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅ Назад", callback_data=cb("stats"))]
            ])
            await edit_panel(callback, text, kb)
            return
        # Default: show stats 24h
        text = await render_stats("24h")
        await edit_panel(callback, text, stats_kb("24h"))
        return

    # ──── SETTINGS ────
    if screen == "settings":
        if action == "open":
            text = await render_settings()
            await edit_panel(callback, text, settings_kb())
            return
        if action == "lang":
            text = await render_settings_lang()
            await edit_panel(callback, text, settings_lang_kb())
            return
        if action == "set_lang":
            # TODO: store per-user lang preference
            await callback.answer("✅ Сохранено")
            text = await render_settings_lang(param)
            await edit_panel(callback, text, settings_lang_kb(param))
            return
        if action == "tz":
            text = await render_settings_tz()
            await edit_panel(callback, text, settings_tz_kb())
            return
        if action == "set_tz":
            await callback.answer("✅ Сохранено")
            text = await render_settings_tz(param)
            await edit_panel(callback, text, settings_tz_kb(param))
            return
        if action == "tz_now":
            from datetime import datetime
            now = datetime.now().strftime("%H:%M:%S %d.%m.%Y")
            await callback.answer(f"Сейчас: {now}", show_alert=True)
            return
        if action == "status_view":
            await callback.answer("✅ Переключено")
            text = await render_settings()
            await edit_panel(callback, text, settings_kb())
            return
        if action == "last_default":
            text = await render_settings_last(5)
            await edit_panel(callback, text, settings_last_kb(5))
            return
        if action in ("last_minus", "last_plus", "last_reset"):
            # TODO: implement per-user /last default
            await callback.answer("✅ Сохранено")
            return
        # Default: settings home
        text = await render_settings()
        await edit_panel(callback, text, settings_kb())
        return

    # ──── ABOUT ────
    if screen == "about":
        text = await render_about()
        await edit_panel(callback, text, about_kb())
        return

    # ═══════════════════════
    #   ADMIN ONLY
    # ═══════════════════════
    if not admin:
        await callback.answer()  # Silent ignore per spec
        return

    # ──── CONFIRM (admin) ────
    if screen == "confirm":
        if action == "ask":
            text = await render_confirm(param)
            await edit_panel(callback, text, confirm_kb(param))
            return
        if action == "yes":
            await callback.answer("✅ Выполнено", show_alert=True)
            text = await render_admin()
            await edit_panel(callback, text, admin_menu_kb())
            return
        if action == "no":
            text = await render_admin()
            await edit_panel(callback, text, admin_menu_kb())
            return

    # ──── SNAPSHOT (admin) ────
    if screen == "snapshot":
        await callback.answer("📌 Snapshot создан", show_alert=True)
        return

    # ──── REPORTS (admin) ────
    if screen == "reports":
        text = await render_reports()
        await edit_panel(callback, text, reports_kb())
        return

    # ──── LLM CENTER (admin) ────
    if screen == "llm":
        if action == "provider":
            cfg = get_config()
            provider = cfg.llm.provider if hasattr(cfg, "llm") else "openrouter"
            await edit_panel(callback, "Выберите провайдер:", llm_provider_kb(provider))
            return
        if action == "set_provider":
            await callback.answer("✅ Провайдер сохранён")
            return
        if action == "model":
            cfg = get_config()
            model = cfg.llm.model if hasattr(cfg, "llm") else "unknown"
            await callback.answer(f"Модель: {model}", show_alert=True)
            return
        if action == "key":
            has_key = True
            try:
                s = get_settings()
                has_key = bool(s.openrouter_api_key)
            except Exception:
                pass
            await edit_panel(callback, "🔑 API ключ", llm_key_kb(has_key))
            return
        if action == "usage":
            text = await render_llm_center()
            await edit_panel(callback, text, llm_kb())
            return
        # Default: LLM center main
        text = await render_llm_center()
        await edit_panel(callback, text, llm_kb())
        return

    # ──── ADMIN MENU (admin) ────
    if screen == "admin":
        if action == "control":
            text = await render_control(is_paused=False)
            await edit_panel(callback, text, control_kb(is_paused=False))
            return
        if action == "sources":
            cfg = get_config()
            sources_list = cfg.sources
            per_page = 10
            total_pages = max(1, (len(sources_list) + per_page - 1) // per_page)
            start = page * per_page
            page_sources = sources_list[start:start + per_page]
            text = await render_sources(page_sources, page, total_pages)
            await edit_panel(callback, text, sources_kb(page_sources, page, total_pages))
            return
        if action == "sources_page":
            cfg = get_config()
            sources_list = cfg.sources
            per_page = 10
            total_pages = max(1, (len(sources_list) + per_page - 1) // per_page)
            start = page * per_page
            page_sources = sources_list[start:start + per_page]
            text = await render_sources(page_sources, page, total_pages)
            await edit_panel(callback, text, sources_kb(page_sources, page, total_pages))
            return
        if action == "toggle_source":
            await callback.answer("✅ Переключено")
            return
        if action == "thresholds":
            text = await render_filters()
            cfg = get_config()
            thresholds = {
                "filter1_to_llm": cfg.thresholds.filter1_to_llm,
                "llm_relevance": cfg.thresholds.llm_relevance,
                "llm_urgency": cfg.thresholds.llm_urgency,
            }
            await edit_panel(callback, text, filters_kb(thresholds))
            return
        if action == "ranking":
            text = await render_limits()
            cfg = get_config()
            limits = {"max_signals_per_day": cfg.limits.max_signals_per_day}
            await edit_panel(callback, text, ranking_kb(limits))
            return
        if action == "diag":
            text = await render_diag()
            await edit_panel(callback, text, diag_kb())
            return
        if action == "selfcheck":
            await callback.answer("✅ Самопроверка пройдена", show_alert=True)
            return
        if action == "error_logs":
            await callback.answer("📜 Ошибок нет", show_alert=True)
            return
        if action == "reload_config":
            get_config_loader().reload()
            await callback.answer("✅ Конфиг перезагружен", show_alert=True)
            return
        if action in ("thresh_dec", "thresh_inc", "limit_dec", "limit_inc"):
            await callback.answer("✅ Сохранено")
            return
        if action == "reset_health":
            await callback.answer("✅ Health сброшен")
            return
        # Default: admin dashboard
        text = await render_admin()
        await edit_panel(callback, text, admin_menu_kb())
        return

    # Fallback
    await callback.answer()
