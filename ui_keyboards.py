"""Keyboards for UI specific interactions."""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def cb(screen: str, action: str = "nav", param: str = "", page: int = 0) -> str:
    """Build callback data string."""
    return f"ui1:{screen}:{action}:{param}:{page}"


def nav_row(back_to: str = "admin") -> list[InlineKeyboardButton]:
    """Standard navigation row: Home | Refresh | Back."""
    return [
        InlineKeyboardButton(text="🏠 Домой", callback_data=cb("main")),
        InlineKeyboardButton(text="↻ Обновить", callback_data=cb("refresh")), # handled generally or contextually
        InlineKeyboardButton(text="↩️ Назад", callback_data=cb(back_to))
    ]


def main_menu_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    """Main menu keyboard."""
    buttons = [
        [
            InlineKeyboardButton(text="❤️ Проверка", callback_data=cb("health")),
            InlineKeyboardButton(text="📊 Статистика", callback_data=cb("stats")),
        ],
        [
            InlineKeyboardButton(text="⚙️ Настройки", callback_data=cb("settings")),
            InlineKeyboardButton(text="ℹ️ О боте", callback_data=cb("about")),
        ]
    ]
    
    if is_admin:
        buttons.append([
            InlineKeyboardButton(text="🔐 Админка", callback_data=cb("admin"))
        ])
    
    # Refresh button for main menu (no back button needed here)
    buttons.append([InlineKeyboardButton(text="↻ Обновить", callback_data=cb("refresh"))])
        
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def health_kb() -> InlineKeyboardMarkup:
    """Health check actions."""
    buttons = [
        [InlineKeyboardButton(text="🔄 Проверить снова", callback_data=cb("health", "refresh"))],
        [InlineKeyboardButton(text="🏠 На главную", callback_data=cb("main"))]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def stats_kb() -> InlineKeyboardMarkup:
    """Stats actions."""
    buttons = [
        [InlineKeyboardButton(text="📋 Источники", callback_data=cb("stats_sources"))],
        [InlineKeyboardButton(text="🏠 На главную", callback_data=cb("main"))]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def settings_kb(current_tz: str) -> InlineKeyboardMarkup:
    """Settings actions."""
    buttons = [
        [
            InlineKeyboardButton(text="🕑 Часовой пояс", callback_data=cb("settings", "tz")),
            InlineKeyboardButton(text="🇷🇺 Язык (RU)", callback_data="noop"),
        ],
        [InlineKeyboardButton(text="🏠 На главную", callback_data=cb("main"))]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def about_kb() -> InlineKeyboardMarkup:
    """About actions."""
    buttons = [
        [InlineKeyboardButton(text="🏠 На главную", callback_data=cb("main"))]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# === ADMIN UI ===

def admin_menu_kb() -> InlineKeyboardMarkup:
    """Admin main menu."""
    buttons = [
        [
            InlineKeyboardButton(text="🚦 Управление (Control)", callback_data=cb("control")),
            InlineKeyboardButton(text="🧩 Источники (Sources)", callback_data=cb("sources")),
        ],
        [
            InlineKeyboardButton(text="🧠 LLM Center", callback_data=cb("llm")),
            InlineKeyboardButton(text="🧮 Фильтры (Filters)", callback_data=cb("filters")),
        ],
        [
            InlineKeyboardButton(text="📊 Диагностика (Diag)", callback_data=cb("diag")),
            InlineKeyboardButton(text="🚥 Лимиты (Ranking)", callback_data=cb("ranking")),
        ],
        [InlineKeyboardButton(text="📝 Reports (Not imp.)", callback_data=cb("reports"))],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data=cb("main"))]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def sources_kb(sources: list, page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Sources list with pagination and toggles."""
    buttons = []
    
    # Toggle buttons
    for s in sources:
        status_icon = "🟢" if s.is_enabled else "🔴"
        # Action: toggle source
        btn = InlineKeyboardButton(
            text=f"{status_icon} {s.name[:20]}",
            callback_data=cb("sources", "toggle", s.type, page) # Pass type correctly or unique ID
        )
        buttons.append([btn])
        
    # Pagination
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=cb("sources", "nav", "", page - 1)))
    nav.append(InlineKeyboardButton(text=f"Стр {page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=cb("sources", "nav", "", page + 1)))
    buttons.append(nav)
    
    # Reset health stats
    buttons.append([
        InlineKeyboardButton(text="🔄 Сброс проверок", callback_data=cb("sources", "reset_checks", "", page))
    ])
    
    # Standard Nav
    buttons.append(nav_row(back_to="admin"))
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def filters_kb(current_thresholds: dict) -> InlineKeyboardMarkup:
    """Adjust filter thresholds."""
    def btn_row(label, key, val, step=0.1):
        return [
            InlineKeyboardButton(text=f"{label}: {val}", callback_data="noop"),
            InlineKeyboardButton(text="➖", callback_data=cb("filters", "dec", key)),
            InlineKeyboardButton(text="➕", callback_data=cb("filters", "inc", key)),
        ]

    buttons = []
    buttons.append(btn_row("Filter1", "filter1", current_thresholds.get("filter1_threshold", 4.0), 0.5))
    buttons.append(btn_row("Relevance", "relevance", current_thresholds.get("min_relevance", 0.6), 0.05))
    buttons.append(btn_row("Urgency", "urgency", current_thresholds.get("min_urgency", 3), 1))
    
    buttons.append(nav_row(back_to="admin"))
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def ranking_kb(limits: dict) -> InlineKeyboardMarkup:
    """Adjust ranking/limits."""
    buttons = [
        [
            InlineKeyboardButton(text=f"Max/Day: {limits.get('max_signals_per_day', 5)}", callback_data="noop"),
            InlineKeyboardButton(text="➖", callback_data=cb("ranking", "dec", "max_day")),
            InlineKeyboardButton(text="➕", callback_data=cb("ranking", "inc", "max_day")),
        ],
        nav_row(back_to="admin")
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
    
# Alias for backwards compatibility if needed
limits_kb = ranking_kb


def confirm_kb(action: str, param: str) -> InlineKeyboardMarkup:
    """Generic confirmation."""
    buttons = [
        [
            InlineKeyboardButton(text="✅ Да", callback_data=cb("confirm", "yes", f"{action}:{param}")),
            InlineKeyboardButton(text="❌ Нет", callback_data=cb("confirm", "no", f"{action}:{param}")),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def close_kb() -> InlineKeyboardMarkup:
    """Close button only."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Закрыть", callback_data=cb("close"))]
    ])


def control_kb(is_paused: bool) -> InlineKeyboardMarkup:
    """Control panel actions."""
    pause_text = "▶️ Resume" if is_paused else "⏸ Pause"
    pause_action = "resume" if is_paused else "pause"
    
    buttons = [
        [
            InlineKeyboardButton(text=pause_text, callback_data=cb("control", pause_action)),
            InlineKeyboardButton(text="⚡ Force Run", callback_data=cb("control", "force_run")),
        ],
        [
            InlineKeyboardButton(text="🔄 Reload Config", callback_data=cb("control", "reload")),
            InlineKeyboardButton(text="📸 Snapshot", callback_data=cb("snapshot", "create")),
        ],
        nav_row(back_to="admin")
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def diag_kb() -> InlineKeyboardMarkup:
    """Diagnostics actions."""
    buttons = [
        [
            InlineKeyboardButton(text="🧪 Self-Check", callback_data=cb("diag", "check")),
            InlineKeyboardButton(text="📜 Error Logs", callback_data=cb("diag", "logs")),
        ],
        nav_row(back_to="admin")
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def llm_kb(stats: dict) -> InlineKeyboardMarkup:
    """LLM Center main menu."""
    buttons = [
        [
            InlineKeyboardButton(text="⚙️ Провайдеры", callback_data=cb("llm_provider")),
            InlineKeyboardButton(text="🔑 API Keys", callback_data=cb("llm_key")),
        ],
        nav_row(back_to="admin")
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def llm_provider_kb(current: str) -> InlineKeyboardMarkup:
    """Select LLM provider."""
    # Mock list
    providers = ["openrouter", "perplexity", "openai"]
    buttons = []
    for p in providers:
        icon = "✅" if p == current else "⚪"
        buttons.append([
            InlineKeyboardButton(text=f"{icon} {p}", callback_data=cb("llm_provider", "set", p))
        ])
    buttons.append(nav_row(back_to="llm"))
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def llm_key_kb(has_key: bool) -> InlineKeyboardMarkup:
    """Manage API Keys."""
    status = "✅ Configured" if has_key else "❌ Missing"
    buttons = [
        [InlineKeyboardButton(text=f"Status: {status}", callback_data="noop")],
        # In real app, we'd have a way to input key or reset
        [InlineKeyboardButton(text="🔄 Reset Key (Cmd only)", callback_data="noop")],
        nav_row(back_to="llm")
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
