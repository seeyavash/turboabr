import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from app.bot.handlers import build_router
from app.bot.middlewares import DbSessionMiddleware
from app.core.config import settings
from app.core.logging import configure_logging
from app.jobs.scheduler import build_scheduler

logger = logging.getLogger(__name__)


async def main() -> None:
    configure_logging()
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is required")
    redis = Redis.from_url(settings.redis_url)
    bot = Bot(settings.bot_token)
    dp = Dispatcher(storage=RedisStorage(redis=redis))
    dp.update.middleware(DbSessionMiddleware())
    dp.include_router(build_router())

    scheduler = build_scheduler(bot)
    scheduler.start()
    logger.info("Bot started")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
