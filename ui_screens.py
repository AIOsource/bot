"""UI Screen Renderers."""
# Generates text content for messages

def header(breadcrumbs: str) -> str:
    """Standard screen header."""
    return f"<b>{breadcrumbs}</b>\n\n"


async def render_main(is_admin: bool = False) -> str:
    text = (
        "👋 <b>PRSBOT Dashboard</b>\n\n"
        "Система мониторинга инфраструктурных событий.\n"
        "Выберите раздел:"
    )
    return text


async def render_health() -> str:
    # Mock health check
    return (
        "🏥 <b>System Health</b>\n\n"
        "✅ Database: Connected\n"
        "✅ Scheduler: Running\n"
        "✅ LLM API: Available\n"
        "✅ RSS Sources: 7/7 OK"
    )


async def render_stats() -> str:
    return (
        "📊 <b>Статистика</b>\n\n"
        "• Сигналов сегодня: 3\n"
        "• Обработано новостей: 142\n"
        "• Отфильтровано: 139"
    )


async def render_stats_sources() -> str:
    return (
        "📋 <b>Источники (Топ-5)</b>\n\n"
        "1. RBC: 42 новости\n"
        "2. TASS: 30 новостей\n"
        "3. Interfax: 15 новостей"
    )


async def render_settings() -> str:
    return (
        "⚙️ <b>Настройки</b>\n\n"
        "Язык: Русский 🇷🇺\n"
        "Часовой пояс: UTC+5"
    )


async def render_about() -> str:
    return (
        "ℹ️ <b>О боте</b>\n\n"
        "PRSBOT v1.5 (SaaS Edition)\n"
        "Developed by Deepmind Agent.\n"
        "2026"
    )


# === ADMIN UI ===

async def render_admin() -> str:
    return (
        f"{header('Меню → Админка')}"
        "Панель администратора.\n"
        "Выберите раздел:"
    )


async def render_sources(sources: list, page: int, total: int) -> str:
    enabled = sum(1 for s in sources if s.is_enabled)
    return (
        f"{header(f'Меню → Админка → Источники ({page+1}/{total})')}"
        f"Всего источников: {len(sources)}\n"
        f"Активно: {enabled}\n\n"
        "Нажмите для вкл/выкл:"
    )


async def render_history(history: list, page: int, total: int) -> str:
    """Render audit history."""
    if not history:
        return f"{header('Меню → Админка → История')}" \
               "История изменений пуста."
               
    text = f"{header(f'Меню → Админка → История ({page+1}/{total})')}"
    
    for item in history:
        # item is ConfigAudit model
        ts = item.timestamp.strftime("%d.%m %H:%M")
        action_icon = "✏️" if item.action == "set" else "🔙" if item.action == "rollback" else "🔄"
        
        val_str = f"{item.old_value} -> {item.new_value}"
        if len(val_str) > 30:
            val_str = f"{item.old_value} -> ..."
            
        text += f"{action_icon} <b>{ts}</b> | {item.user_id}\n"
        text += f"<code>{item.key}</code>\n"
        text += f"{val_str}\n\n"
        
    return text


async def render_diff(diff: dict) -> str:
    """Render config diff."""
    if not diff:
        return f"{header('Меню → Админка → Diff')}" \
               "✅ Нет активных изменений (все значения по умолчанию)."
               
    text = f"{header('Меню → Админка → Diff')}" \
           "<b>Активные изменения (Overrides):</b>\n\n"
           
    for key, vals in diff.items():
        base = vals['base']
        curr = vals['current']
        text += f"🔧 <b>{key}</b>\n"
        text += f"Base: <code>{base}</code>\n"
        text += f"Curr: <code>{curr}</code>\n\n"
        
    return text


async def render_filters() -> str:
    from config_loader import get_config
    c = get_config()
    return (
        f"{header('Меню → Админка → Фильтры')}"
        "Настройка порогов (Hot Reload):\n\n"
        f"• Filter1 Score: {c.filter1_threshold} (min)\n"
        f"• Relevance: {c.min_relevance} (min)\n"
        f"• Urgency: {c.min_urgency} (min)\n"
    )


async def render_limits() -> str:
    from config_loader import get_config
    c = get_config()
    return (
        f"{header('Меню → Админка → Лимиты')}"
        f"Текущие ограничения:\n"
        f"• Max signals/day: {c.limits.max_signals_per_day}\n"
        f"• Processing batch: {c.limits.max_processing_batch}\n"
    )


async def render_confirm(action: str) -> str:
    return (
        f"{header('Подтверждение')}"
        f"Вы уверены, что хотите выполнить: <b>{action}</b>?"
    )


async def render_control(is_paused: bool, status: dict = None) -> str:
    """Render control panel with optional live stats."""
    state = "PAUSED ⏸" if is_paused else "RUNNING ▶️"
    
    text = (
        f"{header('Меню → Админка → Управление')}"
        f"System State: <b>{state}</b>\n"
    )
    
    if status:
        # Live dashboard mode
        import datetime
        now = datetime.datetime.now().strftime("%H:%M:%S")
        text += (
            f"\n📉 <b>Live Stats</b> ({now}):\n"
            f"• Pending: {status.get('pending', 0)}\n"
            f"• Errors 1h: {status.get('errors_1h', 0)}\n"
            f"• Signals 24h: {status.get('signals_24h', 0)}\n"
        )
        
    return text


async def render_diag() -> str:
    return (
        f"{header('Меню → Админка → Диагностика')}"
        "Выбор инструмента:"
    )


async def render_llm_center(stats: dict) -> str:
    """Render LLM stats."""
    # Mock stats if empty
    if not stats:
        stats = {"requests": 0, "tokens": 0, "cost": 0.0, "errors": 0}
        
    return (
        f"{header('Меню → Админка → LLM Center')}"
        f"<b>Сегодня:</b>\n"
        f"• Запросов: {stats.get('requests', 0)}\n"
        f"• Токенов: {stats.get('tokens', 0)}\n"
        f"• Ошибок: {stats.get('errors', 0)}\n"
        f"• Расход: ${stats.get('cost', 0.0):.4f}"
    )
