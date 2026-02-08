"""Rate-limited message broadcaster."""
import asyncio
from typing import List, Optional
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest, TelegramRetryAfter

from db_pkg import get_session, SubscriberRepository, Subscriber
from logging_setup import get_logger

logger = get_logger("bot.broadcaster")


class Broadcaster:
    """Rate-limited message broadcaster for Telegram.
    
    Per ТЗ: 10-15 msg/sec recommended to avoid FloodWait.
    """
    
    def __init__(self, bot: Bot, messages_per_second: float = 15):
        self.bot = bot
        self.delay = 1.0 / messages_per_second  # Delay between messages
    
    async def broadcast(
        self,
        text: str,
        parse_mode: str = "HTML",
        disable_web_page_preview: bool = True
    ) -> tuple[int, int]:
        """
        Broadcast message to all active subscribers.
        
        Returns:
            (sent_count, failed_count)
        """
        async with get_session() as session:
            subscribers = await SubscriberRepository.get_active(session)
        
        if not subscribers:
            logger.info("broadcast_no_subscribers")
            return 0, 0
        
        sent = 0
        failed = 0
        deactivated = []
        
        for subscriber in subscribers:
            try:
                await self.bot.send_message(
                    chat_id=subscriber.chat_id,
                    text=text,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_web_page_preview
                )
                sent += 1
                
            except TelegramForbiddenError:
                # Bot blocked by user
                deactivated.append(subscriber.chat_id)
                failed += 1
                
            except TelegramBadRequest as e:
                # Chat not found or other issue
                if "chat not found" in str(e).lower():
                    deactivated.append(subscriber.chat_id)
                failed += 1
                logger.warning("broadcast_bad_request", chat_id=subscriber.chat_id, error=str(e))
                
            except TelegramRetryAfter as e:
                # Flood control - wait and retry
                logger.warning("broadcast_flood_wait", seconds=e.retry_after)
                await asyncio.sleep(e.retry_after)
                try:
                    await self.bot.send_message(
                        chat_id=subscriber.chat_id,
                        text=text,
                        parse_mode=parse_mode,
                        disable_web_page_preview=disable_web_page_preview
                    )
                    sent += 1
                except Exception:
                    failed += 1
                    
            except Exception as e:
                failed += 1
                logger.error("broadcast_error", chat_id=subscriber.chat_id, error=str(e))
            
            # Rate limiting
            await asyncio.sleep(self.delay)
        
        # Deactivate blocked users
        if deactivated:
            async with get_session() as session:
                for chat_id in deactivated:
                    await SubscriberRepository.set_active(session, chat_id, False)
                await session.commit()
            logger.info("broadcast_deactivated", count=len(deactivated))
        
        logger.info(
            "broadcast_complete",
            sent=sent,
            failed=failed,
            deactivated=len(deactivated)
        )
        
        return sent, failed
    
    async def send_signal(
        self,
        message_text: str,
        signal_id: Optional[int] = None,
        exclude_chat_ids: Optional[List[int]] = None
    ) -> int:
        """
        Send signal to all active subscribers.
        
        Args:
            message_text: Signal text
            signal_id: Signal ID for feedback buttons (admin only)
            exclude_chat_ids: List of chat IDs to exclude
            
        Returns:
            Number of recipients
        """
        exclude = set(exclude_chat_ids or [])
        
        async with get_session() as session:
            subscribers = await SubscriberRepository.get_active(session)
        
        recipients = [s for s in subscribers if s.chat_id not in exclude]
        
        if not recipients:
            return 0
        
        sent, _ = await self._send_to_list(
            recipients,
            message_text,
            signal_id=signal_id,
            parse_mode="HTML",
            disable_web_page_preview=False
        )
        
        return sent
    
    async def _send_to_list(
        self,
        subscribers: List[Subscriber],
        text: str,
        signal_id: Optional[int] = None,
        parse_mode: str = "HTML",
        disable_web_page_preview: bool = True
    ) -> tuple[int, int]:
        """Send to specific list of subscribers."""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from settings import get_settings
        
        settings = get_settings()
        admin_id = settings.admin_chat_id
        
        # Prepare admin keyboard
        admin_kb = None
        if signal_id:
            admin_kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="👍", callback_data=f"fb1:good:{signal_id}"),
                InlineKeyboardButton(text="👎", callback_data=f"fb1:bad:{signal_id}")
            ]])
            
        sent = 0
        failed = 0
        deactivated = []
        
        for subscriber in subscribers:
            try:
                # Attach keyboard only for admin
                reply_markup = admin_kb if subscriber.chat_id == admin_id else None
                
                await self.bot.send_message(
                    chat_id=subscriber.chat_id,
                    text=text,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_web_page_preview,
                    reply_markup=reply_markup
                )
                sent += 1

            except TelegramForbiddenError:
                deactivated.append(subscriber.chat_id)
                failed += 1
                
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after)
                try:
                    await self.bot.send_message(
                        chat_id=subscriber.chat_id,
                        text=text,
                        parse_mode=parse_mode,
                        disable_web_page_preview=disable_web_page_preview
                    )
                    sent += 1
                except Exception:
                    failed += 1
                    
            except Exception as e:
                failed += 1
                logger.debug("send_error", chat_id=subscriber.chat_id, error=str(e))
            
            await asyncio.sleep(self.delay)
        
        # Deactivate blocked users
        if deactivated:
            async with get_session() as session:
                for chat_id in deactivated:
                    await SubscriberRepository.set_active(session, chat_id, False)
                await session.commit()
        
        return sent, failed
