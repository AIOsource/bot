"""Keyboards for UI — per UI spec."""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def cb(screen: str, action: str = "open", param: str = "", page: int = 0) -> str:
    """Build callback data string."""
    return f"ui1:{screen}:{action}:{param}:{page}"


def nav_row(back_to: str = "menu") -> list[InlineKeyboardButton]:
    """Standard back row."""
    return [
        InlineKeyboardButton(text="⬅ Назад", callback_data=cb(back_to))
    ]


# ──────────────────────────────────────
# PUBLIC MENU
# ──────────────────────────────────────

def main_menu_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    """Main menu — одинаковый layout, админ-ряд только для админов."""
    buttons = [
        [
            InlineKeyboardButton(text="✅ Проверить", callback_data=cb("check")),
            InlineKeyboardButton(text="📊 Статистика", callback_data=cb("stats")),
        ],
        [
            InlineKeyboardButton(text="⚙️ Настройки", callback_data=cb("settings")),
            InlineKeyboardButton(text="ℹ️ Об авторе", callback_data=cb("about")),
        ],
    ]
    if is_admin:
        buttons.append([
            InlineKeyboardButton(text="🔐 Админка", callback_data=cb("admin")),
            InlineKeyboardButton(text="🧠 LLM Center", callback_data=cb("llm")),
        ])
    buttons.append([
        InlineKeyboardButton(text="✖ Закрыть", callback_data=cb("close"))
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ──────────────────────────────────────
# CHECK (Public Health)
# ──────────────────────────────────────

def check_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Запустить проверку", callback_data=cb("check", "run"))],
        [InlineKeyboardButton(text="↻ Обновить статус", callback_data=cb("check", "refresh"))],
        nav_row("menu"),
    ])


# ──────────────────────────────────────
# STATS
# ──────────────────────────────────────

def stats_kb(period: str = "24h") -> InlineKeyboardMarkup:
    periods = [("24ч", "24h"), ("7д", "7d")]
    period_btns = []
    for label, p in periods:
        marker = "▪️" if p == period else "▫️"
        period_btns.append(
            InlineKeyboardButton(text=f"{marker} {label}", callback_data=cb("stats", "period", p))
        )
    return InlineKeyboardMarkup(inline_keyboard=[
        period_btns,
        [
            InlineKeyboardButton(text="Топ источники", callback_data=cb("stats", "top_sources")),
            InlineKeyboardButton(text="По регионам", callback_data=cb("stats", "regions")),
        ],
        nav_row("menu"),
    ])


# ──────────────────────────────────────
# SETTINGS  (public, per-user)
# ──────────────────────────────────────

def settings_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌐 Язык", callback_data=cb("settings", "lang")),
            InlineKeyboardButton(text="🕑 Время (TZ)", callback_data=cb("settings", "tz")),
        ],
        [
            InlineKeyboardButton(text="📋 Вид /status", callback_data=cb("settings", "status_view")),
            InlineKeyboardButton(text="📨 /last по умолч.", callback_data=cb("settings", "last_default")),
        ],
        nav_row("menu"),
    ])


def settings_lang_kb(current: str = "ru") -> InlineKeyboardMarkup:
    ru_mark = " ✅" if current == "ru" else ""
    en_mark = " ✅" if current == "en" else ""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"RU{ru_mark}", callback_data=cb("settings", "set_lang", "ru")),
            InlineKeyboardButton(text=f"EN{en_mark}", callback_data=cb("settings", "set_lang", "en")),
        ],
        nav_row("settings"),
    ])


def settings_tz_kb(current: str = "msk") -> InlineKeyboardMarkup:
    msk_mark = " ✅" if current == "msk" else ""
    utc_mark = " ✅" if current == "utc" else ""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"MSK{msk_mark}", callback_data=cb("settings", "set_tz", "msk")),
            InlineKeyboardButton(text=f"UTC{utc_mark}", callback_data=cb("settings", "set_tz", "utc")),
        ],
        [InlineKeyboardButton(text="Показать текущее время", callback_data=cb("settings", "tz_now"))],
        nav_row("settings"),
    ])


def settings_last_kb(n: int = 5) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➖", callback_data=cb("settings", "last_minus")),
            InlineKeyboardButton(text=f"/last = {n}", callback_data="noop"),
            InlineKeyboardButton(text="➕", callback_data=cb("settings", "last_plus")),
        ],
        [InlineKeyboardButton(text="Сброс", callback_data=cb("settings", "last_reset"))],
        nav_row("settings"),
    ])


# ──────────────────────────────────────
# ABOUT
# ──────────────────────────────────────

def about_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        nav_row("menu"),
        [InlineKeyboardButton(text="✖ Закрыть", callback_data=cb("close"))],
    ])


# ──────────────────────────────────────
# ADMIN
# ──────────────────────────────────────

def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🚦 Управление", callback_data=cb("admin", "control")),
            InlineKeyboardButton(text="🧩 Источники", callback_data=cb("admin", "sources")),
        ],
        [
            InlineKeyboardButton(text="🧮 Пороги", callback_data=cb("admin", "thresholds")),
            InlineKeyboardButton(text="🏁 Лимиты", callback_data=cb("admin", "ranking")),
        ],
        [
            InlineKeyboardButton(text="🧪 Диагностика", callback_data=cb("admin", "diag")),
            InlineKeyboardButton(text="📝 Отчёты", callback_data=cb("reports")),
        ],
        nav_row("menu"),
    ])


def control_kb(is_paused: bool) -> InlineKeyboardMarkup:
    toggle_text = "▶️ Резюм" if is_paused else "⏸ Пауза"
    toggle_action = "toggle_pipeline"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=toggle_text, callback_data=cb("confirm", "ask", toggle_action)),
            InlineKeyboardButton(text="🔄 Reload config", callback_data=cb("admin", "reload_config")),
        ],
        [
            InlineKeyboardButton(text="🔁 Force run", callback_data=cb("confirm", "ask", "force_run")),
            InlineKeyboardButton(text="📌 Snapshot", callback_data=cb("snapshot", "create")),
        ],
        nav_row("admin"),
    ])


def sources_kb(sources: list, page: int, total_pages: int = 1) -> InlineKeyboardMarkup:
    buttons = []
    for s in sources:
        if isinstance(s, dict):
            enabled = s.get("enabled", True)
            name = s.get("name", "?")[:22]
            sid = s.get("id", "")
            fails = s.get("failures", 0)
        else:
            enabled = getattr(s, "is_enabled", True)
            name = getattr(s, "name", "?")[:22]
            sid = getattr(s, "id", "")
            fails = getattr(s, "consecutive_failures", 0)

        icon = "🟢" if enabled else "🔴"
        label = f"{icon} {name}"
        if fails:
            label += f" ⚠{fails}"
        buttons.append([
            InlineKeyboardButton(text=label, callback_data=cb("admin", "toggle_source", sid, page))
        ])

    # Pagination
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=cb("admin", "sources_page", "prev", page - 1)))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=cb("admin", "sources_page", "next", page + 1)))
    if nav:
        buttons.append(nav)

    buttons.append([
        InlineKeyboardButton(text="🔄 Reset health", callback_data=cb("admin", "reset_health"))
    ])
    buttons.append(nav_row("admin"))
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def filters_kb(current_thresholds: dict) -> InlineKeyboardMarkup:
    def btn_row(label, key, val):
        return [
            InlineKeyboardButton(text=f"{label}: {val}", callback_data="noop"),
            InlineKeyboardButton(text="➖", callback_data=cb("admin", "thresh_dec", key)),
            InlineKeyboardButton(text="➕", callback_data=cb("admin", "thresh_inc", key)),
        ]
    buttons = [
        btn_row("Filter1", "filter1", current_thresholds.get("filter1_to_llm", 4)),
        btn_row("Relevance", "relevance", current_thresholds.get("llm_relevance", 0.6)),
        btn_row("Urgency", "urgency", current_thresholds.get("llm_urgency", 3)),
    ]
    buttons.append(nav_row("admin"))
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def ranking_kb(limits: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"Макс/день: {limits.get('max_signals_per_day', 5)}", callback_data="noop"),
            InlineKeyboardButton(text="➖", callback_data=cb("admin", "limit_dec", "max_day")),
            InlineKeyboardButton(text="➕", callback_data=cb("admin", "limit_inc", "max_day")),
        ],
        nav_row("admin"),
    ])

limits_kb = ranking_kb


def diag_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🧪 Самопроверка", callback_data=cb("admin", "selfcheck")),
            InlineKeyboardButton(text="📜 Журнал ошибок", callback_data=cb("admin", "error_logs")),
        ],
        nav_row("admin"),
    ])


def confirm_kb(action: str, param: str = "") -> InlineKeyboardMarkup:
    payload = f"{action}:{param}" if param else action
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=cb("confirm", "yes", payload)),
            InlineKeyboardButton(text="❌ Отмена", callback_data=cb("confirm", "no", payload)),
        ]
    ])


# ──────────────────────────────────────
# LLM CENTER (Admin only)
# ──────────────────────────────────────

def llm_kb(stats: dict = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚙️ Провайдер", callback_data=cb("llm", "provider")),
            InlineKeyboardButton(text="🤖 Модель", callback_data=cb("llm", "model")),
        ],
        [
            InlineKeyboardButton(text="🔑 Ключ API", callback_data=cb("llm", "key")),
            InlineKeyboardButton(text="📈 Usage", callback_data=cb("llm", "usage")),
        ],
        nav_row("menu"),
    ])


def llm_provider_kb(current: str = "openrouter") -> InlineKeyboardMarkup:
    providers = ["openrouter", "perplexity", "openai"]
    buttons = []
    for p in providers:
        icon = "✅" if p == current else "⚪"
        buttons.append([
            InlineKeyboardButton(text=f"{icon} {p}", callback_data=cb("llm", "set_provider", p))
        ])
    buttons.append(nav_row("llm"))
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def llm_key_kb(has_key: bool) -> InlineKeyboardMarkup:
    status = "✅ Подключен" if has_key else "❌ Отсутствует"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Статус: {status}", callback_data="noop")],
        [InlineKeyboardButton(text="Ввод: /set_llm_key <KEY>", callback_data="noop")],
        nav_row("llm"),
    ])


def reports_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↻ Обновить", callback_data=cb("reports", "refresh"))],
        nav_row("admin"),
    ])


def close_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✖ Закрыть", callback_data=cb("close"))]
    ])


# ── Health (kept for backward compat) ──
health_kb = check_kb
