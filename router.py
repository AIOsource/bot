"""Main bot router setup."""
from aiogram import Bot, Dispatcher, Router

from user import router as user_router
from admin import router as admin_router
from logging_setup import get_logger

logger = get_logger("bot.router")


def setup_routers(dp: Dispatcher) -> None:
    """Setup all routers for the dispatcher."""
    # Include routers (order matters - admin first for priority)
    dp.include_router(admin_router)
    dp.include_router(user_router)
    
    logger.info("bot_routers_setup", routers=["admin", "user"])


async def create_bot(token: str) -> tuple[Bot, Dispatcher]:
    """Create and configure bot and dispatcher."""
    bot = Bot(token=token)
    dp = Dispatcher()
    
    setup_routers(dp)
    
    return bot, dp
