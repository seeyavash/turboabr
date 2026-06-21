import logging
from datetime import UTC, datetime

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ServiceStatus, User, VpnService
from app.integrations.pasarguard import PasarGuardError
from app.services.catalog import CatalogService
from app.services.notifications import send_supergroup_message

logger = logging.getLogger(__name__)


async def disable_user_active_services(session: AsyncSession, bot: Bot, user: User, reason: str) -> int:
    result = await session.execute(
        select(VpnService).where(
            VpnService.user_id == user.id,
            VpnService.status == ServiceStatus.active.value,
            VpnService.is_test.is_(False),
        )
    )
    services = list(result.scalars())
    disabled = 0
    catalog = CatalogService(session)
    for service in services:
        try:
            panel = await catalog.client_for_panel(service.panel_id)
            await panel.set_disabled(service.pasarguard_username, True)
            service.status = ServiceStatus.disabled.value
            service.disabled_at = datetime.now(UTC)
            service.disabled_reason = "wallet"
            disabled += 1
        except PasarGuardError:
            logger.exception("Failed disabling service %s", service.id)
            await send_supergroup_message(
                session,
                bot,
                "errors",
                f"خطا در غیرفعال‌سازی سرویس\nکاربر: {user.telegram_id}\nسرویس: #{service.id}",
            )
    if disabled:
        await send_supergroup_message(
            session,
            bot,
            "account_changes",
            f"{reason}\nکاربر: {user.telegram_id}\nتعداد سرویس‌های غیرفعال‌شده: {disabled}",
        )
    return disabled


async def reactivate_user_disabled_services(session: AsyncSession, bot: Bot, user: User) -> int:
    if user.wallet_balance_toman <= 0:
        return 0
    result = await session.execute(
        select(VpnService).where(
            VpnService.user_id == user.id,
            VpnService.status == ServiceStatus.disabled.value,
            VpnService.disabled_reason == "wallet",
        )
    )
    services = list(result.scalars())
    reactivated = 0
    catalog = CatalogService(session)
    for service in services:
        try:
            panel = await catalog.client_for_panel(service.panel_id)
            await panel.set_disabled(service.pasarguard_username, False)
            service.status = ServiceStatus.active.value
            service.disabled_at = None
            service.disabled_reason = None
            reactivated += 1
        except PasarGuardError:
            logger.exception("Failed reactivating service %s", service.id)
            await send_supergroup_message(
                session,
                bot,
                "errors",
                f"خطا در فعال‌سازی خودکار سرویس\nکاربر: {user.telegram_id}\nسرویس: #{service.id}",
            )
    if reactivated:
        await bot.send_message(user.telegram_id, f"{reactivated} سرویس شما بعد از شارژ کیف پول دوباره فعال شد.")
        await send_supergroup_message(
            session,
            bot,
            "orders",
            f"فعال‌سازی خودکار بعد از شارژ کیف پول\nکاربر: {user.telegram_id}\nتعداد سرویس‌ها: {reactivated}",
        )
    return reactivated
