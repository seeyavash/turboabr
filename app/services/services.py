from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ProductPlan, ServiceStatus, ServiceType, User, VpnService
from app.integrations.pasarguard import PasarGuardClient
from app.services.settings import SettingsService


class VpnServiceManager:
    def __init__(self, session: AsyncSession, panel: PasarGuardClient):
        self.session = session
        self.panel = panel

    async def create_paid_service(self, user: User, service_type: ServiceType, username: str | None = None) -> VpnService:
        min_balance = await SettingsService(self.session).get_int("min_new_service_balance", 50000)
        if user.wallet_balance_toman < min_balance:
            raise ValueError(f"برای خرید سرویس جدید، موجودی کیف پول باید حداقل {min_balance:,} تومان باشد.")
        return await self._create(
            user,
            service_type.value,
            is_test=False,
            data_limit_bytes=0,
            expire=0,
            plan_id=None,
            panel_id=None,
            username=username,
        )

    async def create_paid_plan(self, user: User, plan: ProductPlan, username: str | None = None) -> VpnService:
        min_balance = await SettingsService(self.session).get_int("min_new_service_balance", 50000)
        if user.wallet_balance_toman < min_balance:
            raise ValueError(f"برای خرید سرویس جدید، موجودی کیف پول باید حداقل {min_balance:,} تومان باشد.")
        return await self._create(
            user,
            plan.name,
            is_test=False,
            data_limit_bytes=0,
            expire=0,
            plan_id=plan.id,
            panel_id=plan.panel_id,
            username=username,
        )

    async def create_test_service(self, user: User) -> VpnService:
        if user.has_test_account:
            raise ValueError("شما قبلاً اکانت تست دریافت کرده‌اید.")
        user.has_test_account = True
        expire = int((datetime.now(UTC) + timedelta(days=1)).timestamp())
        return await self._create(
            user,
            ServiceType.multi_economy.value,
            is_test=True,
            data_limit_bytes=100 * 1024 * 1024,
            expire=expire,
            plan_id=None,
            panel_id=None,
            username=None,
        )

    async def _create(
        self,
        user: User,
        service_type: str,
        is_test: bool,
        data_limit_bytes: int,
        expire: int,
        plan_id: int | None,
        panel_id: int | None,
        username: str | None,
    ) -> VpnService:
        username = username or f"tg_{user.telegram_id}_{int(datetime.now(UTC).timestamp())}"
        panel_user = await self.panel.create_user(username, data_limit_bytes=data_limit_bytes, expire=expire)
        panel_user_id = panel_user.get("id")
        sub_url = panel_user.get("subscription_url")
        if panel_user_id and not sub_url:
            sub_url = await self.panel.subscription_url(int(panel_user_id), fallback=None)
        service = VpnService(
            user_id=user.id,
            plan_id=plan_id,
            panel_id=panel_id,
            type=service_type,
            status=ServiceStatus.active.value,
            pasarguard_username=username,
            pasarguard_user_id=panel_user_id,
            subscription_url=sub_url,
            is_test=is_test,
        )
        self.session.add(service)
        await self.session.flush()
        return service

    async def reenable(self, service: VpnService) -> None:
        await self.panel.set_disabled(service.pasarguard_username, False)
        service.status = ServiceStatus.active.value
        service.disabled_at = None

    async def disable(self, service: VpnService) -> None:
        await self.panel.set_disabled(service.pasarguard_username, True)
        service.status = ServiceStatus.disabled.value
        service.disabled_at = datetime.now(UTC)

    async def delete(self, service: VpnService) -> None:
        await self.panel.delete_user(service.pasarguard_username)
        service.status = ServiceStatus.deleted.value

    async def active_services_for_user(self, user: User) -> list[VpnService]:
        result = await self.session.execute(
            select(VpnService).where(
                VpnService.user_id == user.id,
                VpnService.status.in_([ServiceStatus.active.value, ServiceStatus.disabled.value]),
            )
        )
        return list(result.scalars())
