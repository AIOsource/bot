"""User command handlers for Telegram bot.

Per ТЗ — all user actions logged, no personal data stored.
First /start triggers initial news search with 2-8 min notification.
"""
import asyncio
from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from db_pkg import get_session, SubscriberRepository
from settings import get_settings
from logging_setup import get_logger
from ui_callbacks import show_panel

logger = get_logger("bot.user")
router = Router(name="user")


def mask_chat_id(chat_id: int) -> str:
    """Mask chat_id for logging (last 4 digits)."""
    s = str(abs(chat_id))
    if len(s) <= 4:
        return s
    return "..." + s[-4:]


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Handle /start command - subscribe user and show welcome."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from ui_keyboards import cb
    
    chat_id = message.chat.id
    
    async with get_session() as session:
        subscriber, created = await SubscriberRepository.get_or_create(
            session,
            chat_id=chat_id
        )
        
        # If was inactive, reactivate
        if not created and not subscriber.is_active:
            await SubscriberRepository.set_active(session, chat_id, True)
            created = True  # Treat as new for message
        
        await session.commit()
    
    # Log per ТЗ
    logger.info(
        "user_command",
        chat_id=mask_chat_id(chat_id),
        command="/start",
        result="subscribed" if created else "already_subscribed"
    )
    
    # Show welcome
    await message.answer(
        "👋 <b>Добро пожаловать в PRSBOT</b>\n\n"
        "Система мониторинга инфраструктурных событий.\n"
        "✅ Подписка активирована.\n"
        "📩 Лимит: 5 сигналов в сутки.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="▶️ Продолжить", callback_data=cb("main"))]
        ]),
        parse_mode="HTML"
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    """Show inline menu panel."""
    from ui_callbacks import is_allowed
    
    # Check permissions in groups
    if message.chat.type in ("group", "supergroup"):
        if not is_allowed(message.from_user.id):
            # Silent ignore or minimal notice
            return

    logger.info("user_command", chat_id=mask_chat_id(message.chat.id), command="/menu")
    await show_panel(message)





@router.message(Command("stop"))
async def cmd_stop(message: Message):
    """Handle /stop command - unsubscribe user."""
    chat_id = message.chat.id
    
    async with get_session() as session:
        await SubscriberRepository.set_active(session, chat_id, False)
        await session.commit()
    
    logger.info(
        "user_command",
        chat_id=mask_chat_id(chat_id),
        command="/stop",
        result="unsubscribed",
        is_admin=False
    )
    
    await message.answer("Подписка отключена. Чтобы снова включить — /start")


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command."""
    logger.info(
        "user_command",
        chat_id=mask_chat_id(message.chat.id),
        command="/help",
        result="ok",
        is_admin=False
    )
    
    # Per ТЗ exact text
    text = (
        "Команды:\n"
        "/status — ваш статус подписки\n"
        "/stop — отключить сигналы\n"
        "/privacy — что хранится и что не хранится\n\n"
        "Сигналы отправляются только при высокой релевантности и срочности. "
        "Не чаще 5 раз в сутки."
    )
    await message.answer(text)


@router.message(Command("status"))
async def cmd_status(message: Message):
    """Handle /status command."""
    chat_id = message.chat.id
    
    async with get_session() as session:
        subscriber, _ = await SubscriberRepository.get_or_create(
            session,
            chat_id=chat_id
        )
        is_active = subscriber.is_active
        await session.commit()
    
    logger.info(
        "user_command",
        chat_id=mask_chat_id(chat_id),
        command="/status",
        result="active" if is_active else "inactive",
        is_admin=False
    )
    
    if is_active:
        # Per ТЗ exact text
        text = (
            "Статус: подписка активна\n"
            "Лимит сигналов: 5/сутки\n"
            "Проверка источников: каждые 30 минут"
        )
    else:
        text = "Статус: подписка выключена, включить: /start"
    
    await message.answer(text)


@router.message(Command("privacy"))
async def cmd_privacy(message: Message):
    """Handle /privacy command — data policy."""
    logger.info(
        "user_command",
        chat_id=mask_chat_id(message.chat.id),
        command="/privacy",
        result="ok",
        is_admin=False
    )
    
    # Per ТЗ exact text
    text = (
        "Используются только открытые источники.\n"
        "В базе хранится только ваш chat_id и статус подписки. "
        "Имена/логины не сохраняем."
    )
    await message.answer(text)
