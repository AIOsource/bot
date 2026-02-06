"""User command handlers for Telegram bot.

Per ТЗ — all user actions logged, no personal data stored.
First /start triggers initial news search with 2-8 min notification.
"""
import asyncio
from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from db_pkg import get_session, SubscriberRepository
from logging_setup import get_logger

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
    """Handle /start command - subscribe user and trigger first search."""
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
        result="subscribed" if created else "already_subscribed",
        is_admin=False
    )
    
    # Check if this is the first /start that triggers search
    from ..main import trigger_first_search, is_first_search_done
    
    if not is_first_search_done():
        # Notify about search time
        await message.answer(
            "Привет. Вы подписаны на сигналы.\n\n"
            "⏳ Запускаю первичный поиск новостей...\n"
            "Это займёт от 2 до 8 минут.\n"
            "Я пришлю уведомление, когда закончу."
        )
        
        # Trigger first search in background
        asyncio.create_task(_run_first_search_and_notify(message))
    else:
        if created:
            # New subscriber after first search already done
            text = (
                "Привет. Вы подписаны на сигналы.\n"
                "Я мониторю открытые новости по РФ и присылаю только значимые события "
                "по ЖКХ/промышленности (аварии/остановки/ремонты).\n"
                "Лимит: до 5 сигналов в сутки.\n\n"
                "Команды: /status /stop /help /privacy"
            )
        else:
            text = (
                "Подписка уже активна.\n"
                "Команды: /status /stop /help /privacy"
            )
        await message.answer(text)


async def _run_first_search_and_notify(message: Message):
    """Run first search and notify user when done."""
    from ..main import trigger_first_search
    
    try:
        await trigger_first_search()
        await message.answer(
            "✅ Первичный поиск завершён!\n\n"
            "Теперь бот работает в автоматическом режиме.\n"
            "Проверка источников: каждые 30 минут.\n"
            "Лимит сигналов: 5/сутки.\n\n"
            "Команды: /status /stop /help /privacy"
        )
    except Exception as e:
        logger.error("first_search_failed", error=str(e))
        await message.answer(
            "⚠️ Ошибка при первичном поиске.\n"
            "Бот продолжит работу в автоматическом режиме."
        )


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
