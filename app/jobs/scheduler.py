from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot

from app.db.session import SessionLocal
from app.jobs.billing import delete_stale_disabled_services, sync_traffic_usage
from app.jobs.payments import verify_crypto_payments


def build_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(sync_traffic_usage, "interval", minutes=30, args=[bot], id="traffic-sync", replace_existing=True)
    scheduler.add_job(delete_stale_disabled_services, "interval", hours=1, args=[bot], id="stale-disabled-cleanup", replace_existing=True)

    async def verify_payments_job() -> None:
        async with SessionLocal() as session:
            await verify_crypto_payments(session)
            await session.commit()

    scheduler.add_job(verify_payments_job, "interval", minutes=5, id="payment-verify", replace_existing=True)
    return scheduler

