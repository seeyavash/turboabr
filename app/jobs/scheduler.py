import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.db.session import SessionLocal
from app.jobs.billing import delete_stale_disabled_services, sync_traffic_usage
from app.jobs.payments import verify_crypto_payments
from app.services.backups import send_database_backup_to_admins


logger = logging.getLogger(__name__)


def build_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        sync_traffic_usage,
        "interval",
        minutes=30,
        args=[bot],
        id="traffic-sync",
        replace_existing=True,
        next_run_time=datetime.now(UTC),
        coalesce=True,
        max_instances=1,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        delete_stale_disabled_services,
        "interval",
        hours=1,
        args=[bot],
        id="stale-disabled-cleanup",
        replace_existing=True,
        next_run_time=datetime.now(UTC),
        coalesce=True,
        max_instances=1,
        misfire_grace_time=3600,
    )

    async def verify_payments_job() -> None:
        async with SessionLocal() as session:
            await verify_crypto_payments(session, bot)
            await session.commit()

    scheduler.add_job(
        verify_payments_job,
        "interval",
        minutes=5,
        id="payment-verify",
        replace_existing=True,
        next_run_time=datetime.now(UTC),
        coalesce=True,
        max_instances=1,
        misfire_grace_time=300,
    )

    async def daily_backup_job() -> None:
        async with SessionLocal() as session:
            try:
                sent = await send_database_backup_to_admins(
                    bot,
                    session,
                    "بکاپ خودکار روزانه دیتابیس ربات",
                )
                logger.info("Daily database backup sent to %s admins", sent)
            except Exception:
                logger.exception("Daily database backup failed")

    scheduler.add_job(
        daily_backup_job,
        "cron",
        hour=3,
        minute=30,
        timezone=ZoneInfo("Asia/Tehran"),
        id="daily-database-backup",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=3600,
    )
    return scheduler
