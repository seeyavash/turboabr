import logging

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.settings import SettingsService

logger = logging.getLogger(__name__)

TOPIC_KEYS = {
    "users": "supergroup_users_thread_id",
    "receipts": "supergroup_receipts_thread_id",
    "errors": "supergroup_errors_thread_id",
    "orders": "supergroup_orders_thread_id",
    "account_changes": "supergroup_account_changes_thread_id",
}


async def send_supergroup_message(session: AsyncSession, bot: Bot, topic: str, text: str, **kwargs) -> bool:
    settings = SettingsService(session)
    chat_id = await settings.get("supergroup_chat_id", "")
    thread_key = TOPIC_KEYS.get(topic)
    thread_id = await settings.get(thread_key, "") if thread_key else ""
    if not chat_id or not thread_id:
        return False
    try:
        await bot.send_message(int(chat_id), text, message_thread_id=int(thread_id), **kwargs)
        return True
    except Exception:
        logger.exception("Failed to send supergroup notification to topic %s", topic)
        return False


async def send_supergroup_photo(session: AsyncSession, bot: Bot, topic: str, photo: str, caption: str, **kwargs) -> bool:
    settings = SettingsService(session)
    chat_id = await settings.get("supergroup_chat_id", "")
    thread_key = TOPIC_KEYS.get(topic)
    thread_id = await settings.get(thread_key, "") if thread_key else ""
    if not chat_id or not thread_id:
        return False
    try:
        await bot.send_photo(int(chat_id), photo, caption=caption, message_thread_id=int(thread_id), **kwargs)
        return True
    except Exception:
        logger.exception("Failed to send supergroup photo to topic %s", topic)
        return False
