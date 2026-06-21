import logging
from datetime import UTC, datetime, timedelta

from aiogram import Bot
from sqlalchemy import select

from app.db.models import ProductPlan, ServiceStatus, ServiceType, TrafficUsageLog, User, VpnService
from app.db.session import SessionLocal
from app.integrations.pasarguard import PasarGuardError
from app.services.catalog import CatalogService
from app.services.notifications import send_supergroup_message
from app.services.settings import SettingsService
from app.services.wallet import WalletService

logger = logging.getLogger(__name__)


def cost_for_mb(used_mb: int, price_per_gb: int) -> int:
    return (used_mb * price_per_gb + 1023) // 1024


async def sync_traffic_usage(bot: Bot) -> None:
    async with SessionLocal() as session:
        catalog = CatalogService(session)
        settings = SettingsService(session)
        smart_price = await settings.get_int("price_multi_smart_per_gb", 9000)
        economy_price = await settings.get_int("price_multi_economy_per_gb", 2000)
        low_threshold = await settings.get_int("low_balance_threshold", 10000)

        result = await session.execute(
            select(VpnService, User)
            .join(User, User.id == VpnService.user_id)
            .where(VpnService.status == ServiceStatus.active.value, VpnService.is_test.is_(False))
        )
        for service, user in result.all():
            try:
                panel = await catalog.client_for_panel(service.panel_id)
                total_mb = await panel.total_used_mb(service.pasarguard_username)
                delta_mb = max(0, total_mb - service.last_traffic_mb)
                if delta_mb == 0:
                    continue
                price = smart_price if service.type == ServiceType.multi_smart.value else economy_price
                if service.plan_id:
                    plan = await session.get(ProductPlan, service.plan_id)
                    if plan:
                        price = plan.price_per_gb_toman
                cost = cost_for_mb(delta_mb, price)
                wallet = WalletService(session)
                paid = await wallet.deduct(
                    user,
                    cost,
                    f"هزینه مصرف ترافیک به مقدار {delta_mb} مگابایت",
                    {"service_id": service.id, "used_mb": delta_mb},
                )
                if not paid:
                    await panel.set_disabled(service.pasarguard_username, True)
                    service.status = ServiceStatus.disabled.value
                    service.disabled_at = datetime.now(UTC)
                    await bot.send_message(
                        user.telegram_id,
                        "سرویس شما به دلیل کافی نبودن موجودی کیف پول غیرفعال شد. "
                        "برای فعال‌سازی مجدد، کیف پول خود را شارژ کنید.",
                    )
                    continue
                await wallet.pay_referral_cashback(user, cost)
                service.last_traffic_mb = total_mb
                service.total_billed_mb += delta_mb
                session.add(
                    TrafficUsageLog(
                        service_id=service.id,
                        used_mb_delta=delta_mb,
                        cost_toman=cost,
                        wallet_balance_after=user.wallet_balance_toman,
                        raw_total_mb=total_mb,
                    )
                )
                if user.wallet_balance_toman <= low_threshold:
                    await bot.send_message(
                        user.telegram_id,
                        f"موجودی کیف پول شما کم است: {user.wallet_balance_toman:,} تومان. لطفاً کیف پول را شارژ کنید.",
                    )
            except PasarGuardError:
                logger.exception("PasarGuard sync failed for service %s", service.id)
                await send_supergroup_message(
                    session,
                    bot,
                    "errors",
                    f"خطا در همگام‌سازی مصرف\nسرویس: #{service.id}\nکاربر: {user.telegram_id}",
                )
        await session.commit()


async def delete_stale_disabled_services(bot: Bot) -> None:
    async with SessionLocal() as session:
        catalog = CatalogService(session)
        cutoff = datetime.now(UTC) - timedelta(hours=48)
        result = await session.execute(
            select(VpnService, User)
            .join(User, User.id == VpnService.user_id)
            .where(VpnService.status == ServiceStatus.disabled.value, VpnService.disabled_at <= cutoff)
        )
        for service, user in result.all():
            try:
                panel = await catalog.client_for_panel(service.panel_id)
                await panel.delete_user(service.pasarguard_username)
                service.status = ServiceStatus.deleted.value
                await bot.send_message(user.telegram_id, "یکی از سرویس‌های غیرفعال شما به دلیل عدم شارژ/فعال‌سازی طی ۴۸ ساعت حذف شد.")
                await send_supergroup_message(
                    session,
                    bot,
                    "account_changes",
                    f"سرویس غیرفعال بعد از ۴۸ ساعت حذف شد\nکاربر: {user.telegram_id}\nاکانت: {service.pasarguard_username}",
                )
            except PasarGuardError:
                logger.exception("Failed deleting stale service %s", service.id)
                await send_supergroup_message(
                    session,
                    bot,
                    "errors",
                    f"خطا در حذف سرویس غیرفعال قدیمی\nسرویس: #{service.id}\nکاربر: {user.telegram_id}",
                )
        await session.commit()
