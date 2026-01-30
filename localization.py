# ==============================================================================
# LOCALIZATION / ЛОКАЛИЗАЦИЯ
# ==============================================================================
# RU/EN language strings for the bot

TEXTS = {
    "ru": {
        # Welcome & Auth
        "welcome_title": "🛡 <b>Система мониторинга аварий</b>",
        "welcome_desc": "📡 Автоматический сбор новостей\n🤖 AI-анализ релевантности\n⚡ Мгновенные уведомления",
        "welcome_continue": "▶️ Продолжить",
        "enter_password": "🔐 Введите пароль для доступа:",
        "auth_success": "✅ <b>Авторизация успешна!</b>",
        "auth_failed": "❌ Неверный пароль.",
        "already_auth": "ℹ️ Вы уже авторизованы.",
        
        # Progress
        "progress_wait": "⏳ <b>Подождите...</b>",
        "progress_collecting": "🔍 Сбор новостей",
        "progress_analyzing": "🤖 AI-анализ",
        "progress_done": "✅ Готово",
        "progress_time": "Это займёт 30-60 секунд",
        
        # Check results
        "check_complete": "✅ <b>Проверка завершена!</b>",
        "first_check_complete": "🎉 <b>Первичная проверка завершена!</b>",
        "collected": "📥 Собрано",
        "processed": "🤖 Обработано",
        "relevant": "🎯 Релевантных",
        "signals": "📤 Сигналов",
        "events_found": "🎉 Новые события найдены!",
        "no_events": "ℹ️ Релевантных событий нет.",
        "system_ready": "✅ Система готова к работе!",
        "auto_check": "⏱ Автопроверка каждые 30 минут.",
        "choose_action": "⬇️ Выберите действие:",
        
        # Main menu
        "main_menu": "🏠 <b>Главное меню</b>",
        "stats": "📊 Статистика",
        "check": "🔄 Проверить",
        "settings": "⚙️ Настройки",
        "sources": "📋 Источники",
        "help": "ℹ️ Справка",
        "author": "👤 Автор",
        "back": "⬅️ Назад",
        
        # Stats
        "stats_title": "📊 <b>Статистика</b>",
        "total_articles": "📰 Всего статей",
        "processed_articles": "✅ Обработано",
        "in_queue": "⏳ В очереди",
        "filtered_events": "🎯 Релевантных",
        "sent_signals": "📤 Сигналов",
        
        # Settings
        "settings_title": "⚙️ <b>Настройки</b>",
        "notifications": "🔔 Уведомления",
        "threshold_medium": "📈 Порог: Средний",
        "threshold_high": "📊 Порог: Высокий",
        "change_password": "🔑 Сменить пароль",
        "language": "🌐 Язык",
        
        # Help
        "help_title": "📚 <b>Справка</b>",
        "help_commands": "<b>🎛 Команды:</b>",
        "help_auto": "⏱ Система работает автономно каждые 30 минут.",
        
        # Sources
        "sources_title": "📡 <b>Источники</b>",
        "sources_federal": "🏢 Федеральные СМИ",
        "sources_yandex": "📰 Яндекс Новости",
        "sources_mchs": "🚒 МЧС России",
        "sources_industry": "🏭 Отраслевые порталы",
        "sources_regional": "🏘 Региональные СМИ",
        "sources_total": "📊 Всего: <b>100+</b> источников",
        
        # Author
        "author_title": "👨‍💻 <b>Автор проекта</b>",
        "author_dev": "💬 Разработчик: @SalutByBase",
        "author_desc": "🛠 Система мониторинга аварий для определения потребности в насосном оборудовании.",
        "author_coffee": "☕ <i>Автор не отказался бы от чая... хотя любит кофе ☕</i>",
        
        # Scan
        "scan_started": "🔍 <b>Сканирование запущено</b>",
        "scan_connecting": "📡 Подключение к источникам...",
        "scan_parallel": "⚡ Параллельная обработка (20 потоков)",
        "scan_ai": "🤖 AI: Sonar Large 128K",
        "scan_wait": "⏳ <i>Ожидайте 30-60 секунд</i>",
    },
    
    "en": {
        # Welcome & Auth
        "welcome_title": "🛡 <b>Accident Monitoring System</b>",
        "welcome_desc": "📡 Automatic news collection\n🤖 AI relevance analysis\n⚡ Instant notifications",
        "welcome_continue": "▶️ Continue",
        "enter_password": "🔐 Enter password:",
        "auth_success": "✅ <b>Authorization successful!</b>",
        "auth_failed": "❌ Wrong password.",
        "already_auth": "ℹ️ You are already authorized.",
        
        # Progress
        "progress_wait": "⏳ <b>Please wait...</b>",
        "progress_collecting": "🔍 Collecting news",
        "progress_analyzing": "🤖 AI analysis",
        "progress_done": "✅ Done",
        "progress_time": "This will take 30-60 seconds",
        
        # Check results
        "check_complete": "✅ <b>Check complete!</b>",
        "first_check_complete": "🎉 <b>Initial check complete!</b>",
        "collected": "📥 Collected",
        "processed": "🤖 Processed",
        "relevant": "🎯 Relevant",
        "signals": "📤 Signals",
        "events_found": "🎉 New events found!",
        "no_events": "ℹ️ No relevant events.",
        "system_ready": "✅ System is ready!",
        "auto_check": "⏱ Auto-check every 30 minutes.",
        "choose_action": "⬇️ Choose action:",
        
        # Main menu
        "main_menu": "🏠 <b>Main Menu</b>",
        "stats": "📊 Statistics",
        "check": "🔄 Check",
        "settings": "⚙️ Settings",
        "sources": "📋 Sources",
        "help": "ℹ️ Help",
        "author": "👤 Author",
        "back": "⬅️ Back",
        
        # Stats
        "stats_title": "📊 <b>Statistics</b>",
        "total_articles": "📰 Total articles",
        "processed_articles": "✅ Processed",
        "in_queue": "⏳ In queue",
        "filtered_events": "🎯 Relevant",
        "sent_signals": "📤 Signals",
        
        # Settings
        "settings_title": "⚙️ <b>Settings</b>",
        "notifications": "🔔 Notifications",
        "threshold_medium": "📈 Threshold: Medium",
        "threshold_high": "📊 Threshold: High",
        "change_password": "🔑 Change password",
        "language": "🌐 Language",
        
        # Help
        "help_title": "📚 <b>Help</b>",
        "help_commands": "<b>🎛 Commands:</b>",
        "help_auto": "⏱ System runs automatically every 30 minutes.",
        
        # Sources
        "sources_title": "📡 <b>Sources</b>",
        "sources_federal": "🏢 Federal Media",
        "sources_yandex": "📰 Yandex News",
        "sources_mchs": "🚒 EMERCOM Russia",
        "sources_industry": "🏭 Industry portals",
        "sources_regional": "🏘 Regional Media",
        "sources_total": "📊 Total: <b>100+</b> sources",
        
        # Author
        "author_title": "👨‍💻 <b>Project Author</b>",
        "author_dev": "💬 Developer: @SalutByBase",
        "author_desc": "🛠 Accident monitoring system for pump equipment needs.",
        "author_coffee": "☕ <i>Author wouldn't mind some tea... though prefers coffee ☕</i>",
        
        # Scan
        "scan_started": "🔍 <b>Scan started</b>",
        "scan_connecting": "📡 Connecting to sources...",
        "scan_parallel": "⚡ Parallel processing (20 workers)",
        "scan_ai": "🤖 AI: Sonar Large 128K",
        "scan_wait": "⏳ <i>Wait 30-60 seconds</i>",
    }
}


def get_text(key: str, lang: str = "ru") -> str:
    """Get localized text by key"""
    return TEXTS.get(lang, TEXTS["ru"]).get(key, key)
