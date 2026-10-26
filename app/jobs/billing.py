import logging
from datetime import UTC, datetime, timedelta

from aiogram import Bot
from sqlalchemy import and_, or_, select

from app.db.models import ProductPlan, ServiceStatus, ServiceType, TrafficUsageLog, User, VpnService
from app.db.session import SessionLocal
from app.integrations.pasarguard import PasarGuardError
from app.services.catalog import CatalogService
from app.services.notifications import send_supergroup_message, send_user_message
from app.services.service_lifecycle import (
    disable_user_active_services,
    reactivate_user_disabled_services,
)
from app.services.settings import SettingsService
from app.services.wallet import WalletService

logger = logging.getLogger(__name__)


def cost_for_mb(used_mb: int, price_per_gb: int) -> int:
    return (used_mb * price_per_gb + 1023) // 1024


async def sync_traffic_usage(bot: Bot) -> None:
    # Lock and settle one wallet per transaction. A failed customer must not roll
    # back charges for everyone else, and concurrent syncs must not charge twice.
    eligible = or_(
        VpnService.status == ServiceStatus.active.value,
        and_(
            VpnService.status == ServiceStatus.disabled.value,
            VpnService.disabled_reason == "wallet",
        ),
    )
    async with SessionLocal() as session:
        user_ids = list(
            (
                await session.scalars(
                    select(VpnService.user_id)
                    .where(VpnService.is_test.is_(False), eligible)
                    .distinct()
                    .order_by(VpnService.user_id)
                )
            ).all()
        )

    checked = charged = reassigned = failed = 0
    for user_id in user_ids:
        try:
            async with SessionLocal() as session:
                user = await session.scalar(
                    select(User).where(User.id == user_id).with_for_update()
                )
                if user is None:
                    continue
                catalog = CatalogService(session)
                settings = SettingsService(session)
                smart_price = await settings.get_int("price_multi_smart_per_gb", 9000)
                economy_price = await settings.get_int("price_multi_economy_per_gb", 2000)
                low_threshold = await settings.get_int("low_balance_threshold", 10000)
                services = list(
                    (
                        await session.scalars(
                            select(VpnService)
                            .where(
                                VpnService.user_id == user.id,
                                VpnService.is_test.is_(False),
                                eligible,
                            )
                            .order_by(VpnService.id)
                        )
                    ).all()
                )
                user_failed = False
                user_charged = 0
                user_reassigned = 0
                # Read and bill EVERY service before deciding the wallet state.
                for service in services:
                    checked += 1
                    try:
                        resolved_panel = await catalog.resolve_panel(service.panel_id)
                        panel = await catalog.client_for_panel(resolved_panel.id)
                        total_mb = await panel.total_used_mb(service.pasarguard_username)
                        if total_mb < service.last_traffic_mb:
                            raise PasarGuardError(
                                "Traffic counter moved backwards; manual reconciliation required "
                                f"(recorded_mb={service.last_traffic_mb}, panel_mb={total_mb})"
                            )
                        # Persist legacy mapping only after the account can be read.
                        if service.panel_id != resolved_panel.id:
                            service.panel_id = resolved_panel.id
                            user_reassigned += 1
                        delta_mb = total_mb - service.last_traffic_mb
                        if delta_mb == 0:
                            continue
                        price = (
                            smart_price
                            if service.type == ServiceType.multi_smart.value
                            else economy_price
                        )
                        if service.plan_id:
                            plan = await session.get(ProductPlan, service.plan_id)
                            if plan:
                                price = plan.price_per_gb_toman
                        if price < 0:
                            raise PasarGuardError("Traffic price cannot be negative")
                        cost = cost_for_mb(delta_mb, price)
                        wallet = WalletService(session)
                        await wallet.deduct(
                            user,
                            cost,
                            f"هزینه مصرف ترافیک به مقدار {delta_mb} مگابایت",
                            {"service_id": service.id, "used_mb": delta_mb},
                            allow_negative=True,
                        )
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
                        user_charged += 1
                    except PasarGuardError as exc:
                        failed += 1
                        user_failed = True
                        logger.exception("PasarGuard sync failed for service %s", service.id)
                        await send_supergroup_message(
                            session,
                            bot,
                            "errors",
                            f"خطا در همگام‌سازی مصرف\nسرویس: #{service.id}\n"
                            f"کاربر: {user.telegram_id}\nجزئیات: {str(exc)[:300]}",
                        )

                # Enforce even when usage is unchanged: retry failed disconnects.
                if user.wallet_balance_toman <= 0:
                    disabled = await disable_user_active_services(
                        session,
                        bot,
                        user,
                        "موجودی کیف پول صفر یا منفی شد و سرویس‌ها غیرفعال شدند.",
                    )
                    if disabled:
                        await send_user_message(
                            bot,
                            user.telegram_id,
                            f"موجودی کیف پول شما {user.wallet_balance_toman:,} تومان شد. "
                            "سرویس‌های شما غیرفعال شدند. بعد از شارژ و مثبت شدن موجودی، سرویس‌ها خودکار فعال می‌شوند.",
                        )
                    failed += sum(s.status == ServiceStatus.active.value for s in services)
                elif not user_failed:
                    # Retry a failed top-up reactivation without another payment.
                    await reactivate_user_disabled_services(session, bot, user)
                    if not user.is_blocked:
                        failed += sum(s.status == ServiceStatus.disabled.value for s in services)
                    if user_charged and user.wallet_balance_toman <= low_threshold:
                        await send_user_message(
                            bot,
                            user.telegram_id,
                            f"موجودی کیف پول شما کم است: {user.wallet_balance_toman:,} تومان. لطفاً کیف پول را شارژ کنید.",
                        )
                await session.commit()
                charged += user_charged
                reassigned += user_reassigned
        except Exception:
            failed += 1
            logger.exception("Traffic sync transaction failed for user %s", user_id)

    logger.info(
        "Traffic sync completed: checked=%s charged=%s reassigned=%s failed=%s",
        checked,
        charged,
        reassigned,
        failed,
    )


async def delete_stale_disabled_services(bot: Bot) -> None:
    cutoff = datetime.now(UTC) - timedelta(hours=48)
    async with SessionLocal() as session:
        candidates = list(
            (
                await session.execute(
                    select(VpnService.id, VpnService.user_id).where(
                        VpnService.status == ServiceStatus.disabled.value,
                        VpnService.disabled_reason == "wallet",
                        VpnService.disabled_at <= cutoff,
                    )
                )
            ).all()
        )

    for service_id, user_id in candidates:
        try:
            async with SessionLocal() as session:
                # Same lock order as billing/top-up: a simultaneous top-up must
                # be committed and checked before an account can be deleted.
                user = await session.scalar(
                    select(User).where(User.id == user_id).with_for_update()
                )
                service = await session.get(VpnService, service_id)
                if user is None or service is None or user.wallet_balance_toman > 0:
                    continue
                disabled_at = service.disabled_at
                if disabled_at is not None and disabled_at.tzinfo is None:
                    disabled_at = disabled_at.replace(tzinfo=UTC)
                if (
                    service.status != ServiceStatus.disabled.value
                    or service.disabled_reason != "wallet"
                    or disabled_at is None
                    or disabled_at > cutoff
                ):
                    continue
                panel = await CatalogService(session).client_for_panel(service.panel_id)
                await panel.delete_user(service.pasarguard_username)
                service.status = ServiceStatus.deleted.value
                await session.commit()
                await send_user_message(
                    bot,
                    user.telegram_id,
                    "یکی از سرویس‌های غیرفعال شما به دلیل عدم شارژ/فعال‌سازی طی ۴۸ ساعت حذف شد.",
                )
                await send_supergroup_message(
                    session,
                    bot,
                    "account_changes",
                    f"سرویس غیرفعال بعد از ۴۸ ساعت حذف شد\nکاربر: {user.telegram_id}\nاکانت: {service.pasarguard_username}",
                )
        except Exception:
            logger.exception("Failed deleting stale service %s", service_id)
