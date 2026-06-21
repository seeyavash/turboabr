from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_secret, encrypt_secret
from app.db.models import PanelTemplate, PasarGuardPanel, ProductPlan
from app.integrations.pasarguard import PasarGuardClient


class CatalogService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def active_panels(self) -> list[PasarGuardPanel]:
        result = await self.session.execute(
            select(PasarGuardPanel).where(PasarGuardPanel.is_active.is_(True)).order_by(PasarGuardPanel.id)
        )
        return list(result.scalars())

    async def active_plans(self) -> list[ProductPlan]:
        result = await self.session.execute(
            select(ProductPlan).where(ProductPlan.is_active.is_(True)).order_by(ProductPlan.id)
        )
        return list(result.scalars())

    async def templates_for_panel(self, panel_id: int) -> list[PanelTemplate]:
        result = await self.session.execute(
            select(PanelTemplate).where(PanelTemplate.panel_id == panel_id).order_by(PanelTemplate.id)
        )
        return list(result.scalars())

    async def add_panel(
        self,
        name: str,
        base_url: str,
        username: str,
        password: str,
        group_ids: list[int],
        subscription_client_type: str,
    ) -> PasarGuardPanel:
        panel = PasarGuardPanel(
            name=name,
            base_url=base_url.rstrip("/"),
            username=username,
            password_secret=encrypt_secret(password) or "",
            group_ids=group_ids,
            subscription_client_type=subscription_client_type,
            is_active=True,
        )
        self.session.add(panel)
        await self.session.flush()
        return panel

    async def add_plan(
        self,
        name: str,
        description: str | None,
        price_per_gb_toman: int,
        panel_id: int | None = None,
    ) -> ProductPlan:
        plan = ProductPlan(
            name=name,
            description=description,
            price_per_gb_toman=price_per_gb_toman,
            panel_id=panel_id,
            is_active=True,
        )
        self.session.add(plan)
        await self.session.flush()
        return plan

    async def add_template(
        self,
        panel_id: int,
        name: str,
        group_ids: list[int],
        subscription_client_type: str,
    ) -> PanelTemplate:
        template = PanelTemplate(
            panel_id=panel_id,
            name=name,
            group_ids=group_ids,
            subscription_client_type=subscription_client_type or "v2ray",
            is_active=True,
        )
        self.session.add(template)
        await self.session.flush()
        return template

    async def client_for_panel(self, panel_id: int | None) -> PasarGuardClient:
        if panel_id is None:
            return PasarGuardClient()
        panel = await self.session.get(PasarGuardPanel, panel_id)
        if not panel:
            return PasarGuardClient()
        return PasarGuardClient(
            base_url=panel.base_url,
            username=panel.username,
            password=decrypt_secret(panel.password_secret) or "",
            group_ids=panel.group_ids or [],
            subscription_client_type=panel.subscription_client_type,
        )
