import logging
import asyncio
import os
from datetime import datetime, timedelta
from typing import List, Dict, Set
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.error import TelegramError
from telegram.constants import ParseMode
from models import FilteredEvent, TelegramSignal
from config import config
from database import db
from localization import get_text, TEXTS

logger = logging.getLogger(__name__)
BOT_PASSWORD = config.BOT_PASSWORD
authenticated_users: Set[int] = set()
user_settings: Dict[int, dict] = {}
user_languages: Dict[int, str] = {}  # Язык пользователя (ru/en)
pending_auth: Set[int] = set()  # Пользователи ожидающие ввода пароля
user_wizard_state: Dict[int, dict] = {} # Состояние мастера настройки


class TelegramNotifier:
    def __init__(self):
        self.bot_token = config.TELEGRAM_BOT_TOKEN
        self.application = None
        self.bot = None
        self.manual_check_event = None
    
    async def initialize(self):
        try:
            self.application = Application.builder().token(self.bot_token).build()
            self.bot = self.application.bot
            self.application.add_handler(CommandHandler("start", self.start_command))
            self.application.add_handler(CommandHandler("stats", self.stats_command))
            self.application.add_handler(CommandHandler("help", self.help_command))
            self.application.add_handler(CommandHandler("check", self.check_command))
            self.application.add_handler(CommandHandler("settings", self.settings_command))
            self.application.add_handler(CallbackQueryHandler(self.button_callback))
            self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
            await self.application.initialize()
            logger.info("Telegram bot initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing Telegram bot: {e}")
            raise

    async def start(self, manual_check_event=None):
        self.manual_check_event = manual_check_event
        asyncio.create_task(self._run_bot())
        await asyncio.sleep(1)
        logger.info("Telegram bot started")
    
    async def shutdown(self):
        if self.application:
            await self.application.stop()
            await self.application.shutdown()
        logger.info("Telegram bot shutdown complete")
    
    async def _run_bot(self):
        try:
            if not self.application:
                await self.initialize()
            await self.application.start()
            await self.application.updater.start_polling(drop_pending_updates=True)
        except Exception as e:
            logger.error(f"Error running bot: {e}")
    
    def _get_main_keyboard(self, user_id: int = None) -> InlineKeyboardMarkup:
        lang = user_languages.get(user_id, "ru") if user_id else "ru"
        keyboard = [
            [InlineKeyboardButton(get_text("stats", lang), callback_data="stats"), 
             InlineKeyboardButton(get_text("check", lang), callback_data="check_now")],
            [InlineKeyboardButton(get_text("settings", lang), callback_data="settings"), 
             InlineKeyboardButton(get_text("sources", lang), callback_data="sources")],
            [InlineKeyboardButton(get_text("help", lang), callback_data="help"), 
             InlineKeyboardButton(get_text("author", lang), callback_data="author")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    async def start_wizard(self, chat_id: int, user_id: int, lang: str = "ru"):
        """Запуск мастера настройки"""
        text = get_text("wizard_start", lang)
        keyboard = [
            [InlineKeyboardButton(get_text("wizard_quick", lang), callback_data="wizard_quick")],
            [InlineKeyboardButton(get_text("wizard_custom", lang), callback_data="wizard_custom")]
        ]
        await self.bot.send_message(chat_id=chat_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

    def _get_settings_keyboard(self, user_id: int = None) -> InlineKeyboardMarkup:
        lang = user_languages.get(user_id, "ru") if user_id else "ru"
        current_lang = "🇷🇺 RU" if lang == "ru" else "🇬🇧 EN"
        
        # Check pause status
        paused_until = None
        if user_id:
            settings = user_settings.get(user_id, {})
            paused_until = settings.get("paused_until")
            
        pause_btn_text = "⏸ Пауза 24ч"
        pause_callback = "pause_enable_24h"
        
        if paused_until:
            try:
                pause_dt = datetime.fromisoformat(paused_until)
                if pause_dt > datetime.now():
                    pause_btn_text = "▶️ Возобновить"
                    pause_callback = "pause_disable"
            except:
                pass

        keyboard = [
            [InlineKeyboardButton(get_text("notifications", lang) + ": ВКЛ", callback_data="toggle_notifications"),
             InlineKeyboardButton(pause_btn_text, callback_data=pause_callback)],
            [InlineKeyboardButton(get_text("threshold_medium", lang), callback_data="threshold_medium"), 
             InlineKeyboardButton(get_text("threshold_high", lang), callback_data="threshold_high")],
            [InlineKeyboardButton(f"🌐 {get_text('language', lang)}: {current_lang}", callback_data="switch_language")],
            [InlineKeyboardButton(get_text("change_password", lang), callback_data="change_password")],
            [InlineKeyboardButton(get_text("back", lang), callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name or "User"
        lang = user_languages.get(user_id, "ru")
        
        if user_id in authenticated_users:
            # Уже авторизован - показываем главное меню
            await update.message.reply_text(
                f"👋 <b>Добро пожаловать, {user_name}!</b>\n\n"
                f"{get_text('welcome_title', lang)}\n\n"
                f"📡 Источников: <b>100+</b>\n"
                f"🤖 AI: <b>Sonar Large 128K</b>\n"
                f"✅ Статус: <b>активен</b>\n\n"
                f"{get_text('choose_action', lang)}",
                parse_mode=ParseMode.HTML, reply_markup=self._get_main_keyboard(user_id)
            )
        else:
            # Новый пользователь - показываем приветствие с кнопкой Continue
            welcome_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"), 
                 InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
                [InlineKeyboardButton(get_text("welcome_continue", lang), callback_data="continue_to_auth")]
            ])
            
            # Проверяем есть ли картинка приветствия
            welcome_image = os.path.join(os.path.dirname(__file__), "img.png")
            if os.path.exists(welcome_image):
                with open(welcome_image, "rb") as photo:
                    await update.message.reply_photo(
                        photo=photo,
                        caption=f"👋 <b>Добро пожаловать, {user_name}!</b>\n\n"
                               f"{get_text('welcome_title', lang)}\n\n"
                               f"{get_text('welcome_desc', lang)}",
                        parse_mode=ParseMode.HTML,
                        reply_markup=welcome_keyboard
                    )
            else:
                await update.message.reply_text(
                    f"👋 <b>Добро пожаловать, {user_name}!</b>\n\n"
                    f"{get_text('welcome_title', lang)}\n\n"
                    f"{get_text('welcome_desc', lang)}",
                    parse_mode=ParseMode.HTML,
                    reply_markup=welcome_keyboard
                )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in authenticated_users:
            await update.message.reply_text("❌ Сначала авторизуйтесь!")
            return
        help_text = """📚 <b>Справка</b>

<b>🎛 Команды:</b>
▪️ /start — Главное меню
▪️ /stats — Статистика
▪️ /check — Ручная проверка
▪️ /settings — Настройки
▪️ /help — Справка

⏱ Система работает автономно каждые 30 минут."""
        await update.message.reply_text(help_text, parse_mode=ParseMode.HTML, reply_markup=self._get_main_keyboard())
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in authenticated_users:
            await update.message.reply_text("❌ Сначала авторизуйтесь!")
            return
        try:
            stats = db.get_stats()
            await self.send_status_to_user(update.effective_chat.id, stats, show_keyboard=True)
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    async def check_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in authenticated_users:
            await update.message.reply_text("❌ Сначала авторизуйтесь!")
            return
        await update.message.reply_text("🔄 <b>Запуск проверки...</b>\n\nОжидайте 30-60 секунд.", parse_mode=ParseMode.HTML)
        if self.manual_check_event:
            self.manual_check_event.set()
            logger.info(f"📱 Manual check triggered by user {user_id}")
    
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in authenticated_users:
            await update.message.reply_text("❌ Сначала авторизуйтесь!")
            return
        await update.message.reply_text("⚙️ <b>Настройки</b>\n\nВыберите параметры:", parse_mode=ParseMode.HTML, reply_markup=self._get_settings_keyboard())
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        user_name = query.from_user.first_name or "User"
        lang = user_languages.get(user_id, "ru")
        
        callback_data = query.data
        
        # Обработка выбора языка (до авторизации)
        if callback_data == "lang_ru":
            user_languages[user_id] = "ru"
            lang = "ru"
            welcome_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🇷🇺 Русский ✓", callback_data="lang_ru"), 
                 InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
                [InlineKeyboardButton(get_text("welcome_continue", lang), callback_data="continue_to_auth")]
            ])
            try:
                await query.edit_message_caption(
                    caption=f"👋 <b>Добро пожаловать, {user_name}!</b>\n\n"
                           f"{get_text('welcome_title', lang)}\n\n"
                           f"{get_text('welcome_desc', lang)}",
                    parse_mode=ParseMode.HTML,
                    reply_markup=welcome_keyboard
                )
            except:
                await query.edit_message_text(
                    f"👋 <b>Добро пожаловать, {user_name}!</b>\n\n"
                    f"{get_text('welcome_title', lang)}\n\n"
                    f"{get_text('welcome_desc', lang)}",
                    parse_mode=ParseMode.HTML,
                    reply_markup=welcome_keyboard
                )
            return
        
        elif callback_data == "lang_en":
            user_languages[user_id] = "en"
            lang = "en"
            welcome_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"), 
                 InlineKeyboardButton("🇬🇧 English ✓", callback_data="lang_en")],
                [InlineKeyboardButton(get_text("welcome_continue", lang), callback_data="continue_to_auth")]
            ])
            try:
                await query.edit_message_caption(
                    caption=f"👋 <b>Welcome, {user_name}!</b>\n\n"
                           f"{get_text('welcome_title', lang)}\n\n"
                           f"{get_text('welcome_desc', lang)}",
                    parse_mode=ParseMode.HTML,
                    reply_markup=welcome_keyboard
                )
            except:
                await query.edit_message_text(
                    f"👋 <b>Welcome, {user_name}!</b>\n\n"
                    f"{get_text('welcome_title', lang)}\n\n"
                    f"{get_text('welcome_desc', lang)}",
                    parse_mode=ParseMode.HTML,
                    reply_markup=welcome_keyboard
                )
            return
        
            return

        # --- WIZARD HANDLERS ---
        if callback_data == "wizard_quick":
            user_settings[user_id] = {
                "notifications": True, 
                "threshold": 0.6, 
                "region": "all",
                "focus": "all",
                "noise": "med"
            }
            await self._finish_wizard(query.message.chat.id, user_id, lang)
            return

        elif callback_data == "wizard_custom":
            keyboard = [
                [InlineKeyboardButton(get_text("wizard_region_fed", lang), callback_data="wizard_region_fed")],
                [InlineKeyboardButton(get_text("wizard_region_moscow", lang), callback_data="wizard_region_moscow")],
                [InlineKeyboardButton(get_text("wizard_region_all", lang), callback_data="wizard_region_all")],
            ]
            await query.message.edit_text(get_text("wizard_step_1", lang), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
            return

        elif callback_data.startswith("wizard_region_"):
            region = callback_data.replace("wizard_region_", "")
            user_wizard_state[user_id] = {"region": region}
            keyboard = [
                [InlineKeyboardButton(get_text("wizard_focus_accidents", lang), callback_data="wizard_focus_accidents")],
                [InlineKeyboardButton(get_text("wizard_focus_repairs", lang), callback_data="wizard_focus_repairs")],
                [InlineKeyboardButton(get_text("wizard_focus_all", lang), callback_data="wizard_focus_all")],
            ]
            await query.message.edit_text(get_text("wizard_step_2", lang), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
            return

        elif callback_data.startswith("wizard_focus_"):
            focus = callback_data.replace("wizard_focus_", "")
            if user_id in user_wizard_state: user_wizard_state[user_id]["focus"] = focus
            keyboard = [
                [InlineKeyboardButton(get_text("wizard_noise_low", lang), callback_data="wizard_noise_low")],
                [InlineKeyboardButton(get_text("wizard_noise_med", lang), callback_data="wizard_noise_med")],
                [InlineKeyboardButton(get_text("wizard_noise_high", lang), callback_data="wizard_noise_high")],
            ]
            await query.message.edit_text(get_text("wizard_step_3", lang), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
            return

        elif callback_data.startswith("wizard_noise_"):
            noise = callback_data.replace("wizard_noise_", "")
            state = user_wizard_state.get(user_id, {})
            user_settings[user_id] = {
                "notifications": True, "threshold": 0.6,
                "region": state.get("region", "all"), "focus": state.get("focus", "all"), "noise": noise
            }
            await self._finish_wizard(query.message.chat.id, user_id, lang)
            return
        
        # --- FEEDBACK HANDLERS ---
        if callback_data.startswith("feedback_"):
            try:
                action, article_id = callback_data.replace("feedback_", "").split("_", 1)
                vote = "like" if action == "like" else "dislike"
                db.save_user_feedback(article_id, user_id, vote)
                await query.answer(f"Спасибо! Ваш отзыв учтен ({'👍' if vote=='like' else '👎'}).")
                
                # Remove buttons or mark as voted
                # For now just answer toast is enough, or we can edit markup to remove buttons
                await query.edit_message_reply_markup(reply_markup=None)
            except Exception as e:
                logger.error(f"Error handling feedback: {e}")
                await query.answer("Ошибка при сохранении отзыва.")
            return

        if callback_data == "continue_to_auth":
            pending_auth.add(user_id)
            chat_id = query.message.chat_id
            msg_id = query.message.message_id
            
            # Сохраняем message_id для удаления после авторизации
            if not hasattr(self, 'pending_auth_messages'):
                self.pending_auth_messages = {}
            self.pending_auth_messages[chat_id] = msg_id
            
            try:
                await query.edit_message_caption(
                    caption=f"{get_text('enter_password', lang)}",
                    parse_mode=ParseMode.HTML
                )
            except:
                await query.edit_message_text(
                    f"{get_text('enter_password', lang)}",
                    parse_mode=ParseMode.HTML
                )
            return
        
        # Для остальных callback требуется авторизация
        if user_id not in authenticated_users:
            await query.edit_message_text(get_text("auth_failed", lang))
            return

        
        if callback_data == "stats":
            stats = db.get_stats()
            message = self._format_stats_message(stats, lang)
            await query.edit_message_text(message, parse_mode=ParseMode.HTML, reply_markup=self._get_main_keyboard(user_id))
        
        elif callback_data == "check_now":
            chat_id = query.message.chat_id
            await query.edit_message_text(
                f"{get_text('scan_started', lang)}\n\n"
                f"{get_text('scan_connecting', lang)}\n"
                f"{get_text('scan_parallel', lang)}\n"
                f"{get_text('scan_ai', lang)}\n\n"
                f"{get_text('scan_wait', lang)}",
                parse_mode=ParseMode.HTML
            )
            if self.manual_check_event:
                self.manual_check_event.set()
                if not hasattr(self, 'pending_check_chats'):
                    self.pending_check_chats = set()
                self.pending_check_chats.add(chat_id)
                logger.info(f"📱 Manual check triggered by user {user_id}")
        
        elif callback_data == "settings":
            await query.edit_message_text(
                f"{get_text('settings_title', lang)}\n\n{get_text('choose_action', lang)}",
                parse_mode=ParseMode.HTML, reply_markup=self._get_settings_keyboard(user_id))
        
        elif callback_data == "help":
            await query.edit_message_text(
                f"{get_text('help_title', lang)}\n\n"
                f"{get_text('help_commands', lang)}\n"
                f"▪️ /start — {get_text('main_menu', lang)}\n"
                f"▪️ /stats — {get_text('stats', lang)}\n"
                f"▪️ /check — {get_text('check', lang)}\n"
                f"▪️ /settings — {get_text('settings', lang)}\n\n"
                f"{get_text('help_auto', lang)}",
                parse_mode=ParseMode.HTML, reply_markup=self._get_main_keyboard(user_id))
        
        elif callback_data == "main_menu":
            await query.edit_message_text(
                f"{get_text('main_menu', lang)}\n\n{get_text('choose_action', lang)}",
                parse_mode=ParseMode.HTML, reply_markup=self._get_main_keyboard(user_id))
        
        elif callback_data.startswith("threshold_"):
            threshold = callback_data.split("_")[1]
            await query.answer(f"✅ {threshold}")
        
        elif callback_data == "switch_language":
            # Переключение языка
            new_lang = "en" if lang == "ru" else "ru"
            user_languages[user_id] = new_lang
            await query.edit_message_text(
                get_text("settings_title", new_lang) + "\n\n" + get_text("choose_action", new_lang),
                parse_mode=ParseMode.HTML, 
                reply_markup=self._get_settings_keyboard(user_id)
            )
            return
        
        elif callback_data == "pause_enable_24h":
            # Set pause for 24h
            paused_until = (datetime.now() + timedelta(hours=24)).isoformat()
            if user_id not in user_settings: user_settings[user_id] = {}
            user_settings[user_id]["paused_until"] = paused_until
            
            # Save to DB
            db.update_user_settings(user_id, user_settings[user_id])
            await query.answer("⏸ Уведомления приостановлены на 24 часа")
            
            # Refresh keyboard
            await query.edit_message_reply_markup(reply_markup=self._get_settings_keyboard(user_id))
            return

        elif callback_data == "pause_disable":
            # Resume
            if user_id in user_settings and "paused_until" in user_settings[user_id]:
                del user_settings[user_id]["paused_until"]
                
            # Save to DB
            db.update_user_settings(user_id, user_settings[user_id])
            await query.answer("▶️ Уведомления возобновлены")
            
            # Refresh keyboard
            await query.edit_message_reply_markup(reply_markup=self._get_settings_keyboard(user_id))
            return
        
        elif callback_data == "change_password":
            await query.edit_message_text(
                get_text("change_password", lang) + "\n\n" +
                ("Текущий пароль: 1\nИзмените BOT_PASSWORD в secrets.py" if lang == "ru" else "Current password: 1\nChange BOT_PASSWORD in secrets.py"),
                parse_mode=ParseMode.HTML, reply_markup=self._get_settings_keyboard(user_id))
        
        elif callback_data == "author":
            await query.edit_message_text(
                f"{get_text('author_title', lang)}\n\n"
                f"{get_text('author_dev', lang)}\n\n"
                f"{get_text('author_desc', lang)}\n\n"
                f"{get_text('author_coffee', lang)}",
                parse_mode=ParseMode.HTML, reply_markup=self._get_main_keyboard(user_id))
        
        elif callback_data == "sources":
            await query.edit_message_text(
                f"{get_text('sources_title', lang)}\n\n"
                f"{get_text('sources_federal', lang)}\n"
                f"{get_text('sources_yandex', lang)}\n"
                f"{get_text('sources_mchs', lang)}\n"
                f"{get_text('sources_industry', lang)}\n"
                f"{get_text('sources_regional', lang)}\n\n"
                f"{get_text('sources_total', lang)}",
                parse_mode=ParseMode.HTML, reply_markup=self._get_main_keyboard(user_id))
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        message_text = update.message.text.strip()
        lang = user_languages.get(user_id, "ru")
        
        if user_id in authenticated_users:
            await update.message.reply_text(get_text("already_auth", lang), reply_markup=self._get_main_keyboard(user_id))
            return
        
        if message_text == BOT_PASSWORD:
            # Remove from pending auth if any
            pending_auth.discard(user_id)
            
            # Delete password message for security
            try:
                await update.message.delete()
            except:
                pass
                
            # Delete request message if we saved it
            if hasattr(self, 'pending_auth_messages') and chat_id in self.pending_auth_messages:
                try:
                    await self.bot.delete_message(chat_id=chat_id, message_id=self.pending_auth_messages[chat_id])
                    del self.pending_auth_messages[chat_id]
                except:
                    pass
            
            # START WIZARD (User is NOT yet in authenticated_users)
            # They will be added in _finish_wizard
            await self.start_wizard(chat_id, user_id, lang)
            
            logger.info(f"User {user_id} authenticated - starting wizard")
            
            logger.info(f"User {user_id} authenticated - starting initial check")
        else:
            await update.message.reply_text(get_text("auth_failed", lang))
    
    def has_authenticated_users(self) -> bool:
        """Check if there are any authenticated users"""
        return len(authenticated_users) > 0
    
    async def update_progress(self, current: int, total: int, stage: str = "Сбор новостей"):
        """Update progress bar in real-time via edit_message"""
        if not hasattr(self, 'progress_messages') or not self.progress_messages:
            return
        
        if total > 0:
            pct = int((current / total) * 100)
            filled = int(pct / 10)
            bar = "█" * filled + "░" * (10 - filled)
        else:
            bar = "░" * 10
            pct = 0
        
        progress_text = (
            f"✅ <b>Авторизация успешна!</b>\n\n"
            f"⏳ <b>Подождите...</b>\n\n"
            f"🔍 {stage}...\n"
            f"[{bar}] {pct}%\n"
            f"📊 {current}/{total}\n\n"
            f"<i>Это займёт ещё немного...</i>"
        )
        
        for chat_id, msg_id in list(self.progress_messages.items()):
            try:
                await self.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_id,
                    text=progress_text,
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                # Игнорируем ошибки редактирования (например, если ничего не изменилось)
                pass
    
    def _format_stats_message(self, stats: dict, lang: str = "ru") -> str:
        total = stats['total_articles']
        processed = stats['processed_articles']
        if total > 0:
            pct = int((processed / total) * 100)
            filled = int(pct / 10)
            bar = "█" * filled + "░" * (10 - filled)
        else:
            bar = "░" * 10
            pct = 0
        
        progress_label = "Прогресс" if lang == "ru" else "Progress"
        return (
            f"{get_text('stats_title', lang)}\n\n"
            f"{get_text('total_articles', lang)}: <b>{total}</b>\n"
            f"{get_text('processed_articles', lang)}: <b>{processed}</b>\n"
            f"{progress_label}: [{bar}] {pct}%\n\n"
            f"{get_text('in_queue', lang)}: <b>{stats['unprocessed_articles']}</b>\n"
            f"{get_text('filtered_events', lang)}: <b>{stats['filtered_events']}</b>\n"
            f"{get_text('sent_signals', lang)}: <b>{stats['sent_signals']}</b>"
        )
    
    async def send_event(self, event: FilteredEvent) -> bool:
        if not authenticated_users:
            logger.warning("No authenticated users")
            return False
            
        try:
            message = self._format_message(event)
            priority = "high" if event.urgency >= 4 else "medium"
            
            # Feedback Keyboard
            keyboard = [
                [InlineKeyboardButton("👍 Релевантно", callback_data=f"feedback_like_{event.article_id}"),
                 InlineKeyboardButton("👎 Спам/Не то", callback_data=f"feedback_dislike_{event.article_id}")]
            ]
            markup = InlineKeyboardMarkup(keyboard)
            
            sent_count = 0
            for user_id in authenticated_users:
                # User Settings Filter
                settings = user_settings.get(user_id, {})
                
                # Check Pause
                paused_until = settings.get("paused_until")
                if paused_until:
                    try:
                        pause_dt = datetime.fromisoformat(paused_until)
                        if pause_dt > datetime.now():
                            # Paused
                            continue
                    except:
                        pass
                
                noise_level = settings.get("noise", "med")
                
                # Determine threshold
                if noise_level == "low":    # Vital only
                    threshold = 4
                elif noise_level == "high": # All
                    threshold = 1
                else:                       # Med/Default
                    threshold = 3
                
                # Apply Filter
                if event.urgency < threshold and event.action != 'call':
                    continue
                
                try:
                    await self.bot.send_message(chat_id=user_id, text=message, parse_mode=ParseMode.HTML, disable_web_page_preview=False, reply_markup=markup)
                    sent_count += 1
                except TelegramError as e:
                    logger.error(f"Error sending to {user_id}: {e}")
            
            if sent_count > 0:
                signal = TelegramSignal(event_id=event.article_id, title=event.title, message=message, url=event.url, priority=priority, sent_at=datetime.now())
                signal_dict = signal.model_dump()
                signal_dict['sent_at'] = signal_dict['sent_at'].isoformat()
                db.save_sent_signal(signal_dict)
                logger.info(f"Sent to {sent_count} users: {event.title}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error sending event: {e}")
            return False
    
    def _format_message(self, event: FilteredEvent) -> str:
        # Format:
        # <Priority Emoji> <TITLE>
        # <Region> • <Sphere>
        #
        # 📝 <Body text>
        #
        # 💡 <Why importance>
        #
        # 🔗 <Source Link>
        
        # Emoji mapping
        urgency_emojis = {
            5: "🔴", # Critical
            4: "🟠", # High
            3: "🟡", # Medium
        }
        emoji = urgency_emojis.get(event.urgency, "🔵")
        
        # Category mapping
        cat_map = {
            "accident": "АВАРИЯ",
            "outage": "ОТКЛЮЧЕНИЕ",
            "repair": "РЕМОНТ",
            "other": "ИНЦИДЕНТ"
        }
        category_ru = cat_map.get(event.category, event.category.upper())
        
        # Object mapping
        obj_map = {
            "water": "Водоснабжение",
            "heat": "Теплоснабжение",
            "industrial": "Промышленность",
            "unknown": "ЖКХ / Инфраструктура"
        }
        object_ru = obj_map.get(event.object, event.object)
        
        # Region (Mockup if not parseable, but let's assume federal/Moscow for now)
        # In a real scenario we'd parse region from tags. For now let's be generic or use category if applicable.
        region_str = "РФ / Регионы"

        return f"""{emoji} <b>{category_ru} | Уровень {event.urgency}</b>
<i>{object_ru} • {region_str}</i>

<b>Суть события</b>
{event.title}

<b>Почему это важно</b>
{event.why}

🔗 <a href="{event.url}">Читать оригинал</a>"""
    
    def _determine_priority(self, score: float) -> str:
        if score >= 0.9:
            return "high"
        elif score >= 0.7:
            return "medium"
        return "low"
    
    async def send_status_to_user(self, chat_id: int, stats: dict, show_keyboard: bool = False):
        try:
            message = self._format_stats_message(stats)
            kwargs = {"chat_id": chat_id, "text": message, "parse_mode": ParseMode.HTML}
            if show_keyboard:
                kwargs["reply_markup"] = self._get_main_keyboard()
            await self.bot.send_message(**kwargs)
            logger.info("Sent status message")
        except Exception as e:
            logger.error(f"Error sending status: {e}")
    
    async def send_check_results(self, new_articles: int, relevant_events: int, sent_signals: int):
        # Отправляем результаты в pending_check_chats (ручные проверки)
        if hasattr(self, 'pending_check_chats') and self.pending_check_chats:
            results_msg = f"""✅ <b>Проверка завершена!</b>

📥 Собрано: <b>{new_articles}</b>
🤖 Обработано: <b>{new_articles}</b>
🎯 Релевантных: <b>{relevant_events}</b>
📤 Сигналов: <b>{sent_signals}</b>

{'🎉 Новые события найдены!' if relevant_events > 0 else 'ℹ️ Релевантных событий нет.'}"""
            
            for chat_id in self.pending_check_chats.copy():
                try:
                    await self.bot.send_message(chat_id=chat_id, text=results_msg, parse_mode=ParseMode.HTML, reply_markup=self._get_main_keyboard())
                except Exception as e:
                    logger.error(f"Error sending results to {chat_id}: {e}")
            self.pending_check_chats.clear()
        
        # Отправляем главное меню после первого входа
        if hasattr(self, 'first_login_chats') and self.first_login_chats:
            welcome_msg = f"""🎉 <b>Первичная проверка завершена!</b>

📊 Собрано статей: <b>{new_articles}</b>
🎯 Релевантных событий: <b>{relevant_events}</b>

✅ Система готова к работе!
⏱ Автопроверка каждые 30 минут.

⬇️ Выберите действие:"""
            
            for chat_id in self.first_login_chats.copy():
                try:
                    await self.bot.send_message(chat_id=chat_id, text=welcome_msg, parse_mode=ParseMode.HTML, reply_markup=self._get_main_keyboard())
                except Exception as e:
                    logger.error(f"Error sending welcome to {chat_id}: {e}")
            self.first_login_chats.clear()
            
            if hasattr(self, 'progress_messages'):
                self.progress_messages.clear()

    async def _finish_wizard(self, chat_id: int, user_id: int, lang: str):
        """Завершение настройки и запуск проверки"""
        # 0. Save settings to DB
        if user_id in user_settings:
            try:
                db.update_user_settings(user_id, user_settings[user_id])
                logger.info(f"Settings saved for user {user_id}")
            except Exception as e:
                logger.error(f"Error saving settings for {user_id}: {e}")

        # 1. Send completion message
        await self.bot.send_message(chat_id=chat_id, text=get_text("wizard_complete", lang), parse_mode=ParseMode.HTML)
        
        # 2. Start Initial Check UI
        progress_msg = await self.bot.send_message(
            chat_id=chat_id,
            text=f"{get_text('progress_wait', lang)}\n\n"
                 f"🔍 {get_text('progress_collecting', lang)}...\n"
                 "[░░░░░░░░░░] 0%\n\n"
                 f"<i>{get_text('progress_time', lang)}</i>",
            parse_mode=ParseMode.HTML
        )
        
        # 3. Register progress message
        if not hasattr(self, 'progress_messages'):
            self.progress_messages = {}
        self.progress_messages[chat_id] = progress_msg.message_id
        
        # 4. Activate User (Now they are authenticated)
        authenticated_users.add(user_id)
        
        # 5. Trigger first check (if manual trigger needed, otherwise loop catches it)
        # We can trigger it by setting the event
        if self.manual_check_event:
            self.manual_check_event.set()
            if not hasattr(self, 'pending_check_chats'):
                self.pending_check_chats = set()
            self.pending_check_chats.add(chat_id)

        logger.info(f"Wizard finished for {user_id}. Authenticated and check triggered.")


notifier = TelegramNotifier()
