from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.admin import (
    admin_menu,
    admin_id_actions,
    admin_service_actions,
    admin_user_actions,
    admins_menu,
    panel_actions,
    panels_menu,
    payment_settings_menu,
    plan_actions,
    store_menu,
    user_services_menu,
)
from app.db.models import PasarGuardPanel, PaymentRequest, PaymentStatus, ProductPlan, ServiceStatus, TransactionKind, User, VpnService
from app.services.catalog import CatalogService
from app.services.payments import PaymentService
from app.services.services import VpnServiceManager
from app.services.settings import SettingsService
from app.services.wallet import WalletService

router = Router()


class AdminState(StatesGroup):
    set_value = State()
    add_panel = State()
    edit_panel = State()
    add_plan = State()
    edit_plan = State()
    add_admin = State()
    user_lookup = State()
    broadcast = State()
    wallet_adjust = State()


async def is_admin(session: AsyncSession, telegram_id: int) -> bool:
    return telegram_id in await SettingsService(session).admin_ids()


@router.message(Command("admin"))
async def admin(message: Message, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("Access denied.")
        return
    await message.answer("Admin panel", reply_markup=admin_menu())


@router.callback_query(F.data == "admin:menu")
async def admin_menu_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    await callback.message.answer("Admin panel", reply_markup=admin_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:dashboard")
async def dashboard(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    users = await session.scalar(select(func.count(User.id)))
    active = await session.scalar(select(func.count(VpnService.id)).where(VpnService.status == ServiceStatus.active.value))
    disabled = await session.scalar(select(func.count(VpnService.id)).where(VpnService.status == ServiceStatus.disabled.value))
    wallet_sum = await session.scalar(select(func.coalesce(func.sum(User.wallet_balance_toman), 0)))
    await callback.message.answer(
        f"Users: {users}\nActive services: {active}\nDisabled services: {disabled}\nWallet total: {wallet_sum:,} Toman"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:panels")
async def panels_section(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    await callback.message.answer("Modiriate panelha", reply_markup=panels_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:store")
async def store_section(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    await callback.message.answer("Tanzimat foroshgah", reply_markup=store_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:admins")
async def admins_section(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    await callback.message.answer("Tanzimat adminha", reply_markup=admins_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:payment_settings")
async def payment_settings_section(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    values = await SettingsService(session).all_public()
    wanted = [
        "card_number",
        "card_holder",
        "payment_card_enabled",
        "payment_plisio_enabled",
        "payment_nowpayments_enabled",
        "payment_stars_enabled",
        "plisio_api_token",
        "nowpayments_api_token",
        "stars_to_toman_rate",
    ]
    lines = [f"{key}: {values.get(key)}" for key in wanted]
    await callback.message.answer("\n".join(lines), reply_markup=payment_settings_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:user_services")
async def user_services_section(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    await callback.message.answer("Khadamate karbar", reply_markup=user_services_menu())
    await callback.answer()


@router.callback_query(F.data == "admin_panel:add")
async def add_panel_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    await state.set_state(AdminState.add_panel)
    await callback.message.answer(
        "Send panel data:\n"
        "name | base_url | username | password | group_ids | client_type\n"
        "Example:\n"
        "Main | https://panel.example.com | admin | pass | 1,2 | v2ray"
    )
    await callback.answer()


@router.message(AdminState.add_panel)
async def add_panel_save(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("Access denied.")
        return
    parts = [part.strip() for part in (message.text or "").split("|")]
    if len(parts) != 6:
        await message.answer("Format: name | base_url | username | password | group_ids | client_type")
        return
    group_ids = [int(item.strip()) for item in parts[4].split(",") if item.strip()]
    panel = await CatalogService(session).add_panel(
        name=parts[0],
        base_url=parts[1],
        username=parts[2],
        password=parts[3],
        group_ids=group_ids,
        subscription_client_type=parts[5] or "v2ray",
    )
    await state.clear()
    await message.answer(f"Panel added: #{panel.id} {panel.name}")


@router.callback_query(F.data == "admin_panel:list")
async def panels_list(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    result = await session.execute(select(PasarGuardPanel).order_by(PasarGuardPanel.id))
    panels = list(result.scalars())
    if not panels:
        await callback.message.answer("No PasarGuard panels yet.")
    else:
        for panel in panels:
            await callback.message.answer(
                f"Panel #{panel.id}\n"
                f"Name: {panel.name}\n"
                f"URL: {panel.base_url}\n"
                f"Username: {panel.username}\n"
                f"Groups: {','.join(str(item) for item in (panel.group_ids or [])) or '-'}\n"
                f"Client type: {panel.subscription_client_type}\n"
                f"Active: {panel.is_active}",
                reply_markup=panel_actions(panel.id, panel.is_active),
            )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_panel_edit:"))
async def edit_panel_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    panel = await session.get(PasarGuardPanel, int(callback.data.split(":", 1)[1]))
    if not panel:
        await callback.answer("Panel not found", show_alert=True)
        return
    await state.update_data(panel_id=panel.id)
    await state.set_state(AdminState.edit_panel)
    await callback.message.answer(
        "Current panel:\n"
        f"name: {panel.name}\n"
        f"base_url: {panel.base_url}\n"
        f"username: {panel.username}\n"
        f"group_ids: {','.join(str(item) for item in (panel.group_ids or []))}\n"
        f"client_type: {panel.subscription_client_type}\n\n"
        "Send new data:\n"
        "name | base_url | username | password_or_- | group_ids | client_type\n"
        "Use - for password to keep old password."
    )
    await callback.answer()


@router.message(AdminState.edit_panel)
async def edit_panel_save(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("Access denied.")
        return
    panel = await session.get(PasarGuardPanel, (await state.get_data())["panel_id"])
    if not panel:
        await message.answer("Panel not found.")
        await state.clear()
        return
    parts = [part.strip() for part in (message.text or "").split("|")]
    if len(parts) != 6:
        await message.answer("Format: name | base_url | username | password_or_- | group_ids | client_type")
        return
    from app.core.security import encrypt_secret

    panel.name = parts[0]
    panel.base_url = parts[1].rstrip("/")
    panel.username = parts[2]
    if parts[3] != "-":
        panel.password_secret = encrypt_secret(parts[3]) or ""
    panel.group_ids = [int(item.strip()) for item in parts[4].split(",") if item.strip()]
    panel.subscription_client_type = parts[5] or "v2ray"
    await state.clear()
    await message.answer(f"Panel updated: #{panel.id} {panel.name}")


@router.callback_query(F.data.startswith("admin_panel_enable:"))
async def enable_panel(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    panel = await session.get(PasarGuardPanel, int(callback.data.split(":", 1)[1]))
    if panel:
        panel.is_active = True
    await callback.answer("Panel enabled")


@router.callback_query(F.data.startswith("admin_panel_disable:"))
async def disable_panel(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    panel = await session.get(PasarGuardPanel, int(callback.data.split(":", 1)[1]))
    if panel:
        panel.is_active = False
    await callback.answer("Panel disabled")


@router.callback_query(F.data.startswith("admin_panel_delete:"))
async def delete_panel(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    panel = await session.get(PasarGuardPanel, int(callback.data.split(":", 1)[1]))
    if panel:
        plan_count = await session.scalar(select(func.count(ProductPlan.id)).where(ProductPlan.panel_id == panel.id))
        service_count = await session.scalar(select(func.count(VpnService.id)).where(VpnService.panel_id == panel.id))
        if plan_count or service_count:
            panel.is_active = False
            await callback.answer("Panel has plans/services, disabled instead", show_alert=True)
            return
        await session.delete(panel)
    await callback.answer("Panel deleted")


@router.callback_query(F.data == "admin_plan:add")
async def add_plan_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    await state.set_state(AdminState.add_plan)
    await callback.message.answer(
        "Send tariff data:\n"
        "name | price_per_gb_toman | panel_id(optional)\n"
        "Example:\n"
        "Multi Hoshmand | 9000 | 1"
    )
    await callback.answer()


@router.message(AdminState.add_plan)
async def add_plan_save(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("Access denied.")
        return
    parts = [part.strip() for part in (message.text or "").split("|")]
    if len(parts) not in {2, 3}:
        await message.answer("Format: name | price_per_gb_toman | panel_id(optional)")
        return
    panel_id = int(parts[2]) if len(parts) == 3 and parts[2] else None
    if panel_id and not await session.get(PasarGuardPanel, panel_id):
        await message.answer("Panel not found.")
        return
    plan = await CatalogService(session).add_plan(parts[0], int(parts[1]), panel_id)
    await state.clear()
    await message.answer(f"Tariff added: #{plan.id} {plan.name} - {plan.price_per_gb_toman:,} Toman/GB")


@router.callback_query(F.data == "admin_plan:list")
async def plans_list(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    result = await session.execute(select(ProductPlan).order_by(ProductPlan.id))
    plans = list(result.scalars())
    if not plans:
        await callback.message.answer("No tariffs yet. Defaults are still available until custom tariffs are added.")
    else:
        for plan in plans:
            await callback.message.answer(
                f"Tariff #{plan.id}\n"
                f"Name: {plan.name}\n"
                f"Price: {plan.price_per_gb_toman:,} Toman/GB\n"
                f"Panel: {plan.panel_id or 'env/default'}\n"
                f"Active: {plan.is_active}",
                reply_markup=plan_actions(plan.id, plan.is_active),
            )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_plan_edit:"))
async def edit_plan_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    plan = await session.get(ProductPlan, int(callback.data.split(":", 1)[1]))
    if not plan:
        await callback.answer("Tariff not found", show_alert=True)
        return
    await state.update_data(plan_id=plan.id)
    await state.set_state(AdminState.edit_plan)
    await callback.message.answer(
        "Current tariff:\n"
        f"name: {plan.name}\n"
        f"price_per_gb_toman: {plan.price_per_gb_toman}\n"
        f"panel_id: {plan.panel_id or ''}\n\n"
        "Send new data:\n"
        "name | price_per_gb_toman | panel_id(optional)"
    )
    await callback.answer()


@router.message(AdminState.edit_plan)
async def edit_plan_save(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("Access denied.")
        return
    plan = await session.get(ProductPlan, (await state.get_data())["plan_id"])
    if not plan:
        await message.answer("Tariff not found.")
        await state.clear()
        return
    parts = [part.strip() for part in (message.text or "").split("|")]
    if len(parts) not in {2, 3}:
        await message.answer("Format: name | price_per_gb_toman | panel_id(optional)")
        return
    panel_id = int(parts[2]) if len(parts) == 3 and parts[2] else None
    if panel_id and not await session.get(PasarGuardPanel, panel_id):
        await message.answer("Panel not found.")
        return
    plan.name = parts[0]
    plan.price_per_gb_toman = int(parts[1])
    plan.panel_id = panel_id
    await state.clear()
    await message.answer(f"Tariff updated: #{plan.id} {plan.name}")


@router.callback_query(F.data.startswith("admin_plan_enable:"))
async def enable_plan(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    plan = await session.get(ProductPlan, int(callback.data.split(":", 1)[1]))
    if plan:
        plan.is_active = True
    await callback.answer("Tariff enabled")


@router.callback_query(F.data.startswith("admin_plan_disable:"))
async def disable_plan(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    plan = await session.get(ProductPlan, int(callback.data.split(":", 1)[1]))
    if plan:
        plan.is_active = False
    await callback.answer("Tariff disabled")


@router.callback_query(F.data.startswith("admin_plan_delete:"))
async def delete_plan(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    plan = await session.get(ProductPlan, int(callback.data.split(":", 1)[1]))
    if plan:
        service_count = await session.scalar(select(func.count(VpnService.id)).where(VpnService.plan_id == plan.id))
        if service_count:
            plan.is_active = False
            await callback.answer("Tariff has services, disabled instead", show_alert=True)
            return
        await session.delete(plan)
    await callback.answer("Tariff deleted")


@router.callback_query(F.data == "admin_admin:add")
async def add_admin_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    await state.set_state(AdminState.add_admin)
    await callback.message.answer("Send numeric Telegram ID to add as admin:")
    await callback.answer()


@router.message(AdminState.add_admin)
async def add_admin_save(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("Access denied.")
        return
    new_admin_id = int((message.text or "").strip())
    settings = SettingsService(session)
    ids = await settings.admin_ids()
    ids.add(new_admin_id)
    await settings.set("admin_ids", ",".join(str(item) for item in sorted(ids)))
    await state.clear()
    await message.answer(f"Admin added: {new_admin_id}")


@router.callback_query(F.data == "admin_admin:list")
async def admins_list(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    ids = await SettingsService(session).admin_ids()
    if not ids:
        await callback.message.answer("No admins configured.")
    for admin_id in sorted(ids):
        await callback.message.answer(f"Admin ID: {admin_id}", reply_markup=admin_id_actions(admin_id))
    await callback.answer()


@router.callback_query(F.data.startswith("admin_admin_remove:"))
async def remove_admin(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    admin_id = int(callback.data.split(":", 1)[1])
    if admin_id == callback.from_user.id:
        await callback.answer("You cannot remove yourself here", show_alert=True)
        return
    settings = SettingsService(session)
    configured = await settings.get("admin_ids", "")
    ids = {int(item.strip()) for item in (configured or "").split(",") if item.strip()}
    if admin_id not in ids:
        await callback.answer("This admin comes from ENV or is not removable here", show_alert=True)
        return
    ids.remove(admin_id)
    await settings.set("admin_ids", ",".join(str(item) for item in sorted(ids)))
    await callback.answer("Admin removed")


@router.callback_query(F.data == "admin_user:lookup")
async def user_lookup_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    await state.set_state(AdminState.user_lookup)
    await callback.message.answer("Send numeric Telegram ID:")
    await callback.answer()


async def send_admin_user_info(message: Message, session: AsyncSession, telegram_id: int) -> None:
    user = (await session.execute(select(User).where(User.telegram_id == telegram_id))).scalar_one_or_none()
    if not user:
        await message.answer("User not found.")
        return
    result = await session.execute(select(VpnService).where(VpnService.user_id == user.id))
    services = list(result.scalars())
    active_count = len([service for service in services if service.status == ServiceStatus.active.value])
    disabled_count = len([service for service in services if service.status == ServiceStatus.disabled.value])
    await message.answer(
        f"User {user.telegram_id}\n"
        f"Name: {user.full_name or '-'}\n"
        f"Username: @{user.username or '-'}\n"
        f"Wallet: {user.wallet_balance_toman:,} Toman\n"
        f"Services: {len(services)} total, {active_count} active, {disabled_count} disabled\n"
        f"Test used: {user.has_test_account}\n"
        f"Blocked: {user.is_blocked}",
        reply_markup=admin_user_actions(user.id, user.is_blocked),
    )


@router.message(AdminState.user_lookup)
async def user_lookup_state(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("Access denied.")
        return
    await send_admin_user_info(message, session, int((message.text or "").strip()))
    await state.clear()


@router.callback_query(F.data == "admin:users")
async def users_list(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    result = await session.execute(select(User).order_by(User.created_at.desc()).limit(20))
    users = list(result.scalars())
    if not users:
        await callback.message.answer("No users yet.")
    else:
        lines = [
            f"{user.telegram_id} | {user.full_name or '-'} | {user.wallet_balance_toman:,} Toman"
            for user in users
        ]
        await callback.message.answer("Latest users:\n" + "\n".join(lines))
    await callback.answer()


@router.callback_query(F.data == "admin:services")
async def services_list(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    result = await session.execute(
        select(VpnService, User)
        .join(User, User.id == VpnService.user_id)
        .where(VpnService.status != ServiceStatus.deleted.value)
        .order_by(VpnService.created_at.desc())
        .limit(20)
    )
    rows = list(result.all())
    if not rows:
        await callback.message.answer("No services yet.")
    for service, user in rows:
        await callback.message.answer(
            f"Service #{service.id}\n"
            f"User: {user.telegram_id}\n"
            f"Type: {service.type}\n"
            f"Status: {service.status}\n"
            f"Billed: {service.total_billed_mb} MB",
            reply_markup=admin_service_actions(service.id, service.status == ServiceStatus.disabled.value),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_set:"))
async def admin_set_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    key = callback.data.split(":", 1)[1]
    await state.update_data(setting_key=key)
    await state.set_state(AdminState.set_value)
    await callback.message.answer(f"Send new value for {key}. For card_info use: card_number | holder")
    await callback.answer()


@router.message(AdminState.set_value)
async def admin_set_value(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("Access denied.")
        return
    data = await state.get_data()
    key = data["setting_key"]
    service = SettingsService(session)
    if key == "card_info":
        parts = [part.strip() for part in (message.text or "").split("|", 1)]
        if len(parts) != 2:
            await message.answer("Use: card_number | holder")
            return
        card, holder = parts
        await service.set("card_number", card)
        await service.set("card_holder", holder)
    else:
        await service.set(key, message.text or "")
    await state.clear()
    await message.answer("Saved.")


@router.callback_query(F.data == "admin:receipts")
async def pending_receipts(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    result = await session.execute(
        select(PaymentRequest).where(
            PaymentRequest.method == "card",
            PaymentRequest.status == PaymentStatus.pending.value,
        )
    )
    payments = list(result.scalars())
    if not payments:
        await callback.message.answer("No pending receipts.")
    for payment in payments:
        await callback.message.answer(f"Receipt #{payment.id}: {payment.amount_toman:,} Toman")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_receipt_ok:"))
async def approve_receipt(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    payment = await session.get(PaymentRequest, int(callback.data.split(":", 1)[1]))
    if payment:
        await PaymentService(session).approve(payment, f"Approved by {callback.from_user.id}")
        user = await session.get(User, payment.user_id)
        if user:
            await callback.bot.send_message(user.telegram_id, f"Receipt approved. Wallet charged by {payment.amount_toman:,} Toman.")
    await callback.answer("Approved")


@router.callback_query(F.data.startswith("admin_receipt_no:"))
async def reject_receipt(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    payment = await session.get(PaymentRequest, int(callback.data.split(":", 1)[1]))
    if payment:
        await PaymentService(session).reject(payment, f"Rejected by {callback.from_user.id}")
        user = await session.get(User, payment.user_id)
        if user:
            await callback.bot.send_message(user.telegram_id, "Receipt rejected. Please contact support if this is wrong.")
    await callback.answer("Rejected")


@router.callback_query(F.data.startswith("admin_svc_disable:"))
async def admin_disable_service(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    service = await session.get(VpnService, int(callback.data.split(":", 1)[1]))
    if service:
        panel = await CatalogService(session).client_for_panel(service.panel_id)
        await VpnServiceManager(session, panel).disable(service)
    await callback.answer("Disabled")


@router.callback_query(F.data.startswith("admin_svc_reactivate:"))
async def admin_reactivate_service(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    service = await session.get(VpnService, int(callback.data.split(":", 1)[1]))
    if service:
        panel = await CatalogService(session).client_for_panel(service.panel_id)
        await VpnServiceManager(session, panel).reenable(service)
    await callback.answer("Reactivated")


@router.callback_query(F.data.startswith("admin_svc_delete:"))
async def admin_delete_service(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    service = await session.get(VpnService, int(callback.data.split(":", 1)[1]))
    if service:
        panel = await CatalogService(session).client_for_panel(service.panel_id)
        await VpnServiceManager(session, panel).delete(service)
    await callback.answer("Deleted")


@router.callback_query(F.data.startswith("admin_user_block:"))
async def admin_block_user(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    user = await session.get(User, int(callback.data.split(":", 1)[1]))
    if user:
        user.is_blocked = True
        result = await session.execute(
            select(VpnService).where(
                VpnService.user_id == user.id,
                VpnService.status == ServiceStatus.active.value,
            )
        )
        for service in result.scalars():
            panel = await CatalogService(session).client_for_panel(service.panel_id)
            await VpnServiceManager(session, panel).disable(service)
    await callback.answer("User blocked")


@router.callback_query(F.data.startswith("admin_user_unblock:"))
async def admin_unblock_user(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    user = await session.get(User, int(callback.data.split(":", 1)[1]))
    if user:
        user.is_blocked = False
    await callback.answer("User unblocked")


@router.callback_query(F.data == "admin:broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    await state.set_state(AdminState.broadcast)
    await callback.message.answer("Send broadcast text.")
    await callback.answer()


@router.message(AdminState.broadcast)
async def broadcast_send(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("Access denied.")
        return
    result = await session.execute(select(User.telegram_id))
    sent = 0
    for telegram_id in result.scalars():
        try:
            await message.bot.send_message(telegram_id, message.text or "")
            sent += 1
        except Exception:
            pass
    await state.clear()
    await message.answer(f"Broadcast sent to {sent} users.")


@router.message(Command("add_balance"))
async def add_balance(message: Message, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("Access denied.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Usage: /add_balance <telegram_id> <amount>")
        return
    user = (await session.execute(select(User).where(User.telegram_id == int(parts[1])))).scalar_one_or_none()
    if not user:
        await message.answer("User not found.")
        return
    await WalletService(session).add(user, int(parts[2]), TransactionKind.admin_adjustment, f"Admin adjustment by {message.from_user.id}")
    await message.answer("Balance updated.")


@router.message(Command("remove_balance"))
async def remove_balance(message: Message, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("Access denied.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Usage: /remove_balance <telegram_id> <amount>")
        return
    user = (await session.execute(select(User).where(User.telegram_id == int(parts[1])))).scalar_one_or_none()
    if not user:
        await message.answer("User not found.")
        return
    amount = min(user.wallet_balance_toman, int(parts[2]))
    await WalletService(session).deduct(
        user,
        amount,
        f"Admin balance removal by {message.from_user.id}",
        {"admin_id": message.from_user.id},
    )
    await message.answer("Balance updated.")


@router.message(Command("user"))
async def user_lookup(message: Message, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("Access denied.")
        return
    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Usage: /user <telegram_id>")
        return
    await send_admin_user_info(message, session, int(parts[1]))


@router.message(Command("service_disable"))
async def service_disable(message: Message, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("Access denied.")
        return
    service = await session.get(VpnService, int((message.text or "").split()[1]))
    if service:
        panel = await CatalogService(session).client_for_panel(service.panel_id)
        await VpnServiceManager(session, panel).disable(service)
        await message.answer("Service disabled.")
